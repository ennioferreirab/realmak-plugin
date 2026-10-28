"""Exceções do módulo de compras (adaptado do mcp-brasil, MIT)."""


class McpBrasilError(Exception):
    """Exceção base."""


class HttpClientError(McpBrasilError):
    """Erro de comunicação HTTP com API externa."""
