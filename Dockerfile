# syntax=docker/dockerfile:1
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.9.24 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    MCP_REALMAK_HOST=0.0.0.0 \
    MCP_REALMAK_PORT=8095 \
    CONLICITACAO_SESSION_FILE=/data/conlicitacao-sessao.json
RUN useradd --system --uid 10001 --create-home --home-dir /home/app app \
    && mkdir -p /data && chown app:app /data
COPY --from=build --chown=app:app /app /app
WORKDIR /app
USER app
VOLUME ["/data"]
EXPOSE 8095
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8095/healthz', timeout=3).status == 200 else 1)"
CMD ["python", "-m", "mcp_realmak"]
