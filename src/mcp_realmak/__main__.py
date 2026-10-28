"""Ponto de entrada: sobe o servidor HTTP com o uvicorn."""

from __future__ import annotations

import logging
import os


def main() -> None:
    import uvicorn

    from .server import build_app

    logging.basicConfig(
        level=os.environ.get("MCP_REALMAK_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    host = os.environ.get("MCP_REALMAK_HOST", "127.0.0.1")
    port = int(os.environ.get("MCP_REALMAK_PORT", "8095"))
    # O uvicorn não loga cabeçalhos; o log de acesso fica desligado por precaução.
    uvicorn.run(
        build_app(),
        host=host,
        port=port,
        access_log=False,
        proxy_headers=True,
        forwarded_allow_ips=os.environ.get("MCP_REALMAK_FORWARDED_ALLOW_IPS", "127.0.0.1"),
    )


if __name__ == "__main__":
    main()
