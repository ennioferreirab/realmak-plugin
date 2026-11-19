---
name: cotacao-fornecedor
description: Só quando o analista pede no card (botão "Pesquisar fornecedores e gerar e-mails"): pesquisa fornecedores na internet (fabricante primeiro) e redige um e-mail de cotação por fornecedor, enviados pelo carteiro depois da aprovação. Na leitura de resposta, lê cada resposta e, se o preço não serve, redige contraproposta para aprovação. Não é item da análise.
---

# Cotação com fornecedor

## Modos e entradas
- Preparar pedidos (passos 1–6): roda só a pedido do analista, nunca no fluxo automático da análise (plano `2026-11-16-analise-edital-e-cotacao-sob-demanda.md`). Itens: os que o analista indicar; sem indicação, os itens e peças de `analise/tecnica.json` de maior valor, sem oferta online comparável. Custo pequeno com cotação online confiável dispensa pedido.
- Ler resposta (passo 7): toda resposta recebida é lida, qualquer que seja o custo.
- Entradas: `analise/tecnica.json` (itens, exigências, quantidade, entrega, `cotacoes_online`); `analise/edital.json` (pagamento, garantia, prazos); `analise/precificacao.json` (custo e margem, para a contraproposta); sem análise publicada, o edital e o TR da pasta. Respostas em `cotacao-fornecedor/respostas/<pedido>/`; na atualização, `fontes/antes-cotacao-<tarefa>.json`, quando existir.
- Parâmetros (AGENTS §2): `cotacao.*`, `precificacao.tributos_pct`, `precificacao.margem_minima_pct`.
- Sem lista cadastrada de fornecedores: a pesquisa parte do zero a cada pedido. Referências: [MODELO-PEDIDO](referencias/MODELO-PEDIDO.md), [MODELO-CONTRAPROPOSTA](referencias/MODELO-CONTRAPROPOSTA.md).

## Passos

1. **Itens:** especificação como no TR, quantidade, destino, prazo de entrega e o que o edital exige do fornecedor (carta de solidariedade, credenciamento, registro).
2. **Fornecedores:** pesquise com `buscar_web`, na ordem fabricante → representante oficial → distribuidor autorizado → revendedor: marca citada no edital, sites de fabricantes e suas listas de representantes, vencedores do item em atas e compras públicas, CNPJ/CNAE, vendedores das `cotacoes_online`, [cerebro](../../../../plugins/realmak/skills/cerebro/SKILL.md) (`fontes/cerebro.json`). Tipo e fonte comercial oficial de cada um, com o e-mail comercial publicado pelo próprio fornecedor.
3. **Quantidade:** `cotacao.regras_quantidade` é orientação; menos fornecedores não segura nada nem vira pendência. Grave `cotacao-fornecedor/fornecedores.json` (item, fornecedor, tipo, fonte).
4. **Pedido**, um por fornecedor, pelo modelo: melhor preço para o volume, quantidade total estimada (registro de preços: sem compromisso de compra mínima), faixas de volume, frete até o destino, pagamento do edital (`analise/edital.json`). Sem órgão nem licitação (`cotacao.sigilo_oportunidade`). Sem promessa de compra nem exclusividade.
5. **Data-limite:** o menor entre hoje + `cotacao.prazo_resposta_dias_uteis` dias úteis (mais um dia útil para a revisão no card) e a sessão − `cotacao.prazo_limite_dias_antes_sessao`.
6. **Gravar** em `agents/<nome_agente>/cotacao-fornecedor/` um `<itens>-<fornecedor>.md` por pedido, no formato do MODELO-PEDIDO:
   - id = nome sem `.md`: minúsculas, sem acento nem espaço, só letras, números e `-` (ex.: `1-7-lg-brasil`);
   - frontmatter `para` (e-mail comercial oficial), `assunto` entre aspas até 200 caracteres, `data_limite` `AAAA-MM-DD`, `estado: rascunho`; corpo em texto até 16 KB;
   - `pedidos.json`: `{"gerado_em": "<ISO-8601>", "pedidos": [{"id": "…", "fornecedor": "…", "tipo": "fabricante|representante|distribuidor|revendedor", "fonte": "…", "itens": ["rótulo curto"], "data_limite": "AAAA-MM-DD"}]}`. Acrescente aos pedidos que já estão lá; nunca apague nem altere um pedido anterior (pode já ter sido enviado).
   O daemon recusa saída fora do formato: corrija e grave de novo. O analista revisa, edita e envia pelo card; o Odoo envia pelo carteiro e recebe a resposta.
