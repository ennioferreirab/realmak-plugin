---
name: gerar-visao-fluxo
description: "Use ao alterar definições, skills ou critérios de um agente Realmak que afetem sua aba Fluxo no CRM. Atualiza as notas, regenera visao.json e confere a saída com o contrato v1."
---

# Atualizar a visão de fluxo

1. Abra `agentes/<agente>/fluxo.json`, `agente.json`, `AGENTS.md`, `GESTOR.md` quando existir e as skills dos itens afetados. Confira saídas, dependências, tolerância a falha, tiers e decisões.
2. Atualize `agentes/<agente>/visao-notas.json`. Cada etapa executável precisa de descrição e grupos que cubram seus itens uma vez. Cada item precisa de resumo e lista de restrições. Cada portão precisa de critérios e texto para cada decisão vigente. Use as regras implantadas e deixe os limites configuráveis do daemon para o CRM exibir a partir da configuração real.
3. Para agente de chat sem `fluxo.json`, descreva as operações sob demanda em `etapas_descritivas`. A visão terá grupos vazios e hash de fluxo nulo.
4. Na raiz, execute `uv run --locked python scripts/gerar_visao_fluxo.py` e depois acrescente `--check` ao mesmo comando para conferir. Versione as notas e os arquivos `visao.json` gerados juntos. Ao mudar a versão do plugin, regenere também as visões.
