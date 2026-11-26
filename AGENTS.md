# AGENTS.md

Deploy do MCP e prévia no Stage: [DEPLOY.md](DEPLOY.md).

## PROJECT VISION

Vale para pessoas e agentes e prevalece sobre regras mais restritivas deste arquivo para Stage e desenvolvimento.

- A Realmak está em desenvolvimento, com poucos usuários. Prioridade: entregar funcionando para Ennio validar.
- Simplicidade e eficiência de desenvolvedor sênior: resolva na origem, com a solução mais simples. Toda configuração necessária fica no repositório e é aplicada pelo deploy normal; nada pode depender de passo manual no servidor.
- Stage e desenvolvimento: deploy rápido autorizado, inclusive direto na VPS, sem esperar etiquetas ou aprovação. Agentes podem aplicar `pronto` e `stage` e fazer merge na `main` para o Stage. Produção (`pd`) continua exigindo autorização de Ennio.
- Segurança proporcional à fase: aplique o que for barato. Se for custoso, entregue e registre a pendência no PR e em `PENDENCIAS-SEGURANCA.md` na raiz do repositório.
- Pronto é validado: depois de cada deploy, teste o fluxo afetado como o usuário usa (link, card, busca) antes de reportar. Merge, deploy e funcionando são estados diferentes.
- Corrija direto quando for mais rápido que delegar. Evite rodadas extras de revisão, pacotes de ensaio e relatórios intermediários.
- Melhoria contínua: pergunte a Ennio antes de iniciar ou prolongar um ciclo.

## Deploy no Stage

- No Stage (VPS, `/srv/mcp-realmak`, usuário `deploy`), implante só com `scripts/vps/deploy.sh`. `docker compose up` sem `compose.vps.yaml` tira o contêiner das redes `mcp-realmak` e `realmak-previa`, e `/mcp` público responde 502 (26/11/2026). O script confere as redes e o 401 de `/mcp`.
