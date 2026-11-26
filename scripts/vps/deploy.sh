#!/usr/bin/env bash
# Implanta o mcp-realmak no Stage (VPS). Use SEMPRE este script, no checkout /srv/mcp-realmak, como `deploy`.
# Motivo: `docker compose up` só com compose.yaml recria o contêiner fora das redes mcp-realmak e realmak-previa;
# a borda do CRM deixa de alcançá-lo e /mcp responde 502 (aconteceu duas vezes em 26/11/2026).
#   scripts/vps/deploy.sh            atualiza para o topo de origin/main e sobe
#   scripts/vps/deploy.sh --sem-git  só sobe o checkout atual
set -Eeuo pipefail
cd "$(dirname "$0")/../.."
[ "${1:-}" = "--sem-git" ] || git pull --ff-only -q
docker compose -f compose.yaml -f compose.vps.yaml up -d --build --wait
redes="$(docker inspect mcp-realmak --format '{{json .NetworkSettings.Networks}}')"
for rede in mcp-realmak realmak-previa; do
  case "$redes" in *"\"$rede\""*) ;; *) echo "ERRO: mcp-realmak fora da rede $rede" >&2; exit 1 ;; esac
done
publico="${MCP_REALMAK_PUBLIC_URL:-https://app.realmakservicos.com.br}"
codigo="$(curl -s -o /dev/null -w '%{http_code}' -m 20 -X POST -H 'content-type: application/json' "$publico/mcp" || true)"
[ "$codigo" = 401 ] || { echo "ERRO: $publico/mcp respondeu $codigo (esperado 401 sem credencial)" >&2; exit 1; }
if docker ps --format '{{.Names}}' | grep -qx 'realmak-crm-agentes-1'; then
  invalidos="$(docker exec -w /opt/realmak/agentes realmak-crm-agentes-1 node -e 'import("./src/manifesto.ts").then(m => { const c = new m.Catalogo("/agentes", "/plugin-realmak"); const inv = c.agentesInvalidos(); console.log(JSON.stringify(inv)); if (inv.length) process.exit(1); })')" || {
    echo "ERRO: realmak-crm-agentes-1 recusou manifesto(s): $invalidos" >&2
    exit 1
  }
fi
echo "==> mcp-realmak implantado: $(git log --oneline -1) · $publico/mcp ok (401 sem credencial) · catalogo ok"
