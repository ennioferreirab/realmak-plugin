"""Cliente do site do ConLicitação (login com cookie de sessão).

Porte assíncrono do ConlicitacaoSiteClient do CRM. Regras mantidas:
- só HTTPS (HTTP apenas em localhost, para teste);
- redirecionamento só para a mesma origem;
- login em POST /users/login.json, com o cookie _boletim_web_session;
- sessão vencida (401, 403 ou 423): novo login e uma repetição da consulta;
- um lock impede dois logins ao mesmo tempo quando várias ferramentas rodam juntas.

A sessão fica num arquivo do servidor (modo 0600), para sobreviver a reinícios.
Nada do que está aqui sai nas respostas das ferramentas.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import time
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx

from ..sanitize import mask_sensitive
from .errors import ConlicitacaoError

log = logging.getLogger("mcp_realmak.conlicitacao.site")

DEFAULT_ORIGIN = "https://consulteonline.conlicitacao.com.br"
SESSION_COOKIE = "_boletim_web_session"
MAX_BYTES = 10 * 1024 * 1024
LOCAL_HOSTS = ("127.0.0.1", "localhost")


class ConlicitacaoSiteClient:
    def __init__(
        self,
        base_url: str,
        login: str,
        password: str,
        session_file: str | None = None,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        parsed = urlsplit(self.base_url)
        if parsed.scheme.lower() not in ("https", "http"):
            raise ConlicitacaoError("Esquema de URL inválido para o ConLicitação.")
        if parsed.scheme.lower() == "http" and parsed.hostname not in LOCAL_HOSTS:
            raise ConlicitacaoError("O ConLicitação exige HTTPS.")
        local = parsed.hostname in LOCAL_HOSTS
        self._scheme = parsed.scheme.lower()
        self._netloc = parsed.netloc.lower()
        self._origin = self.base_url if local else DEFAULT_ORIGIN
        self._referer = f"{self._origin}/"
        self._login = login
        self._password = password
        self._session_file = Path(session_file) if session_file else None
        self._timeout = timeout
        self._transport = transport
        self._cookies = httpx.Cookies()
        self.empresa_id: int | None = None
        self._lock = asyncio.Lock()
        self._generation = 0
        self._loaded = False

    # --- sessão em disco -----------------------------------------------------

    def _has_session(self) -> bool:
        return any(c.name == SESSION_COOKIE and c.value for c in self._cookies.jar) and bool(
            self.empresa_id
        )

    def _load_session(self) -> None:
        self._loaded = True
        if not self._session_file or not self._session_file.is_file():
            return
        try:
            data = json.loads(self._session_file.read_text(encoding="utf-8"))
            now = time.time()
            for c in data.get("cookies", []):
                if c.get("expires") and c["expires"] < now:
                    continue
                self._cookies.set(
                    c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path", "/")
                )
            empresa = data.get("empresa_id")
            self.empresa_id = empresa if isinstance(empresa, int) and empresa > 0 else None
        except (OSError, ValueError, KeyError, TypeError):
            log.warning("Arquivo de sessão do ConLicitação ilegível; vai logar de novo.")
            self._cookies.clear()
            self.empresa_id = None

    def _save_session(self) -> None:
        if not self._session_file:
            return
        payload = {
            "empresa_id": self.empresa_id,
            "cookies": [
                {"name": c.name, "value": c.value, "domain": c.domain, "path": c.path, "expires": c.expires}
                for c in self._cookies.jar
            ],
        }
        try:
            self._session_file.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self._session_file.parent, prefix=".sessao-")
            try:
                os.fchmod(fd, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(payload, fh)
                os.replace(tmp, self._session_file)
            except BaseException:
                Path(tmp).unlink(missing_ok=True)
                raise
        except OSError:
            log.warning("Não foi possível gravar o arquivo de sessão do ConLicitação.")

    def _clear_session(self) -> None:
        self._cookies.clear()
        self.empresa_id = None
        if self._session_file:
            self._session_file.unlink(missing_ok=True)

    # --- HTTP ------------------------------------------------------------------

    async def _send(
        self, method: str, path_or_url: str, *, json_body: dict | None = None, headers: dict | None = None
    ) -> httpx.Response:
        url = path_or_url if path_or_url.startswith("http") else f"{self.base_url}{path_or_url}"
        async with httpx.AsyncClient(
            timeout=self._timeout, transport=self._transport, cookies=self._cookies, follow_redirects=False
        ) as client:
            for _ in range(4):
                resp = await client.request(method, url, json=json_body, headers=headers)
                if resp.status_code in (301, 302, 303, 307, 308) and "location" in resp.headers:
                    target = urljoin(url, resp.headers["location"])
                    destino = urlsplit(target)
                    if destino.scheme.lower() != self._scheme or destino.netloc.lower() != self._netloc:
                        raise ConlicitacaoError("Redirecionamento bloqueado: origem diferente da autorizada.")
                    url = target
                    if resp.status_code in (301, 302, 303):
                        method, json_body = "GET", None
                    continue
                self._cookies = client.cookies
                return resp
        raise ConlicitacaoError("Redirecionamentos demais no ConLicitação.")

    async def _do_login(self) -> None:
        if not self._login or not self._password:
            raise ConlicitacaoError(
                "As credenciais do site do ConLicitação não estão configuradas no servidor."
            )
        self._cookies.clear()
        try:
            resp = await self._send(
                "POST",
                "/users/login.json",
                json_body={"login": self._login, "senha": self._password, "refresh": False},
                headers={
                    "Accept": "application/json",
                    "frontend": "true",
                    "Origin": self._origin,
                    "Referer": self._referer,
                },
            )
        except httpx.HTTPError as exc:
            log.warning("Falha de conexão no login do ConLicitação: %s", type(exc).__name__)
            raise ConlicitacaoError("Falha de conexão com o ConLicitação ao autenticar.") from None
        if resp.status_code != 200:
            self._clear_session()
            log.warning("Login no ConLicitação recusado: HTTP %s", resp.status_code)
            raise ConlicitacaoError(
                "O ConLicitação recusou o login (credenciais erradas ou serviço indisponível). "
                "Avise quem administra o servidor."
            )
        try:
            company = resp.json().get("user", {}).get("client_id")
        except (ValueError, AttributeError):
            company = None
        if isinstance(company, str) and company.isdecimal():
            company = int(company)
        if type(company) is not int or company <= 0:
            self._clear_session()
            raise ConlicitacaoError("O login no ConLicitação não informou a empresa da sessão.")
        self.empresa_id = company
        if not any(c.name == SESSION_COOKIE and c.value for c in self._cookies.jar):
            self._clear_session()
            raise ConlicitacaoError("O login no ConLicitação não devolveu o cookie de sessão.")
        self._generation += 1
        self._save_session()

    async def _ensure_session(self) -> None:
        async with self._lock:
            if not self._loaded:
                self._load_session()
            if not self._has_session():
                await self._do_login()

    async def _relogin(self, seen_generation: int) -> None:
        async with self._lock:
            if self._generation != seen_generation:
                return  # outra chamada já renovou a sessão
            self._clear_session()
            await self._do_login()

    async def get_json(self, path: str) -> dict:
        """GET autenticado que devolve um objeto JSON; renova a sessão uma vez se vencer."""
        await self._ensure_session()
        for attempt in range(2):
            generation = self._generation
            try:
                resp = await self._send("GET", path, headers={"Accept": "application/json"})
            except httpx.HTTPError as exc:
                log.warning("Falha de comunicação com o ConLicitação: %s", type(exc).__name__)
                raise ConlicitacaoError("Falha de comunicação com o ConLicitação.") from None
            if resp.status_code in (401, 403, 423):
                if attempt == 0:
                    await self._relogin(generation)
                    continue
                raise ConlicitacaoError(
                    f"O ConLicitação recusou a consulta mesmo após novo login (HTTP {resp.status_code})."
                )
            if resp.status_code == 204:
                return {}
            if resp.status_code != 200:
                raise ConlicitacaoError(f"Falha ao consultar o ConLicitação (HTTP {resp.status_code}).")
            if len(resp.content) > MAX_BYTES:
                raise ConlicitacaoError("Resposta do ConLicitação grande demais.")
            try:
                data = resp.json()
            except ValueError:
                raise ConlicitacaoError("Resposta do ConLicitação não é JSON válido.") from None
            if not isinstance(data, dict):
                raise ConlicitacaoError("Resposta do ConLicitação com estrutura inesperada.")
            self._save_session()
            return data
        raise ConlicitacaoError("Falha ao consultar o ConLicitação.")  # pragma: no cover

    # --- consultas -------------------------------------------------------------

    async def buscar(self, filtros: list[tuple[str, str | int]], pagina: int = 1) -> dict:
        from urllib.parse import urlencode

        await self._ensure_session()
        query: list[tuple[str, str | int]] = [("companyId", self.empresa_id or 0)]
        query.extend(filtros)
        query.append(("page", pagina))
        return await self.get_json("/biddings.json?" + urlencode(query))

    async def obter_licitacao(self, licitacao_id: int) -> dict:
        _validar_id(licitacao_id)
        data = await self.get_json(f"/biddings/{licitacao_id}.json")
        if data.get("id") != licitacao_id:
            raise ConlicitacaoError("A resposta do ConLicitação não é da licitação pedida.")
        return data

    async def obter_resumo(self, licitacao_id: int) -> dict | None:
        _validar_id(licitacao_id)
        data = await self.get_json(
            f"/chatbots/bidding_chat/bidding_summary?conlicitacao_id={licitacao_id}"
        )
        summary = data.get("summary")
        return summary if isinstance(summary, dict) and summary else None


def _validar_id(licitacao_id: int) -> None:
    if type(licitacao_id) is not int or not (0 < licitacao_id <= 2_147_483_647):
        raise ConlicitacaoError("ID de licitação inválido: use um número inteiro positivo.")


def safe_error(exc: Exception) -> str:
    return mask_sensitive(exc)
