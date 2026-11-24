# Pendências de segurança

Itens custosos adiados na fase de desenvolvimento (PROJECT VISION). Cada item: risco, mitigação atual e o que falta.

## Links curtos únicos (`/a/<codigo>`), 24/11/2026

- **Acesso sem login e sem rate limit por IP:** `GET /a/<codigo>` atende sem sessão nem limitação de taxa na borda/MCP, como nos links legados `/mcp/arquivos/...`. Mitigado por código aleatório de 9 caracteres base62 gerado com `secrets`, TTL de 30 minutos, limpeza automática dos vencidos, auditoria em `acessos_links` e validação de escopo na origem (Odoo/Galeed) a cada leitura. Falta adicionar rate limit por IP na borda/MCP se o tráfego crescer.
- **Retenção de metadados em `acessos_links`:** `/data/links.sqlite` (permissão `0600` no volume persistente `/data`) retém e-mail, IP e User-Agent dos acessos por 30 dias para rastreabilidade. Falta política formal de expurgo/anonimização caso haja exigência regulatória adicional.
