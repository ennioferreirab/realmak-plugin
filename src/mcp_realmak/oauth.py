"""OAuth 2.1 para o botão Connect dos aplicativos (Claude Desktop, Cowork), com login de pessoa.

Bots continuam usando `Authorization: Bearer gld_live_...` direto. O OAuth é a porta das
pessoas: o Connect abre uma página da Realmak, a pessoa prova o e-mail (Google Workspace,
conta do Galeed ou código por e-mail) e o servidor confere no Galeed se esse e-mail tem
acesso ao cérebro. As consultas dela vão ao Galeed com a chave de serviço do servidor e o
header X-Galeed-Act-As, então vale o grant da própria pessoa e revogar no painel vale na hora.

Sem banco. Tudo o que precisa sobreviver entre requisições vai cifrado (Fernet) com
MCP_REALMAK_OAUTH_SECRET: o client_id (cadastro assinado), a transação de login, o código de
autorização (60 s), o access token (1 h) e o refresh token (30 dias). Em memória ficam só os
códigos já usados e as tentativas de código por e-mail.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import hmac
import html
import json
import logging
import re
import secrets
import smtplib
import ssl
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from email.message import EmailMessage
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
from cryptography.fernet import Fernet, InvalidToken
from starlette.authentication import AuthenticationError
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Route

log = logging.getLogger("mcp_realmak.oauth")

ACCESS_PREFIX = "rmk_"
REFRESH_PREFIX = "rmkr_"
CODE_TTL = 60
TXN_TTL = 900
EMAIL_CODE_TTL = 600
EMAIL_CODE_TRIES = 5
ACCESS_TTL = 3600
REFRESH_TTL = 30 * 24 * 3600
MAX_SEEN = 4096
MAX_REDIRECT_URIS = 5
MAX_BODY_BYTES = 16_384
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
DEFAULT_REDIRECT_HOSTS = ("claude.ai", "www.claude.ai", "claude.com", "www.claude.com")
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")
GOOGLE_COOKIE = "rmk_google"
# Rotas operacionais sob /mcp: a borda já repassa /mcp* e o resto do domínio pode ser de outro app.
# Só os metadados /.well-known/oauth-* ficam na raiz, como pedem as RFC 8414 e 9728.
BASE = "/mcp/oauth"

# Confere se o e-mail tem acesso ao cérebro. True/False; AuthenticationError se o Galeed não responder.
VerifyPerson = Callable[[str], Awaitable[bool]]


@dataclass(frozen=True)
class GoogleLogin:
    client_id: str
    client_secret: str
    domain: str = ""  # domínio do Workspace (hd); vazio aceita qualquer conta Google verificada


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    user: str
    password: str
    sender: str


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


_FERNET_RE = re.compile(r"[A-Za-z0-9_-]+={0,2}")


def pkce_s256(verifier: str) -> str:
    return _b64e(hashlib.sha256(verifier.encode("ascii")).digest())


def _norm_email(email: str) -> str:
    return email.strip().lower()


class OAuthServer:
    def __init__(
        self,
        public_url: str,
        secret: str,
        *,
        verify_person: VerifyPerson,
        google: GoogleLogin | None = None,
        galeed_login_url: str = "",
        smtp: SmtpConfig | None = None,
        extra_redirect_hosts: tuple[str, ...] = (),
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.public_url = public_url.rstrip("/")
        self._sign_key = hashlib.sha256(b"sig:" + secret.encode()).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(hashlib.sha256(b"enc:" + secret.encode()).digest()))
        self.verify_person = verify_person
        self.google = google
        self.galeed_login_url = galeed_login_url.rstrip("/")
        self.smtp = smtp
        self.redirect_hosts = set(DEFAULT_REDIRECT_HOSTS) | {h.strip().lower() for h in extra_redirect_hosts if h.strip()}
        self._transport = transport
        self._seen: dict[str, float] = {}  # jti de código já trocado
        self._tries: dict[str, tuple[float, int]] = {}  # jti do código por e-mail → tentativas
        self.send_email = self._send_email_smtp  # trocável nos testes

    # --- blobs cifrados ----------------------------------------------------

    def seal(self, kind: str, data: dict, ttl: int) -> str:
        blob = {**data, "t": kind, "exp": time.time() + ttl}
        return self._fernet.encrypt(json.dumps(blob, separators=(",", ":")).encode()).decode()

    def unseal(self, kind: str, token: str) -> dict | None:
        # O base64 ignora o que vem depois do "=" final; aceite só a forma exata que emitimos.
        if len(token) % 4 or not _FERNET_RE.fullmatch(token):
            return None
        try:
            blob = json.loads(self._fernet.decrypt(token.encode()))
        except (InvalidToken, ValueError, json.JSONDecodeError):
            return None
        if not isinstance(blob, dict) or blob.get("t") != kind or blob.get("exp", 0) < time.time():
            return None
        return blob

    def _first_use(self, jti: str, exp: float) -> bool:
        now = time.time()
        for old in [j for j, e in self._seen.items() if e < now]:
            self._seen.pop(old, None)
        if jti in self._seen or len(self._seen) >= MAX_SEEN:
            return False
        self._seen[jti] = exp
        return True

    # --- tokens ------------------------------------------------------------

    def issue_tokens(self, email: str, client_id: str) -> dict:
        return {
            "access_token": ACCESS_PREFIX + self.seal("at", {"e": email}, ACCESS_TTL),
            "token_type": "Bearer",
            "expires_in": ACCESS_TTL,
            "refresh_token": REFRESH_PREFIX + self.seal("rt", {"e": email, "ci": client_id}, REFRESH_TTL),
        }

    def read_access_token(self, token: str) -> tuple[str, int] | None:
        """(email, expira_em) de um access token emitido aqui, ou None."""
        if not token.startswith(ACCESS_PREFIX):
            return None
        blob = self.unseal("at", token[len(ACCESS_PREFIX):])
        if blob is None or not isinstance(blob.get("e"), str):
            return None
        return blob["e"], int(blob["exp"])

    # --- clientes (client_id assinado) -------------------------------------

    def _sign(self, payload: str) -> str:
        return _b64e(hmac.new(self._sign_key, payload.encode(), hashlib.sha256).digest()[:24])

    def make_client_id(self, name: str, redirect_uris: list[str]) -> str:
        payload = _b64e(json.dumps({"n": name, "r": redirect_uris}, separators=(",", ":")).encode())
        return f"rc_{payload}.{self._sign(payload)}"

    def read_client_id(self, client_id: str) -> dict | None:
        if not client_id.startswith("rc_") or "." not in client_id:
            return None
        payload, _, sig = client_id[3:].partition(".")
        if not hmac.compare_digest(sig, self._sign(payload)):
            return None
        try:
            data = json.loads(_b64d(payload))
        except (ValueError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict) or not isinstance(data.get("r"), list):
            return None
        return data

    def redirect_allowed(self, uri: str) -> bool:
        try:
            parts = urlsplit(uri)
            host = (parts.hostname or "").lower()
        except ValueError:
            return False
        if parts.fragment or not host:
            return False
        if host in LOOPBACK_HOSTS:
            return parts.scheme in ("http", "https")
        return parts.scheme == "https" and host in self.redirect_hosts

    def _check_authorize(self, q: dict[str, str]) -> tuple[str | None, dict]:
        client = self.read_client_id(q.get("client_id", ""))
        if client is None:
            return "Aplicativo não reconhecido. Remova o conector e conecte de novo.", {}
        redirect_uri = q.get("redirect_uri", "")
        if redirect_uri not in client["r"] or not self.redirect_allowed(redirect_uri):
            return "O endereço de retorno do aplicativo não confere com o cadastro.", {}
        if q.get("response_type") != "code":
            return "Pedido de login inválido (response_type).", {}
        if q.get("code_challenge_method") != "S256" or not q.get("code_challenge"):
            return "Pedido de login inválido (PKCE S256 é obrigatório).", {}
        return None, {
            "ci": q["client_id"], "cn": str(client.get("n", "Aplicativo")), "ru": redirect_uri,
            "cc": q["code_challenge"], "st": q.get("state", ""),
        }

    # --- login: passos comuns ---------------------------------------------

    def _methods(self) -> list[str]:
        return [m for m, on in (("google", self.google), ("galeed", self.galeed_login_url), ("email", self.smtp)) if on]

    async def _finish(self, email: str, p: dict) -> Response:
        email = _norm_email(email)
        try:
            ok = await self.verify_person(email)
        except AuthenticationError as exc:
            return _page(_msg_html("Não foi possível conectar", str(exc)), 503)
        if not ok:
            return _page(
                _msg_html(
                    "Sem acesso",
                    f"O e-mail {email} não tem acesso ao cérebro nem às licitações da Realmak. "
                    "Peça acesso a quem administra o Galeed ou o Odoo.",
                ),
                403,
            )
        code = self.seal("code", {"e": email, "cc": p["cc"], "ru": p["ru"], "ci": p["ci"], "j": secrets.token_urlsafe(12)}, CODE_TTL)
        query = {"code": code, **({"state": p["st"]} if p.get("st") else {})}
        sep = "&" if "?" in p["ru"] else "?"
        log.info("Login concluído para %s", _mask(email))
        return RedirectResponse(f"{p['ru']}{sep}{urlencode(query)}", status_code=302, headers=_NO_STORE)

    def _chooser(self, txn: str, p: dict, erro: str = "", status: int = 200) -> Response:
        return _page(_chooser_html(txn, p["cn"], urlsplit(p["ru"]).hostname or "", self._methods(), erro), status)

    # --- Google ------------------------------------------------------------

    async def _google_start(self, request: Request) -> Response:
        p = self.unseal("txn", request.query_params.get("txn", ""))
        if p is None or self.google is None:
            return _page(_msg_html("Login expirado", "Volte ao aplicativo e clique em Connect de novo."), 400)
        nonce = secrets.token_urlsafe(16)
        state = self.seal("gst", {"p": p, "n": nonce}, TXN_TTL)
        params = {
            "client_id": self.google.client_id,
            "redirect_uri": f"{self.public_url}{BASE}/login/google/callback",
            "response_type": "code",
            "scope": "openid email",
            "state": state,
            "prompt": "select_account",
        }
        if self.google.domain:
            params["hd"] = self.google.domain
        resp = RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}", status_code=302, headers=_NO_STORE)
        resp.set_cookie(GOOGLE_COOKIE, nonce, max_age=TXN_TTL, path=f"{BASE}/login/google", secure=self.public_url.startswith("https://"), httponly=True, samesite="lax")
        return resp

    async def _google_callback(self, request: Request) -> Response:
        g = self.google
        st = self.unseal("gst", request.query_params.get("state", ""))
        nonce = request.cookies.get(GOOGLE_COOKIE, "")
        if g is None or st is None or not nonce or not hmac.compare_digest(nonce, str(st.get("n", ""))):
            return _page(_msg_html("Login expirado", "Volte ao aplicativo e clique em Connect de novo."), 400)
        p = st["p"]
        if request.query_params.get("error") or not request.query_params.get("code"):
            return self._chooser(self.seal("txn", p, TXN_TTL), p, "O login com Google foi cancelado.")
        try:
            async with httpx.AsyncClient(timeout=15, transport=self._transport, follow_redirects=False) as c:
                r = await c.post(GOOGLE_TOKEN_URL, data={
                    "code": request.query_params["code"],
                    "client_id": g.client_id,
                    "client_secret": g.client_secret,
                    "redirect_uri": f"{self.public_url}{BASE}/login/google/callback",
                    "grant_type": "authorization_code",
                })
            id_token = r.json().get("id_token", "") if r.status_code == 200 else ""
        except (httpx.HTTPError, ValueError):
            id_token = ""
        email = _google_email(id_token, g)
        if email is None:
            dominio = f" do domínio {g.domain}" if g.domain else ""
            return self._chooser(self.seal("txn", p, TXN_TTL), p, f"Não deu para confirmar o e-mail pelo Google. Use uma conta Google{dominio}.")
        resp = await self._finish(email, p)
        resp.delete_cookie(GOOGLE_COOKIE, path=f"{BASE}/login/google")
        return resp

    # --- conta do Galeed ---------------------------------------------------

    async def _galeed_login(self, form: dict[str, str]) -> Response:
        txn = form.get("txn", "")
        p = self.unseal("txn", txn)
        if p is None or not self.galeed_login_url:
            return _page(_msg_html("Login expirado", "Volte ao aplicativo e clique em Connect de novo."), 400)
        email, senha = _norm_email(form.get("email", "")), form.get("password", "")
        if not email or not senha:
            return self._chooser(txn, p, "Informe e-mail e senha da conta do Galeed.")
        try:
            async with httpx.AsyncClient(timeout=15, transport=self._transport, follow_redirects=False) as c:
                r = await c.post(f"{self.galeed_login_url}/auth/login", json={"email": email, "password": senha})
                if r.status_code == 200:
                    # Só queríamos a prova da senha: encerra a sessão que o Galeed abriu.
                    cookie = r.headers.get("set-cookie", "").split(";", 1)[0]
                    if cookie:
                        with contextlib.suppress(httpx.HTTPError):
                            await c.post(f"{self.galeed_login_url}/auth/logout", headers={"cookie": cookie})
        except httpx.HTTPError:
            return self._chooser(txn, p, "O Galeed não respondeu. Tente de novo em instantes.", 503)
        if r.status_code == 401:
            return self._chooser(txn, p, "E-mail ou senha inválidos.", 401)
        if r.status_code == 429:
            return self._chooser(txn, p, "Muitas tentativas. Espere um minuto e tente de novo.", 429)
        if r.status_code != 200:
            return self._chooser(txn, p, f"O Galeed respondeu HTTP {r.status_code}. Tente de novo em instantes.", 503)
        return await self._finish(email, p)

    # --- código por e-mail -------------------------------------------------

    def _code_hash(self, jti: str, code: str) -> str:
        return hmac.new(self._sign_key, f"{jti}:{code}".encode(), hashlib.sha256).hexdigest()

    async def _send_email_smtp(self, to: str, code: str) -> None:
        s = self.smtp
        if s is None:
            raise RuntimeError("SMTP não configurado")
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = s.sender, to, f"Código de acesso Realmak: {code}"
        msg.set_content(
            f"Seu código para conectar ao servidor da Realmak é {code}.\n\n"
            "Ele vale por 10 minutos. Se não foi você que pediu, ignore este e-mail."
        )

        def enviar() -> None:
            ctx = ssl.create_default_context()
            if s.port == 465:
                with smtplib.SMTP_SSL(s.host, s.port, context=ctx, timeout=20) as smtp:
                    if s.user:
                        smtp.login(s.user, s.password)
                    smtp.send_message(msg)
            else:
                with smtplib.SMTP(s.host, s.port, timeout=20) as smtp:
                    smtp.starttls(context=ctx)
                    if s.user:
                        smtp.login(s.user, s.password)
                    smtp.send_message(msg)

        await asyncio.to_thread(enviar)

    async def _email_start(self, form: dict[str, str]) -> Response:
        txn = form.get("txn", "")
        p = self.unseal("txn", txn)
        if p is None or self.smtp is None:
            return _page(_msg_html("Login expirado", "Volte ao aplicativo e clique em Connect de novo."), 400)
        email = _norm_email(form.get("email", ""))
        if "@" not in email:
            return self._chooser(txn, p, "Informe um e-mail válido.")
        try:
            tem_acesso = await self.verify_person(email)
        except AuthenticationError as exc:
            return self._chooser(txn, p, str(exc), 503)
        jti = secrets.token_urlsafe(12)
        h = ""
        if tem_acesso:
            code = f"{secrets.randbelow(1_000_000):06d}"
            try:
                await self.send_email(email, code)
            except Exception as exc:  # SMTP fora do ar, credencial errada
                log.warning("Falha ao enviar o código por e-mail: %s", type(exc).__name__)
                return self._chooser(txn, p, "Não foi possível enviar o e-mail agora. Tente outra forma de login.", 503)
            h = self._code_hash(jti, code)
        # Mesma resposta com ou sem acesso: a página não revela quem está cadastrado.
        etxn = self.seal("etx", {"p": p, "e": email, "h": h, "j": jti}, EMAIL_CODE_TTL)
        return _page(_code_html(etxn, email), 200)

    async def _email_verify(self, form: dict[str, str]) -> Response:
        etxn = form.get("etxn", "")
        st = self.unseal("etx", etxn)
        if st is None:
            return _page(_msg_html("Código expirado", "Volte ao aplicativo e clique em Connect de novo."), 400)
        now = time.time()
        for old in [j for j, (exp, _) in self._tries.items() if exp < now]:
            self._tries.pop(old, None)
        exp, n = self._tries.get(st["j"], (st["exp"], 0))
        if n >= EMAIL_CODE_TRIES:
            return _page(_msg_html("Tentativas esgotadas", "Volte ao aplicativo e peça um código novo."), 429)
        self._tries[st["j"]] = (exp, n + 1)
        code = "".join(ch for ch in form.get("code", "") if ch.isdigit())
        if not st.get("h") or not hmac.compare_digest(self._code_hash(st["j"], code), st["h"]):
            return _page(_code_html(etxn, st["e"], "Código incorreto."), 401)
        if not self._first_use(st["j"], st["exp"]):
            return _page(_msg_html("Código já usado", "Volte ao aplicativo e clique em Connect de novo."), 400)
        return await self._finish(st["e"], st["p"])

    # --- rotas -------------------------------------------------------------

    def routes(self, resource_routes: list[Route]) -> list[Route]:
        async def metadata(request: Request) -> Response:
            return _json({
                # Igual ao authorization_servers da RFC 9728 (o pydantic normaliza com "/" no fim).
                "issuer": f"{self.public_url}/",
                "authorization_endpoint": f"{self.public_url}{BASE}/authorize",
                "token_endpoint": f"{self.public_url}{BASE}/token",
                "registration_endpoint": f"{self.public_url}{BASE}/register",
                "response_types_supported": ["code"],
                "grant_types_supported": ["authorization_code", "refresh_token"],
                "code_challenge_methods_supported": ["S256"],
                "token_endpoint_auth_methods_supported": ["none"],
            })

        async def register(request: Request) -> Response:
            if request.method == "OPTIONS":
                return _cors(Response(status_code=204))
            try:
                body = json.loads((await request.body())[:MAX_BODY_BYTES])
            except ValueError:
                return _oauth_error("invalid_client_metadata", "JSON inválido")
            uris = body.get("redirect_uris") if isinstance(body, dict) else None
            if not isinstance(uris, list) or not uris or len(uris) > MAX_REDIRECT_URIS:
                return _oauth_error("invalid_redirect_uri", "redirect_uris é obrigatório")
            if any(not isinstance(u, str) or not self.redirect_allowed(u) for u in uris):
                # Só esquema e host: o caminho e a query da URI não entram no log.
                destinos = sorted({f"{urlsplit(str(u)).scheme}://{urlsplit(str(u)).hostname}" for u in uris})
                log.warning(
                    "Registro recusado: redirect URI fora da lista de hosts permitidos: %s (%s, %s)",
                    destinos, str(body.get("client_name") or "")[:80], request.headers.get("user-agent", "")[:80],
                )
                return _oauth_error("invalid_redirect_uri", "redirect_uri não permitida neste servidor")
            name = str(body.get("client_name") or "Aplicativo")[:80]
            return _json(
                {
                    "client_id": self.make_client_id(name, uris),
                    "client_name": name,
                    "redirect_uris": uris,
                    "grant_types": ["authorization_code", "refresh_token"],
                    "response_types": ["code"],
                    "token_endpoint_auth_method": "none",
                    "client_id_issued_at": int(time.time()),
                },
                status=201,
            )

        async def authorize(request: Request) -> Response:
            erro, p = self._check_authorize(dict(request.query_params))
            if erro:
                return _page(_msg_html("Não foi possível conectar", erro), 400)
            return self._chooser(self.seal("txn", p, TXN_TTL), p)

        async def galeed_login(request: Request) -> Response:
            return await self._galeed_login(await _form(request))

        async def email_start(request: Request) -> Response:
            return await self._email_start(await _form(request))

        async def email_verify(request: Request) -> Response:
            return await self._email_verify(await _form(request))

        async def token(request: Request) -> Response:
            if request.method == "OPTIONS":
                return _cors(Response(status_code=204))
            form = await _form(request)
            grant = form.get("grant_type")
            if grant == "authorization_code":
                blob = self.unseal("code", form.get("code", ""))
                if blob is None or not self._first_use(blob["j"], blob["exp"]):
                    return _oauth_error("invalid_grant", "código inválido, usado ou vencido")
                verifier = form.get("code_verifier", "")
                if (
                    blob["ci"] != form.get("client_id")
                    or blob["ru"] != form.get("redirect_uri")
                    or not verifier.isascii()
                    or not hmac.compare_digest(pkce_s256(verifier), blob["cc"])
                ):
                    return _oauth_error("invalid_grant", "client_id, redirect_uri ou code_verifier não conferem")
                return _json(self.issue_tokens(blob["e"], blob["ci"]))
            if grant == "refresh_token":
                raw = form.get("refresh_token", "")
                blob = self.unseal("rt", raw[len(REFRESH_PREFIX):]) if raw.startswith(REFRESH_PREFIX) else None
                if blob is None or blob.get("ci") != form.get("client_id"):
                    return _oauth_error("invalid_grant", "refresh token inválido ou vencido")
                try:
                    ok = await self.verify_person(blob["e"])
                except AuthenticationError as exc:
                    return _oauth_error("temporarily_unavailable", str(exc), 503)
                if not ok:
                    return _oauth_error("invalid_grant", "o acesso desta pessoa ao cérebro foi retirado")
                return _json(self.issue_tokens(blob["e"], blob["ci"]))
            return _oauth_error("unsupported_grant_type", "use authorization_code ou refresh_token")

        return [
            *resource_routes,
            Route("/.well-known/oauth-authorization-server", metadata, methods=["GET", "OPTIONS"]),
            Route(f"{BASE}/register", register, methods=["POST", "OPTIONS"]),
            Route(f"{BASE}/authorize", authorize, methods=["GET"]),
            Route(f"{BASE}/login/google", self._google_start, methods=["GET"]),
            Route(f"{BASE}/login/google/callback", self._google_callback, methods=["GET"]),
            Route(f"{BASE}/login/galeed", galeed_login, methods=["POST"]),
            Route(f"{BASE}/login/email", email_start, methods=["POST"]),
            Route(f"{BASE}/login/email/verify", email_verify, methods=["POST"]),
            Route(f"{BASE}/token", token, methods=["POST", "OPTIONS"]),
        ]


def _google_email(id_token: str, g: GoogleLogin) -> str | None:
    """E-mail verificado do id_token. Ele veio direto do Google por TLS com o nosso client_secret,
    então os claims bastam (OIDC Core 3.1.3.7); conferimos emissor, público, validade e domínio."""
    try:
        claims = json.loads(_b64d(id_token.split(".")[1]))
    except (IndexError, ValueError, json.JSONDecodeError):
        return None
    if claims.get("iss") not in GOOGLE_ISSUERS or claims.get("aud") != g.client_id:
        return None
    if float(claims.get("exp", 0)) < time.time() or claims.get("email_verified") is not True:
        return None
    email = _norm_email(str(claims.get("email", "")))
    if "@" not in email:
        return None
    if g.domain and (claims.get("hd") != g.domain or not email.endswith("@" + g.domain.lower())):
        return None
    return email


def _mask(email: str) -> str:
    nome, _, dominio = email.partition("@")
    return f"{nome[:2]}***@{dominio}"


async def _form(request: Request) -> dict[str, str]:
    raw = (await request.body())[:MAX_BODY_BYTES].decode("utf-8", "replace")
    return {k: v[0] for k, v in parse_qs(raw).items()}


# --- respostas ---------------------------------------------------------------

_NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


def _cors(resp: Response) -> Response:
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, MCP-Protocol-Version"
    return resp


def _json(data: dict, status: int = 200) -> Response:
    return _cors(JSONResponse(data, status_code=status, headers=_NO_STORE))


def _oauth_error(code: str, description: str, status: int = 400) -> Response:
    return _json({"error": code, "error_description": description}, status)


def _page(body: str, status: int) -> Response:
    return HTMLResponse(
        body,
        status_code=status,
        headers={
            **_NO_STORE,
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer",
            # form-action precisa aceitar o redirect final para o aplicativo e o Google.
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self' https: http://localhost:* http://127.0.0.1:*; frame-ancestors 'none'; base-uri 'none'",
        },
    )


_CSS = """
:root{--bg:#fff;--fg:#17181c;--mut:#5d6370;--line:#d9dce3;--acc:#1f4fd8;--err:#b3261e}
@media (prefers-color-scheme:dark){:root{--bg:#14161a;--fg:#eceef2;--mut:#9aa1ad;--line:#2b2f37;--acc:#7ea2ff;--err:#ff8a80}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 system-ui,sans-serif;
display:grid;min-height:100vh;place-items:center;padding:16px}
main{width:100%;max-width:420px}h1{font-size:1.25rem;margin:0 0 .25rem}h2{font-size:1rem;margin:1.5rem 0 .25rem}
p{color:var(--mut);margin:.25rem 0 1rem}label{display:block;font-weight:600;margin:.75rem 0 .35rem}
input{width:100%;padding:.7rem .8rem;border:1px solid var(--line);border-radius:8px;background:transparent;color:inherit;font:inherit}
button,a.btn{display:block;text-align:center;text-decoration:none;margin-top:.75rem;width:100%;padding:.75rem;border:0;border-radius:8px;
background:var(--acc);color:#fff;font:inherit;font-weight:600;cursor:pointer}
hr{border:0;border-top:1px solid var(--line);margin:1.5rem 0}.err{color:var(--err);font-weight:600}
"""


def _shell(inner: str) -> str:
    return (
        '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>Conectar à Realmak</title><style>{_CSS}</style></head><body><main>{inner}</main></body></html>"
    )


def _msg_html(titulo: str, msg: str) -> str:
    return _shell(f"<h1>{html.escape(titulo)}</h1><p class=\"err\">{html.escape(msg)}</p>")


def _chooser_html(txn: str, client_name: str, host: str, methods: list[str], erro: str = "") -> str:
    t = html.escape(txn)
    partes: list[str] = []
    if "google" in methods:
        partes.append(f'<a class="btn" href="{BASE}/login/google?{html.escape(urlencode({"txn": txn}))}">Entrar com Google</a>')
    if "galeed" in methods:
        partes.append(
            f'<h2>Conta do Galeed</h2><form method="post" action="{BASE}/login/galeed">'
            f'<input type="hidden" name="txn" value="{t}">'
            '<label for="ge">E-mail</label><input id="ge" name="email" type="email" autocomplete="username" required>'
            '<label for="gs">Senha</label><input id="gs" name="password" type="password" autocomplete="current-password" required>'
            "<button type=\"submit\">Entrar</button></form>"
        )
    if "email" in methods:
        partes.append(
            f'<h2>Código por e-mail</h2><form method="post" action="{BASE}/login/email">'
            f'<input type="hidden" name="txn" value="{t}">'
            '<label for="ce">E-mail</label><input id="ce" name="email" type="email" autocomplete="email" required>'
            "<button type=\"submit\">Enviar código</button></form>"
        )
    aviso = f'<p class="err">{html.escape(erro)}</p>' if erro else ""
    return _shell(
        "<h1>Conectar à Realmak</h1>"
        f"<p><strong>{html.escape(client_name)}</strong> ({html.escape(host)}) quer acessar o cérebro da Realmak "
        "em seu nome. Só continue se foi você que clicou em Connect.</p>"
        f"{aviso}{'<hr>'.join(partes) or '<p class=\"err\">Nenhuma forma de login está configurada.</p>'}"
    )


def _code_html(etxn: str, email: str, erro: str = "") -> str:
    aviso = f'<p class="err">{html.escape(erro)}</p>' if erro else ""
    return _shell(
        "<h1>Digite o código</h1>"
        f"<p>Se {html.escape(email)} tiver acesso ao cérebro, enviamos um código de 6 dígitos. Ele vale por 10 minutos.</p>"
        f'{aviso}<form method="post" action="{BASE}/login/email/verify">'
        f'<input type="hidden" name="etxn" value="{html.escape(etxn)}">'
        '<label for="cd">Código</label><input id="cd" name="code" inputmode="numeric" autocomplete="one-time-code" maxlength="8" required autofocus>'
        "<button type=\"submit\">Conectar</button></form>"
    )
