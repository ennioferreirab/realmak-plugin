"""Acesso somente leitura ao site ConLicitação para exploração.

Uso (CLI):  python3 cl.py GET "/companies_activities"            -> imprime JSON (truncado)
            python3 cl.py GET "/mercado/get_biddings.json?x=1" --full
Uso (módulo): from cl import get_json

Regras:
- Somente GET. Qualquer outro método é recusado.
- Credenciais: CONLICITACAO_LOGIN e CONLICITACAO_SITE_PASSWORD do ambiente (container do daemon); fora dele,
  do .env indicado em `REALMAK_CRM_ENV`. Sem nenhum dos dois, falha. Nunca impressas.
- Login uma vez; cookie guardado em ~/.cache/agente-precificacao/ (chmod 600) e reaproveitado entre processos.
- Rotas com efeito colateral conhecido são bloqueadas (ver BLOQUEADAS).
"""
import http.cookiejar
import json
import os
import stat
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://consultaonline.conlicitacao.com.br"
ENV = Path(os.environ.get("REALMAK_CRM_ENV", ""))
HERE = Path(__file__).resolve().parent
COOKIES = Path.home() / ".cache" / "agente-precificacao" / "conlicitacao_cookies.txt"  # fora da pasta do agente
COOKIES.parent.mkdir(parents=True, exist_ok=True)
SESSION_COOKIE = "_boletim_web_session"
# GET que cria registro na conta (get-or-create): não chamar sem aprovação humana.
BLOQUEADAS = ("/chatbots/bidding_chat/bidding_user_chats",)


def _env() -> dict:
    if os.environ.get("CONLICITACAO_LOGIN") and os.environ.get("CONLICITACAO_SITE_PASSWORD"):
        return {k: os.environ[k] for k in ("CONLICITACAO_LOGIN", "CONLICITACAO_SITE_PASSWORD")}
    if str(ENV) == ".":  # Path("") sem REALMAK_CRM_ENV
        raise SystemExit("credenciais ausentes: defina CONLICITACAO_LOGIN/CONLICITACAO_SITE_PASSWORD ou REALMAK_CRM_ENV")
    vals = {}
    for line in ENV.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        vals[k.strip()] = v.strip().strip('"').strip("'")
    return vals


def _jar() -> http.cookiejar.LWPCookieJar:
    jar = http.cookiejar.LWPCookieJar(str(COOKIES))
    if COOKIES.exists():
        jar.load(ignore_discard=True, ignore_expires=True)
    return jar


def _opener(jar):
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def _save(jar):
    jar.save(ignore_discard=True, ignore_expires=True)
    os.chmod(COOKIES, stat.S_IRUSR | stat.S_IWUSR)


def login(jar=None):
    jar = jar or _jar()
    e = _env()
    body = json.dumps({"login": e["CONLICITACAO_LOGIN"], "senha": e["CONLICITACAO_SITE_PASSWORD"], "refresh": False}).encode()
    req = urllib.request.Request(
        f"{BASE}/users/login.json", data=body, method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "Origin": "https://consulteonline.conlicitacao.com.br", "Referer": "https://consulteonline.conlicitacao.com.br/"},
    )
    with _opener(jar).open(req, timeout=30) as r:
        data = json.loads(r.read().decode() or "{}")
    if not any(c.name == SESSION_COOKIE for c in jar):
        raise SystemExit("login sem cookie de sessão")
    _save(jar)
    # devolve só metadados não sensíveis
    return {k: data.get(k) for k in ("id", "empresa_autorizada_id", "nome") if isinstance(data, dict) and k in data}


def get_json(path: str, retry: bool = True, prazo: float | None = None):
    """Com prazo, limita login, renovação e leitura inteira em processo cancelável."""
    if prazo is not None:
        worker = (
            "import json, pathlib, runpy, sys; "
            "ns = runpy.run_path(sys.argv[1]); "
            "fn = ns['get_json']; "
            "fn.__globals__.update(BASE=sys.argv[2], ENV=pathlib.Path(sys.argv[3]), "
            "COOKIES=pathlib.Path(sys.argv[4])); "
            "print(json.dumps(fn(sys.stdin.read(), retry=sys.argv[5] == 'True')))"
        )
        result = subprocess.run(
            [sys.executable, "-c", worker, str(Path(__file__).resolve()),
             BASE, str(ENV), str(COOKIES), str(retry)],
            input=path, text=True, capture_output=True, timeout=prazo,
        )
        if result.returncode:
            raise ConnectionError("Falha ao consultar o ConLicitação")
        status, data = json.loads(result.stdout)
        return status, data
    if path.startswith(BLOQUEADAS):
        raise SystemExit(f"rota bloqueada (efeito colateral): {path}")
    jar = _jar()
    if not any(c.name == SESSION_COOKIE for c in jar):
        login(jar)
    req = urllib.request.Request(f"{BASE}{path}", method="GET", headers={
        "Accept": "application/json", "Origin": "https://consulteonline.conlicitacao.com.br",
        "Referer": "https://consulteonline.conlicitacao.com.br/"})
    try:
        with _opener(jar).open(req, timeout=60) as r:
            raw = r.read()
            _save(jar)
            try:
                return r.status, json.loads(raw.decode())
            except Exception:
                return r.status, raw.decode(errors="replace")[:2000]
    except urllib.error.HTTPError as err:
        if retry and err.code in (401, 403, 423):
            COOKIES.unlink(missing_ok=True)
            login()
            return get_json(path, retry=False)
        return err.code, err.read().decode(errors="replace")[:1000]


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1].upper() != "GET":
        raise SystemExit("uso: cl.py GET <path> [--full]   (somente GET)")
    status, data = get_json(sys.argv[2])
    out = json.dumps(data, ensure_ascii=False, indent=1) if not isinstance(data, str) else data
    print("HTTP", status)
    print(out if "--full" in sys.argv else out[:4000])
