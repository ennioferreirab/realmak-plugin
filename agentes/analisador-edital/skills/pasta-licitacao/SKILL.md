---
name: pasta-licitacao
description: Localiza manifesto, textos e originais de uma licitação por `licitacao_id` e diz onde gravar a saída. Referência de todas as skills; não é item do fluxo (o script `resumo_conlicitacao.py` é o item `resumo`).
---

# Pasta da licitação

## Entradas
- `licitacao_id` (ID numérico do ConLicitação, ex.: `19478221`, ou chave da fonte externa, ex.: `pncp-02292266000180-1-000164-2026`). Documento que não veio do CRM (ex.: edital por e-mail): registre a origem em `analise/edital.json` (`documentos[].origem`).
- Parâmetros (AGENTS §2): `pasta_licitacoes`, `nome_agente`, `crm_resumo`.

## Referências
`<pasta_licitacoes>/<licitacao_id>/manifesto.json` é o índice. Campos com cuidado:

| Campo | Cuidado |
|---|---|
| `metadados.objeto`, `valor_estimado`, `datahora_prazo` | Não são confirmação; conferir no edital (sessão também no PNCP) |
| `metadados.edital` | Número do boletim, não o oficial |
| `metadados.item` | CATMAT do edital, pode estar errado |
| `anexos[].extraidos[]` | Texto em `extraidos/<caminho>`; original em `<caminho_documento>`; `status` e `paginas_nao_extraidas` |

ConLicitação `/biddings/{id}.json`: itens com quantidade e valor estimado ([PERFIL](../../referencias/conlicitacao/PERFIL.md) §3).

## Passos
1. **Manifesto.** Sem `manifesto.json` ou sem `anexos[].extraidos[]`: diga em `nao_lido` da análise do edital ("licitação sem manifesto", "edital sem texto extraído: pedir processamento no CRM").
2. **Resumo IA:** `python3 scripts/resumo_conlicitacao.py <licitacao_id>` devolve o `arquivo` que as skills leem. `sem_resumo` ou falha: segue pelo edital, sem pendência. É sugestão externa: campo usado como fato precisa do trecho no edital; juízos do resumo são refeitos, nunca copiados.
3. **Mapa de leitura:** no fluxo, reutilize `fontes/mapa_leitura.json` do item `mapa` (E0). Fora do fluxo ou após documento novo: `python3 ../guia-leitura-edital/scripts/localizar.py <licitacao_id>`.
4. **Textos:** pela lista de `anexos[].extraidos[]`. Não varrer pastas. Extração incompleta vai em `nao_lido` só quando compromete uma conclusão.
5. **Outros agentes** em `agents/`: só contexto; o fato vem do original.
6. **Gravar** só em `agents/<nome_agente>/`: `analise/` (os JSON do [contrato do card](../../referencias/card/CONTRATO.md) e as entregas das skills do plugin: HTML, planilhas, Markdown), `fontes/` (dados externos para reuso), `relatorio/` (score e decisões do gestor), `cotacao-fornecedor/` e `<skill>/` (auxiliares).

## Saída
Para as skills: metadados, textos, caminho do resumo e pasta de gravação. Esta skill não grava arquivo próprio.

## Limites
- Fora de `agents/<nome_agente>/`, a pasta é só leitura.
- Edital prevalece sobre manifesto e resumo IA.
- Em volume de rede no macOS, apague os `._*` criados nas subpastas de saída.

Decisões: [referencias/DECISOES.md](referencias/DECISOES.md).
