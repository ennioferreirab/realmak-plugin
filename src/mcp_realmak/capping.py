"""Limite de tamanho dos resultados das ferramentas (cerca de 100 mil caracteres)."""

from __future__ import annotations

import json
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.tools import ToolResult
from mcp import types as mt

from .config import MAX_RESULT_CHARS

AVISO = (
    "\n\n[Resultado cortado em {limite} caracteres (tinha {total}). "
    "Refine o filtro ou use a paginação para ver o restante.]"
)


def cap_text(text: str, limit: int = MAX_RESULT_CHARS) -> str:
    """Corta o texto no limite e acrescenta um aviso em português."""
    if len(text) <= limit:
        return text
    return text[:limit] + AVISO.format(limite=limit, total=len(text))


def dumps(obj: Any, limit: int = MAX_RESULT_CHARS) -> str:
    """JSON legível (UTF-8) com corte de tamanho."""
    return cap_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), limit)


class ResultCapMiddleware(Middleware):
    """Garante o teto de tamanho em qualquer ferramenta, inclusive as de compras."""

    def __init__(self, limit: int = MAX_RESULT_CHARS) -> None:
        self.limit = limit

    async def on_call_tool(self, context: MiddlewareContext[mt.CallToolRequestParams], call_next):
        result: ToolResult = await call_next(context)
        for block in result.content:
            if isinstance(block, mt.TextContent) and len(block.text) > self.limit:
                block.text = cap_text(block.text, self.limit)
        structured = result.structured_content
        if structured is not None:
            size = len(json.dumps(structured, ensure_ascii=False, default=str))
            if size > self.limit:
                # O texto cortado já vai no conteúdo; o estruturado inteiro estouraria o teto.
                result.structured_content = None
        return result
