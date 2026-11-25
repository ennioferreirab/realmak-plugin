---
name: gerar-visao-fluxo
description: "Use ao alterar definições, skills ou critérios de um agente Realmak que afetem sua aba Fluxo no CRM. Atualiza as notas, regenera visao.json e confere a saída com o contrato v1 (Cartões e Canvas)."
---

# Atualizar a visão de fluxo

1. Abra `agentes/<agente>/fluxo.json`, `agente.json`, `AGENTS.md`, `GESTOR.md` quando existir e as skills dos itens afetados. Confira saídas, dependências, tolerância a falha, tiers e decisões.
2. Atualize `agentes/<agente>/visao-notas.json` seguindo o contrato retrocompatível `versao: 1`:
   - **Cada etapa:** `objetivo` (1 frase direta), `criterios` (lista curta de critérios objetivos), `descricao` e `grupos` cobrindo cada item da etapa exatamente uma vez.
   - **Cada item:** `objetivo` (1 frase direta), `criterios` (lista curta de critérios objetivos), `resumo` e `restricoes`. O script descobre deterministicamente `skill_origem` (`"agente" | "plugin" | null`), `skill_caminho` (caminho relativo ao `SKILL.md`) e `skill_arquivos` (arquivos legíveis da pasta da skill).
   - **Cada portão:** `objetivo` (1 frase direta), `criterios` e `decisoes` com `quando` e `destino` (`"proxima" | "parar" | "humano" | "rerodar" | "precos"`) para cada decisão vigente, permitindo ao Canvas desenhar desvios corretamente.
   Use as regras implantadas e deixe os limites configuráveis do daemon para o CRM exibir a partir da configuração real.
3. Para agente de chat sem `fluxo.json`, descreva as operações sob demanda em `etapas_descritivas` com `id`, `titulo`, `objetivo`, `criterios` e `descricao`. A visão terá grupos vazios e hash de fluxo nulo.
4. Na raiz, execute `uv run --locked python scripts/gerar_visao_fluxo.py` e depois acrescente `--check` ao mesmo comando para conferir. Versione as notas e os arquivos `visao.json` gerados juntos. Ao mudar a versão do plugin, regenere também as visões.
