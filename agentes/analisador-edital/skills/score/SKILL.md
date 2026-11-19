---
name: score
description: Regras do score 0–100 e da nota 1–5, calculados só por `scripts/score.py` (T0) a partir de `analise/habilitacao.json`, `tecnica.json`, `precificacao.json` e da sessão em `edital.json`. O score responde "vale analisar?". Ler para entender ou mudar a conta.
---

# Score

## Execução
`python3 skills/score/scripts/score.py <licitacao_id>`; no fluxo, item `score`, com `--dados <pasta do agente>`. Grava só `relatorio/topo.json`, que o daemon lê para o Score IA do card.

## Conta
Três perguntas, pontos em `score.pontos` (AGENTS §2). Não precisa ser exato; falta de dado dá pontos parciais, nunca zero.

| Pergunta (chave) | Pontos |
|---|---|
| **Podemos participar?** (`triagem`, 30) | Aderência da `mais_aderente` em `habilitacao.json`: alta 100%, média 75%, baixa 40%, não atende 0. Sem habilitação: metade. |
| **Dá para executar?** (`lote`, 30) | `tecnica.json.conclusao.viavel`: sim 100%, com ressalvas 2/3, não 0. Sem conclusão: 1/3. |
| **Dá lucro?** (`margem`, 40) | `precificacao.json`: inexequível 0; `margem_pct` ≥ `precificacao.margem_minima_pct` 100%; entre 0 e a mínima, metade; negativa 0. Sem margem ou sem precificação: 1/4. |

## Nota 1–5
1. Trava (sessão em menos de `dias_minimos_preparo` dias corridos; todas as empresas avaliadas `nao_atende`; análise técnica `nao`; preço inexequível): score até 20, nota 1.
2. Sem margem calculada e com execução possível: nota 3, Inconclusivo. O score continua visível.
3. Senão, `score.faixas_nota`: 0–29 → 1 · 30–54 → 2 · 55–74 → 4 · 75–100 → 5.

## Saída
`relatorio/topo.json`: `score` (número), `nota`, `rotulo`, `termos[]` {`rotulo`, `pontos`, `maximo`, `motivo`}, `trava`, `avisos`, `hipotese_precificacao`, `tip_score`. Não é chance de vencer.

## Limites
- O script só calcula; não reavalia conteúdo. Nenhuma skill grava score.
- Mudança de pontos ou regra: DECISOES antes de valer.

Decisões: [referencias/DECISOES.md](referencias/DECISOES.md).
