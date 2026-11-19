---
name: guia-leitura-edital
description: Localiza cada informação nos textos do edital (documento, ordem e página) e grava o mapa que as skills leem antes do edital. Roda na preparação ou após documento novo.
---

# Guia de leitura do edital

## Entradas
- `licitacao_id`. Sem texto extraído: registre a lacuna (pasta-licitacao).
- Parâmetros (AGENTS §2): `pasta_licitacoes`, `nome_agente`, `crm_resumo.container`.
- [referencias/catalogo.json](referencias/catalogo.json): fonte única da ordem de leitura e dos termos. [ONDE-ESTA.md](referencias/ONDE-ESTA.md) é gerado dele; não editar.
- Tipo de documento do CRM (`edital`, `termo_referencia`, `estudo_tecnico_preliminar`, `minuta_contrato`, `planilha_precos`, `outros`): lido do início do documento; confirme pelo conteúdo. Resumo IA: só índice.

## Passos
1. Gere `agents/<nome_agente>/fontes/mapa_leitura.json` com `python3 scripts/localizar.py <licitacao_id>`: documentos (tipo, origem do tipo, páginas não extraídas, TR embutido) e, por informação, ordem de leitura e até 4 achados.
2. Leia o item completo nas páginas dos achados. Sem achado, siga o catálogo e sinônimos; busca vazia não prova ausência.
3. Confira páginas não extraídas antes de concluir "edital não exige". Na dúvida, ❓.
4. Conflito entre documentos: cite os dois, ⚠️, e aplique a precedência do edital; sem regra, edital sobre anexos e a divergência vira ponto de esclarecimento.
5. Informação sempre fora da ordem: ajuste `ordem` no catálogo, registre em DECISOES e rode `localizar.py --guia`.

## Saída
- `mapa_leitura.json` para as skills; não vai ao relatório.
- `analisar-edital` lista os documentos (`documentos[]`) e o TR embutido; aviso de tipo só se a leitura não confirmou.

## Limites
- Achado é ocorrência do termo, não conclusão.
- Planilha chega sem cabeçalho: confira números no original.
- CRM somente `SELECT`.

Decisões: [referencias/DECISOES.md](referencias/DECISOES.md).
