"""Fornecedor sub-server — contratos de um CNPJ cruzando as fontes.

This file only registers components. Zero business logic (ADR-001 rule #4).
"""

from fastmcp import FastMCP

from .tools import contratos_vigentes_por_cnpj

mcp = FastMCP("fornecedor")

mcp.tool(contratos_vigentes_por_cnpj, tags={"contratos", "fornecedores", "compras", "cnpj"})
