"""Armazenamento SQLite de links curtos (`/a/<codigo>`) e registro de acessos.

Fica no mesmo volume persistente do servidor (`/data/links.sqlite` por padrão) para
sobreviver a reinícios sem depender de serviço externo. Tokens vencidos e acessos
antigos são limpos automaticamente.
"""

from __future__ import annotations

import logging
import os
import re
import secrets
import sqlite3
import threading
import time
from contextlib import closing, suppress
from dataclasses import dataclass
from pathlib import Path

from ..config import Settings

log = logging.getLogger("mcp_realmak.licitacao")

ALFABETO = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
TAMANHO_CODIGO = 9
CODIGO_RE = re.compile(r"^[0-9A-Za-z]{8,12}$")
RETENCAO_ACESSOS_S = 30 * 24 * 3600

_lock = threading.Lock()
_inicializados: set[Path] = set()


@dataclass(frozen=True)
class RegistroLink:
    codigo: str
    tipo: str
    token: str
    criado_por: str
    nome: str
    criado_em: int
    expira_em: int


def caminho_banco(settings: Settings) -> Path:
    if settings.links_db_path:
        return Path(settings.links_db_path)
    return Path(settings.conlicitacao_session_file).parent / "links.sqlite"


def _conectar(caminho: Path) -> sqlite3.Connection:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    novo = not caminho.exists()
    conn = sqlite3.connect(str(caminho), timeout=5.0)
    if novo:
        with suppress(OSError):
            os.chmod(caminho, 0o600)
    if novo or caminho not in _inicializados:
        with suppress(sqlite3.OperationalError):
            conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS links_curtos (
                codigo TEXT PRIMARY KEY,
                tipo TEXT NOT NULL,
                token TEXT NOT NULL,
                criado_por TEXT NOT NULL,
                nome TEXT NOT NULL DEFAULT '',
                criado_em INTEGER NOT NULL,
                expira_em INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_links_curtos_expira ON links_curtos(expira_em);

            CREATE TABLE IF NOT EXISTS acessos_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT NOT NULL,
                tipo TEXT NOT NULL,
                email TEXT NOT NULL,
                modo TEXT NOT NULL,
                ip TEXT NOT NULL,
                user_agent TEXT NOT NULL,
                status INTEGER NOT NULL,
                aberto_em INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_acessos_links_codigo ON acessos_links(codigo);
            CREATE INDEX IF NOT EXISTS idx_acessos_links_aberto ON acessos_links(aberto_em);
            """
        )
        _inicializados.add(caminho)
    return conn


def limpar_vencidos(conn: sqlite3.Connection, agora: int) -> None:
    conn.execute("DELETE FROM links_curtos WHERE expira_em < ?", (agora,))
    conn.execute("DELETE FROM acessos_links WHERE aberto_em < ?", (agora - RETENCAO_ACESSOS_S,))


def criar(
    settings: Settings,
    *,
    tipo: str,
    token: str,
    email: str,
    expira_em: int,
    nome: str = "",
    agora: int | None = None,
) -> str:
    """Grava o token com validade e devolve um código curto aleatório (9 chars base62)."""
    instante = int(time.time()) if agora is None else agora
    caminho = caminho_banco(settings)
    with _lock, closing(_conectar(caminho)) as conn, conn:
        limpar_vencidos(conn, instante)
        for _ in range(5):
            codigo = "".join(secrets.choice(ALFABETO) for _ in range(TAMANHO_CODIGO))
            try:
                conn.execute(
                    "INSERT INTO links_curtos (codigo, tipo, token, criado_por, nome, criado_em, expira_em) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (codigo, tipo, token, email, nome[:200], instante, expira_em),
                )
                return codigo
            except sqlite3.IntegrityError:
                continue
    raise RuntimeError("Não foi possível gerar um código curto único.")


def buscar(settings: Settings, codigo: str, agora: int | None = None) -> RegistroLink | None:
    """Recupera um link curto válido; se estiver vencido, remove e retorna None."""
    if not CODIGO_RE.fullmatch(codigo):
        return None
    instante = int(time.time()) if agora is None else agora
    caminho = caminho_banco(settings)
    if not caminho.exists():
        return None
    with _lock, closing(_conectar(caminho)) as conn, conn:
        row = conn.execute(
            "SELECT codigo, tipo, token, criado_por, nome, criado_em, expira_em "
            "FROM links_curtos WHERE codigo = ?",
            (codigo,),
        ).fetchone()
        if row is None:
            return None
        registro = RegistroLink(*row)
        if registro.expira_em < instante:
            conn.execute("DELETE FROM links_curtos WHERE codigo = ?", (codigo,))
            return None
        return registro


def registrar_acesso(
    settings: Settings,
    *,
    codigo: str,
    tipo: str,
    email: str,
    modo: str,
    ip: str,
    user_agent: str,
    status: int,
    agora: int | None = None,
) -> None:
    """Registra quem abriu um link curto, quando, em qual modo e com qual status HTTP."""
    instante = int(time.time()) if agora is None else agora
    caminho = caminho_banco(settings)
    try:
        with _lock, closing(_conectar(caminho)) as conn, conn:
            conn.execute(
                "INSERT INTO acessos_links (codigo, tipo, email, modo, ip, user_agent, status, aberto_em) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (codigo, tipo, email, modo, ip[:64], user_agent[:300], status, instante),
            )
    except sqlite3.Error:
        log.warning("Falha ao registrar acesso ao link curto %s", codigo)
