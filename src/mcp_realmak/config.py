"""Configuração lida só de variáveis de ambiente. Nada é gravado no repositório."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_CONLICITACAO_URL = "https://consultaonline.conlicitacao.com.br"
DEFAULT_SESSION_FILE = "/data/conlicitacao-sessao.json"
MAX_RESULT_CHARS = 100_000


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _int_env(name: str, default: int) -> int:
    raw = _env(name)
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


@dataclass(frozen=True)
class Settings:
    galeed_api_url: str
    galeed_timeout_s: float
    token_cache_ttl_s: int
    conlicitacao_url: str
    conlicitacao_token: str
    conlicitacao_login: str
    conlicitacao_site_password: str
    conlicitacao_session_file: str
    max_result_chars: int
    oauth_public_url: str = ""
    oauth_secret: str = ""
    oauth_redirect_hosts: tuple[str, ...] = ()
    galeed_service_key: str = ""
    galeed_login_url: str = ""
    google_client_id: str = ""
    google_client_secret: str = ""
    google_domain: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    odoo_mcp_url: str = ""
    odoo_mcp_secret: str = ""
    odoo_mcp_secret_file: str = ""
    odoo_timeout_s: float = 60.0
    arquivo_max_bytes: int = 50 * 1024 * 1024

    @property
    def licitacao_configured(self) -> bool:
        """Ferramentas de licitação: URL interna do Odoo e segredo (valor ou arquivo)."""
        return bool(self.odoo_mcp_url and (self.odoo_mcp_secret or self.odoo_mcp_secret_file))

    def odoo_secret(self) -> str:
        """Segredo das rotas internas do Odoo. O arquivo vem do volume que o Odoo cria; lido a cada uso."""
        if self.odoo_mcp_secret:
            return self.odoo_mcp_secret
        if not self.odoo_mcp_secret_file:
            return ""
        try:
            with open(self.odoo_mcp_secret_file, encoding="ascii") as origem:
                return origem.read().strip()
        except (OSError, UnicodeError):
            return ""

    @property
    def google_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_from)

    @property
    def oauth_configured(self) -> bool:
        """Login de pessoa: URL pública, segredo, chave de serviço e ao menos uma forma de login."""
        return (
            bool(self.oauth_public_url)
            and len(self.oauth_secret) >= 32
            and bool(self.galeed_service_key)
            and (self.google_configured or bool(self.galeed_login_url) or self.smtp_configured)
        )

    @property
    def galeed_configured(self) -> bool:
        return bool(self.galeed_api_url)


def load_settings() -> Settings:
    """Lê o ambiente a cada chamada, o que facilita os testes."""
    return Settings(
        galeed_api_url=_env("GALEED_API_URL").rstrip("/"),
        galeed_timeout_s=_int_env("GALEED_TIMEOUT_MS", 30_000) / 1000,
        token_cache_ttl_s=_int_env("MCP_REALMAK_TOKEN_CACHE_SECONDS", 300),
        conlicitacao_url=(_env("CONLICITACAO_URL") or DEFAULT_CONLICITACAO_URL).rstrip("/"),
        conlicitacao_token=_env("CONLICITACAO_TOKEN"),
        conlicitacao_login=_env("CONLICITACAO_LOGIN"),
        conlicitacao_site_password=_env("CONLICITACAO_SITE_PASSWORD"),
        conlicitacao_session_file=_env("CONLICITACAO_SESSION_FILE") or DEFAULT_SESSION_FILE,
        max_result_chars=_int_env("MCP_REALMAK_MAX_RESULT_CHARS", MAX_RESULT_CHARS),
        oauth_public_url=_env("MCP_REALMAK_PUBLIC_URL").rstrip("/"),
        oauth_secret=_env("MCP_REALMAK_OAUTH_SECRET"),
        oauth_redirect_hosts=tuple(h for h in _env("MCP_REALMAK_OAUTH_REDIRECT_HOSTS").split(",") if h.strip()),
        galeed_service_key=_env("GALEED_SERVICE_KEY"),
        galeed_login_url=_env("GALEED_LOGIN_URL").rstrip("/"),
        google_client_id=_env("GOOGLE_CLIENT_ID"),
        google_client_secret=_env("GOOGLE_CLIENT_SECRET"),
        google_domain=_env("GOOGLE_WORKSPACE_DOMAIN").lower(),
        smtp_host=_env("SMTP_HOST"),
        smtp_port=_int_env("SMTP_PORT", 587),
        smtp_user=_env("SMTP_USER"),
        smtp_password=_env("SMTP_PASSWORD"),
        smtp_from=_env("SMTP_FROM"),
        odoo_mcp_url=_env("ODOO_MCP_URL").rstrip("/"),
        odoo_mcp_secret=_env("ODOO_MCP_SECRET"),
        odoo_mcp_secret_file=_env("ODOO_MCP_SECRET_FILE"),
        odoo_timeout_s=_int_env("ODOO_MCP_TIMEOUT_MS", 60_000) / 1000,
        arquivo_max_bytes=_int_env("MCP_REALMAK_ARQUIVO_MAX_MB", 50) * 1024 * 1024,
    )