7. **Resposta recebida:**
   1. Extraia por item: preço unitário, quantidade base, faixas de volume, frete, prazo de entrega, validade, pagamento, impostos inclusos.
   2. Confira contra as exigências de `analise/tecnica.json` (`itens[].exigencias`): `atende` sim · não · não verificável, com a divergência. Não atende: comparabilidade 0, registrada.
      Resposta que não é proposta comercial (teste, simulação, recusa, preço "a confirmar"): `preco_unit: null` em `respostas.json`; o valor citado vai só na divergência, nunca na coluna de preço.
   3. Acumule em `cotacao-fornecedor/respostas.json`:
      ```json
      {"respostas": [{"pedido": "37-fornecedor-x", "fornecedor": "…", "recebida_em": "AAAA-MM-DD", "itens": [
        {"escopo": "item-37", "preco_unit": 0.0, "quantidade_base": 0, "faixas_volume": [{"a_partir_de": 0, "preco_unit": 0.0}],
         "frete": "incluso|nao_incluso|desconhecido", "prazo_entrega_dias": null, "validade_ate": "AAAA-MM-DD", "pagamento": "…",
         "atende": "sim|nao|nao_verificavel", "divergencia": "…", "comparabilidade": 1, "fonte": "respostas/<pedido>/<arquivo>"}]}]}
      ```
      Não altere os arquivos de `analise/`.
   4. **Contraproposta**, só se, no mesmo escopo e componente:
      - o preço cotado passa de outra evidência comparável nas mesmas condições de quantidade, frete e pagamento; ou
      - com ele, a margem do preço de `analise/precificacao.json` (ou de `antes-cotacao`, quando houver) fica abaixo de `margem_minima_pct` ou negativa.

      Preço pedido = o menor entre a outra evidência e a parcela do fornecedor: `preço de venda do item (analise/precificacao.json) × (1 − tributos_pct/100 − margem_minima_pct/100) − demais componentes do item`. Sem os demais componentes, não afirme que o preço garante a margem: peça melhoria sem valor ou use só a outra evidência. Nunca exponha o orçamento total, o preço de venda nem o órgão.

      Grave `<pedido>-contraproposta.md` pelo modelo, com `estado: aguardando_aprovacao` e `contraproposta_de`. Cada contraproposta tem aprovação própria. Uma por fornecedor e escopo por análise.

Estados do pedido: `rascunho` (revisão no card) → `enviado` → `respondido` | `sem_resposta` | `recusado`. Contraproposta: `aguardando_aprovacao` (aprovação no card pelo daemon) → `enviado` → …. Falha de envio não conta como enviado.

## Saída
- Passos 1–6: os `.md` e `pedidos.json` em `cotacao-fornecedor/` (o daemon valida e avisa o card).
- Passo 7: `cotacao-fornecedor/respostas.json` (formato acima), a saída que o daemon valida na leitura de resposta. Depois dela, a atualização refaz a precificação e publica nova versão.
- Não crie pendência de aprovação: contraproposta em `aguardando_aprovacao` o daemon leva ao card.

## Limites
- Nada é enviado sem aprovação humana; a skill não envia e-mail.
- Só contato comercial oficial, publicado pelo fornecedor. Quem pediu para não ser contatado (registro em `cotacao-fornecedor/respostas/`) fica fora.

Decisões: [referencias/DECISOES.md](referencias/DECISOES.md).
