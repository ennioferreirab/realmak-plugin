---
name: analise-tecnica
description: Item `tecnica` (E2). Lê `cabecalho.tipo_objeto` de `analise/edital.json` e segue a skill certa — analisar-edital-manutencao ou analisar-edital-fornecimento — gravando `analise/tecnica.json`. Existe porque o fluxo não escolhe skill por campo de arquivo.
---

# Análise técnica

## Entradas
- `analise/edital.json` (item `edital`, E1): `cabecalho.tipo_objeto`, `atencao`, `habilitacao` (grupo `tecnica`).
- `analise/habilitacao.json` (item `habilitacao`, E2) e, quando necessário, os parciais em `analise/habilitacao/<alias>.json`: atestados, CATs e provas técnicas já validados.
- Pasta da licitação ([pasta-licitacao](../pasta-licitacao/SKILL.md)).

## Passos
1. Leia `analise/habilitacao.json` (e os parciais aplicáveis) para herdar explicitamente os atestados e CATs validados da(s) empresa(s) avaliada(s). Nunca contradiga a habilitação (por exemplo, não afirme limite inferior de capacidade/TR quando uma CAT ou atestado validado em `habilitacao.json` comprovar capacidade superior).
2. Leia `cabecalho.tipo_objeto` e escolha:

   | `tipo_objeto` | Siga |
   |---|---|
   | `manutencao` | [analisar-edital-manutencao](../../../../plugins/realmak/skills/analisar-edital-manutencao/SKILL.md) |
   | `fornecimento` | [analisar-edital-fornecimento](../../../../plugins/realmak/skills/analisar-edital-fornecimento/SKILL.md) |
   | `misto` | Manutenção que inclui peças: só a de manutenção. Bens com contrato de manutenção no mesmo edital: as duas, num único `tecnica.json` com `tipo` do objeto de maior valor; os itens de bens em `itens[]` e o serviço em `escopo`, `equipe` e `sla` |
   | `outro_servico` | A de manutenção, só os passos que fizerem sentido (escopo, equipe, SLA, conclusão); o que não se aplicar fica com lista vazia |
   | ausente ou `edital.json` sem texto | Confira o objeto no edital e decida pela tabela; diga a escolha em `conclusao.resumo` |

2. Leia o SKILL.md escolhido por inteiro e faça os passos dele. É skill do realmak-plugin: siga o [AGENTS.md §7](../../AGENTS.md#skills-do-realmak-plugin) para onde ler os documentos e gravar as entregas (pasta do processo = `analise/`; nada na conversa).
3. Grave `analise/tecnica.json` no [contrato do card](../../referencias/card/CONTRATO.md), com `arquivos` listando os HTML da skill (`analise/analise-fornecimento.html`; na manutenção, o painel `analise/analise-manutencao.html` primeiro e o relatório de impressão `analise/analise-manutencao-relatorio.html`) e as planilhas `.xlsx`. Uma única `saida`.

## Limites
- Não repita o que a análise do edital já traz; parta dela.
- Não decide participação nem preço.

Decisões: [referencias/DECISOES.md](referencias/DECISOES.md).
