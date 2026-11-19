# ConLicitação: ferramentas de concorrência e histórico de disputa

Data da investigação: 2026-10-15. Empresa da sessão: companyId 30933 (REALMAK, CNPJ 03496338000174). Método: leitura dos bundles JS (`main.b732f4f5.chunk.js`, `2.7bddd968.chunk.js`) e 56 GETs via `cl.py` (limite combinado era ~60), com pausa de 1 s. Nenhum POST/PUT/PATCH/DELETE, nada salvo, nenhuma mensagem ou robô acionado. Nenhum dado pessoal (CPF, e-mail, telefone, nomes de sócios) foi copiado para este relatório.

Base da API: `https://consultaonline.conlicitacao.com.br` (cookie de sessão, JSON). O frontend usa axios: arrays vão como `chave[]=v1&chave[]=v2`.

Convenções úteis
- IDs de UF (alfabético): AC1 AL2 AM3 AP4 BA5 CE6 **DF7** ES8 **GO9** MA10 MG11 MS12 MT13 PA14 PB15 PE16 PI17 PR18 RJ19 RN20 RO21 RR22 RS23 SC24 SE25 SP26 TO27 (confirmados por CE=6 e RS=23 nas respostas).
- `modalidade_id`: 4 = Concorrência, 7 = Dispensa (DL), 10 = Pregão Eletrônico (PE). `tipo_orgao_id`: 1 Municipal, 2 Estadual, 3 Federal, 4 Distrital.
- CNPJ: as rotas de perfil aceitam 14 dígitos com zero à esquerda. Nas respostas de `/mercado/results` o campo `cnpj` vem como número (perde o zero: `9108248000145`); preencher com zeros até 14 dígitos antes de reutilizar.
- Filtro salvo da REALMAK: `filter_id=44760` (atividades 0201, 0204, 0408, 1203, 2206, 2401; todas as esferas).

---

## 1. Tabela de endpoints testados

| # | Rota (GET) | Status | Para quê |
|---|---|---|---|
| 1 | `/mercado/get_client_filters?companyId=30933` | 200 | Filtros salvos da empresa (id 44760 e atividades). |
| 2 | `/mercado/get_filter_options.json?filter_id=44760&companyId=30933` | 200 | Atividades (id, nome, código) do filtro. |
| 3 | `/mercado/search.json` | 200 | Licitações do mercado + totais por mês, região e modalidade (visão panorâmica). |
| 4 | **`/mercado/results`** | 200 | **Itens adjudicados: fornecedor, CNPJ, item, quantidade, valor unitário/total, por licitação.** Núcleo da skill concorrência. |
| 5 | **`/mercado/search_providers.json`** | 200 | Ranking de fornecedores (CNPJ, nº de licitações, valor total) para o filtro aplicado. |
| 6 | `/mercado/search_buyers.json` | 200 | Ranking de órgãos compradores para o filtro. |
| 7 | `/mercado/products_services` | 200 | Mesmos itens adjudicados, separados em produtos e serviços. |
| 8 | `/mercado/get_public_body.json?public_body_id=` | 200 | Ficha do órgão (UASG, CNPJ, tipo, site). |
| 9 | `/mercado/get_biddings.json?orgao_id=` | 200 | Licitações de um órgão (1 retornada para o TJDFT; sem paginação aparente). |
| 10 | **`/mercado/get_result_bidding.json?bidding_id=`** | 200 | **Resultado de uma licitação: itens vencidos por fornecedor, aviso de homologação, edital.** Retorna `{"licitacao": ""}` quando não há resultado (ex.: 17991035). |
| 11 | **`/get_company_data?cnpj=`** | 200 | **Perfil cadastral do concorrente: porte (ME/EPP/DEMAIS), abertura, UF, capital, CNAEs, situação.** |
| 12 | `/mercado/company?cnpj=` | 200 | Mesmo conteúdo, formato `{"data": {...}}`. |
| 13 | **`/participants/{cnpj}`** | 200 | **Resumo de participações: nº de disputas, vitórias, valores, por UF/modalidade, itens ganhos e perdidos com valor final.** |
| 14 | **`/strategic_aspects/{cnpj}`** | 200 | **Desclassificações/inabilitações e os motivos (texto do pregoeiro).** |
| 15 | `/get_company_bidding_data.json?cnpj=&page=` | 200 | Licitações da empresa com valor estimado, itens e flags (`me_epp`, `exclusivo_regional`, vazios nos testes). Retornou só 2 licitações para a Tectronix. |
| 16 | `/mercado/search_provider?cnpj=&page=` | 200 | Itens adjudicados ao CNPJ (documentos do Elasticsearch, 43 itens, 8 páginas para a Tectronix). |
| 17 | `/list_my_biddings/{cnpj}` | 200 | Retornou `total: 0` para a Tectronix (provável "licitações monitoradas por mim"). Sem utilidade comprovada. |
| 18 | `/sanctions_list?page=&cnpj=` | 200 | Sanções do CNPJ. Tectronix: lista vazia. |
| 19 | **`/contracts/search?page=`** | 200 / 500 | **Contratos por objeto/UF/período/valor: valor estimado da licitação x valor contratado por fornecedor.** 500 ao usar `empresa=` ou `cnpj=`. |
| 20 | `/price_register/search?page=` | 200 | Atas de registro de preço (metadados e URL do PDF; sem preços nem fornecedores no JSON). |
| 21 | **`/bidding_desert/imminence?has_low_competition=true&page=&companyId=`** | 200 | **Licitações com baixa concorrência / deserta / iminência, com nº de propostas por item.** |
| 22 | `/bidding_desert/imminence/search?objeto=&page=&estados_ids[]=` | 200 | Busca por objeto/UF nas mesmas licitações (retornou casos de 2024 com itens fracassados). |
| 23 | **`/my_history?page=&filtro=all`** | 200 | **Nosso histórico: itens vencidos (valor final) e agregados por modalidade/região/órgão.** |
| 24 | `/mercado/get_followups_my_history?page=&filtro=&companyId=` | 200 | Licitações monitoradas por nós com andamentos (554 KB por página; pesado). |
| 25 | `/biddings/{id}.json` | 200 / 401 | Detalhe da licitação, inclui `contracts` (fornecedor, valor contratado) e `electronic_trading`. 401 em 17991035 mesmo após novo login (provável restrição de acesso). |
| 26 | `/price_intelligence/health` | 200 | Saúde da base de preços (12,66 milhões de pontos, coleção `precos_publicos`). |
| 27 | `/price_intelligence/saved` | 200 | Pesquisas de preço salvas (vazio). |
| 28 | `/gestao_ia/licitacoes/{id}/historico_contratacoes` | 404 | Histórico de compras do órgão por item. Só funciona para licitação com card na Gestão IA (nossa conta tem 0 cards: `/gestao_ia/cards` retorna `{"cards": {}}`). |
| 29 | `/gestao_ia/cards` | 200 | Cards da gestão (vazio). |

Só por bundle, sem chamada (POST, mutação ou sem dado para testar): `POST /price_intelligence/search`, `POST /price_intelligence/analyze`, `POST /price_intelligence/saved`, `POST /get_membership_data`, `POST/DELETE /gestao_ia/licitacoes/{id}/historico_contratacoes/interesses`, `GET .../historico_contratacoes/{licitacoes,detalhe,ocorrencias,ocorrencias/arquivos}`, `GET/POST /minhas_licitacoes/bidder_considerations[/team|/remove]`, `GET /mercado/followups`, `GET /contracts/contratos`, `GET /ata_de_registro_preco.json`. Reducers de certidões APF/SP e penalidades existem no bundle, mas sem chamada HTTP associada (a tela usa `/sanctions_list`).

Fonte do front: páginas `/concorrentes`, `/concorrente/:cnpj`, `/mercado` (análise), `/meu_historico`, `/contratos`, `/ata_de_registro_preco`, `/iminencia`, `/pesquisa_de_precos`.

---

## 2. Detalhe dos endpoints úteis

### 2.1 Filtros comuns da família `/mercado/*` (results, search_providers, search_buyers, products_services, search.json)

Parâmetros (nomes tirados do bundle; os marcados "testado" foram verificados):

| Parâmetro | Significado |
|---|---|
| `page` | Página (10 licitações por página; `per_page` é ignorado, testado). |
| `interval` | Janela em meses: 3, 6, 9, 12, 24 (testado 12 e 24). |
| `advanced_search` | **Tem de ser `true` para os filtros abaixo valerem** (testado: com `false` o `item_input`, `states` e `term` foram ignorados e o universo ficou restrito às atividades do `filter_id`). |
| `exact_search` | `true` exige a frase exata na descrição ("manutenção ar condicionado" = 0 resultados; "ar condicionado" = ok; "manutenção de ar condicionado" = 1). `false` é busca ampla (mais ruído). |
| `item_input` | Texto na descrição/marca/fabricante do item (testado). |
| `states[]` | IDs de UF (testado 7 e 9). `cities[]`, `modalities[]`, `public_body_types[]` existem no bundle (não testados). |
| `buyer_input` | Nome ou código do órgão (não testado). |
| `provider_input` | Nome ou CNPJ do fornecedor (testado: "tectronix", "hebrom", CNPJ 14 dígitos). |
| `followup_input` | Texto na síntese do acompanhamento (testado: comportou-se como o filtro de fornecedor ao procurar REALMAK). |
| `min_value`, `max_value`, `type_value` | Faixa de valor; `type_value` 1 = valor total, 2 = valor unitário (não testados). |
| `filter_id` | Filtro salvo (44760). Sem `advanced_search=true` restringe às atividades do filtro. |
| `term` | Palavra-chave; no teste não filtrou. Usar `item_input`. |

Limites observados: `/mercado/results` página 26 de 26 respondeu (1,7 MB, licitações com centenas de itens); página 2000 devolveu **500** (janela de paginação do Elasticsearch, na prática ~10 mil registros). Sem erro de cota em 56 chamadas.

### 2.2 `/mercado/results` (fornecedores vencedores e preços por item)

Exemplo de consulta que atende "quem vence manutenção/aquisição de ar-condicionado no DF/GO":
`/mercado/results?page=1&interval=12&exact_search=false&advanced_search=true&item_input=ar%20condicionado&states%5B%5D=7&states%5B%5D=9&type_value=1`
-> `lista_resultados.total = 255` licitações, `resultados[]` com 10 por página.

Estrutura: `lista_resultados.resultados[].licitacao` com os campos da licitação (`id`, `objeto`, `itens`, `modalidade_id/sigla/nome`, `edital`, `processo`, `datahora_abertura`, `data_validade`, `orgao{id,nome,cidade,estado,tipo_orgao,uasg}`) e **`licitacao.resultados[]`**, um registro por item adjudicado:

```
{"id":65951370,"licitacao_id":19470858,"portal_id":12,"atividades":"0101 0201",
 "fornecedor":"IDEIA COMERCIO E SERVICOS LTDA","cnpj":22494284000152,
 "item_numero":"1","item_descricao":"MANUTENCAO E REFORMA PREDIAL ...",
 "item_unidade":"...","item_quantidade":"1",
 "item_valor_unitario":4720.0,"item_valor_total":4720.0,
 "marca_item_ofertado":null,"fabricante_item_ofertado":null,"modelo_item_ofertado":null,
 "data_validade_licitacao":"2026-10-13","status":1,"created":"2026-10-14T23:34:51Z"}
```

Observações: `marca/fabricante/modelo` vieram nulos nos testes; o filtro de item filtra a licitação, mas a lista `resultados[]` traz todos os itens dela (filtrar no cliente por `item_descricao`).

Amostra real (DF/GO, 12 meses, "ar condicionado"): EGF ENGENHARIA TERMICA LTDA (GO; manutenção até 30.000 BTU a R$ 180 x 61; instalação 18.000 BTU a R$ 550 x 12; limpeza completa a R$ 130 x 18), SOL ENGENHARIA BRIGADA DE INCENDIO (DF; manutenção/limpeza de sistemas, R$ 23.000), NEW SOLUCOES ELETRICA E CLIMATIZACAO (GO; instalação split a R$ 600 x 6), VALE COMERCIO DE MATERIAIS (GO; split 12.000 BTU a R$ 1.988,92 x 4).

### 2.3 `/mercado/search_providers.json` e `/mercado/search_buyers.json` (rankings)

`providers: {total (máx. 100), total_pages, results:[{cnpj, razao_social, total_results, valor_total}]}`. `total_results` = nº de licitações em que o fornecedor aparece e `valor_total` soma **todos** os itens dessas licitações, não só os do `item_input`. Resultado: ranking ruidoso (apareceram fornecedores de móveis, material hospitalar etc.). Para ranking limpo de HVAC, paginar `/mercado/results` e agregar no cliente por `fornecedor` filtrando `item_descricao` (CONDICION, CLIMATIZ, SPLIT, CHILLER...).
`buyers: {total, total_pages, results:[{orgao_id, doc_count, nome, uf, cidade}]}`: para "ar condicionado" no DF vieram 23 órgãos (Correios, AGU, Embrapa, PM-DF...).

### 2.4 `/get_company_data?cnpj=` (perfil do concorrente; ME/EPP)

Campos: `company.empresa{id, cnpj, razao_social, nome_fantasia, tipo_empresa, abertura, **porte**, natureza_juridica, logradouro/numero/bairro/municipio/uf/cep, situacao, data_situacao, capital_social, cnaes[{codigo, descricao, _joinData.atividade_principal}], quadro_socios_administradores[...], parcerias, sintegra}` e `segmentosCnaes`. (Há e-mail e telefone da empresa; tratar como dado de contato e não replicar sem necessidade.)

Resultados dos casos pedidos:
- TECTRONIX SISTEMAS ELETRONICOS LTDA, CNPJ 09108248000145: porte DEMAIS, aberta em 2007, Garopaba/SC, capital R$ 100.000, CNAE principal 4329103 (elevadores/escadas), ATIVA.
- HEBROM CONSTRUCOES LTDA., CNPJ 04941945000169: porte EPP, São Paulo/SP, capital R$ 5.000.000. Existe também HEBROM COMERCIO E SERVICOS LTDA, CNPJ 03979504000193 (GO).
- EGF ENGENHARIA TERMICA LTDA, CNPJ 21445969000146: porte ME, Petrolina de Goiás/GO, capital R$ 120.000 (recorrente nas dispensas de ar-condicionado em GO).

### 2.5 `/participants/{cnpj}` (histórico de disputas e onde para nos lances)

Parâmetros: `page_vencidos`, `page_nao_vencidos`, `per_page` (testado 3 e 5; a paginação devolve `total_paginas` para cada lista).

```
{"participacoes_resumo":{
  "participacoes":565,
  "disputas_vencidas":{"quantidade":41,"valor_total":640240.26,
     "itens":[{"bidding_id":17861004,"descricao":null,"quantidade":1,
               "valor_final":196000.0,"valor_unitario":196000.0,"source_id":146}, ...]},
  "disputas_nao_vencidas":{"quantidade":524,"valor_total":80539690.93,"itens":[{... mesmo formato ...}]},
  "licitacoes_por_modalidade":[{"modalidade":10,"participacoes":41,"valor_total":640240.26}],
  "licitacoes_por_estado":[{"estado":"DF","participacoes":22,"valor_total":291120.0}, ...]},
 "paginacao":{"per_page":5,"vencidos":{"page":1,"total_itens":41,"total_paginas":9},"nao_vencidos":{...}}}
```

Leitura dos números (verificada contra o aviso de homologação de 17861004): em itens vencidos, `valor_final` = valor homologado. Em itens não vencidos, `valor_final` é, muito provavelmente, o último valor ofertado pela empresa no item, ou seja, **onde ela parou no lance** (comparar com o preço do vencedor em `/mercado/get_result_bidding.json`). Não validado com sessão de lances; tratar como indício.

Perfis testados:
| Empresa | Participações | Vitórias (itens) | Taxa | Observação |
|---|---|---|---|---|
| TECTRONIX 09108248000145 | 565 | 41 (R$ 640 mil) | 7,3% | Ganhos em DF (22) e SC (18); só modalidade 10. |
| HEBROM CONSTRUCOES 04941945000169 | 323 | 6 (R$ 10,3 mi) | 1,9% | Ganha obras em SP (modalidade 4); disputa lotes de R$ 15 a 39 mi. |
| HEBROM COMERCIO E SERVICOS 03979504000193 | 212 | 46 (R$ 8,4 mi) | 21,7% | Só GO. |
| REALMAK 03496338000174 | 692 | 37 (R$ 1,37 mi) | 5,3% | 33 vitórias no DF. Igual ao `/my_history`. |

Limites e sujeira: cobre sobretudo `source_id` 146 (Compras.gov.br, pregões eletrônicos); EGF (que ganha dispensas) aparece com 0 participações. `descricao` é quase sempre null; só `bidding_id`. Há registros absurdos (ex.: bidding 18877536 com `valor_unitario` 328152 e total de R$ 107 bilhões, mistura de quantidade com preço). Filtrar outliers.

### 2.6 `/strategic_aspects/{cnpj}` (fraquezas do concorrente)

```
{"total_participacoes":565,"desclassificacoes":30,"inabilitacoes":0,
 "percentuais":{"desclassificacoes":5.3,"inabilitacoes":0.0},
 "motivos":[{"tipo":"Desclassificação","bidding_id":18323765,"descricao":"Não apresentou a comprovação da exequibilidade da proposta...",
             "ocorrencias":1,"numero_item":"1","portal":"ComprasNet"}, ...]}
```
Útil para saber por que o concorrente cai (falta de documento, inexequibilidade, grupo sem proposta).

### 2.7 `/mercado/get_result_bidding.json?bidding_id=`

`{"licitacao":{id, datas{...}, objeto, situacao (ex.: "REABERTURA"), edital, processo, edital_status_id, edicts[]}, "orgao":{nome, uasg, cidade_uf, endereco, site}, "resultados":[{id, fornecedor, cnpj, item_numero, item_descricao, item_unidade, item_quantidade, item_valor_unitario, item_valor_total, marca/fabricante/modelo}], "acompanhamentos":[{data_fonte, sintese (texto do aviso de homologação com empresas vencedoras e preços por item), ...}]}`.
Exemplo 17861004 (TJDFT, manutenção de portas giratórias): 44 itens adjudicados; vencedores TECTRONIX (item 1 a R$ 196.000) e REALMAK (item 23 a R$ 79.000 etc.). Não traz lances, só o preço final. Valor estimado/teto não vem aqui (ver 2.8).

### 2.8 `/biddings/{id}.json` (teto, contratos, situação do pregão)

Campos para concorrência: `valor_estimado` (teto da licitação; 987.421,87 em 17861004), `tipo_valor_estimado_id`, `itens` (texto com "Tratamento Diferenciado" quando ME/EPP, quando o portal informa), `electronic_trading{trading_situation, trading_id, source_id}`, `bidding_info[]` (esclarecimentos/impugnações), e **`contracts[]`**: `nome_fornecedor`, `cpf_cnpj`, `valor_contratado`, `data_assinatura`, `vigencia_inicio/fim`, `contrato_pncp_id`, `files[]` (URLs do PNCP). Em 17861004: contrato TECTRONIX R$ 291.120 e REALMAK R$ 96.610.
Deságio por licitação = `1 - valor_contratado / valor_estimado` (só confiável com um contrato cobrindo todos os itens). `me_epp` e `exclusivo_regional` vieram `null` nos testes: o enquadramento ME/EPP do **concorrente** deve ser lido em `porte` (2.4).

### 2.9 `/contracts/search?page=` (estimado x contratado, por objeto/UF)

Parâmetros (bundle): `objeto`, `exact_search`, `all_segments`/`searchAll` (true = todo o mercado, não só nossos segmentos), `state[]`, `Getcities[]`, `tipo_orgao_id[]`, `tipo_contrato_id[]`, `poderes[]`, `modalidadeSelecionada[]`, `vigencia_inicio`/`vigencia_fim` (YYYY-MM-DD), `valorEstimado`/`valorEstimadoAte`, `valorContratado`/`valorContratadoAte`, `orgao`, `edital`, `id`, `companyId`. **`empresa` e `cnpj` provocaram 500** nos testes (busca por fornecedor não funcionou).

Teste: `/contracts/search?page=1&objeto=ar%20condicionado&state[]=7&state[]=9&exact_search=true&all_segments=true&searchAll=true&companyId=30933` -> `{contratos[20], total_pages:21, total_rows:432}`. Cada item: `_source{id, objeto, itens, valor_estimado, modalidade_sigla, orgao{...}, contratos[{nome_fornecedor, cpf_cnpj, valor_contratado, data_assinatura, vigencia_inicio/fim, contrato_pncp_id, tipo_poder}], contratos_arquivos[], public_body{capag...}}`. Sem `exact_search`, o termo "manutenção ar condicionado" trouxe ruído (água mineral, ônibus).

Amostra (primeira página, 15 licitações com estimado > 0, contratos somados; indicativo, não estatística): deságio mediano ~16% nas dispensas (variando de 0% a 69%) e ~42% nos pregões eletrônicos (25% a 52%). Exemplos: AREMAR MIX (DF, PE) R$ 626.638 -> R$ 350.675 (44%); CAPUCHE TECNOCLIMA (DF, PE) R$ 887.917 -> R$ 665.913 (25%); POLO PECAS PARA REFRIGERACAO (GO, PE) R$ 133.184 -> R$ 76.680 (42%); 3R COMERCIO E SERVICOS DE MAQUINAS (DF, DL) R$ 62.867 -> R$ 53.080 (16%); EGF (GO, DL) R$ 31.267 -> R$ 9.600 (69%). Atenção: contratos podem cobrir só parte dos itens/lotes e `valor_estimado = 0` é frequente (excluir).

### 2.10 `/bidding_desert/imminence` e `/search` (baixa concorrência)

`/bidding_desert/imminence?{has_low_competition|has_desert|has_imminence}=true&page=&companyId=30933` -> `{imminences[10], total_pages, total_rows, total_imminence:[{has_low_competition:147},{has_imminence:196},{has_desert:3043}]}`.
Cada `_source`: dados da licitação (`edital`, `objeto`, `orgao_*`, `valor_estimado`, `atividade`, `tipo_agrupamento_nome`, `edicts`), `imminence{has_low_competition, has_imminence, has_desert, bidding_type, trading_id, source_id}` e **`itens_imminance[]`/`imminence.imminence_items[]`**: `number_item`, `description_item`, `quantity`, `estimated_value`, **`proposals`** (nº de propostas no item), `type_of_judgment`, `bidding_desert_imminence_situation` (ex.: "Baixa concorrência", "Fracassada", "Outros").
`/bidding_desert/imminence/search?objeto=&page=&estados_ids[]=&cidades_ids[]=&tipo_orgao_id=&vigencia_inicio=&vigencia_fim=` busca por texto. Teste "ar condicionado" DF/GO: 1 licitação (BRB, 2024, split, item com 1 proposta e item fracassado). `/bidding_desert/imminence/search_item?item=&states_ids=&stateImminence=` existe no bundle (não testado). Único endpoint com **número de propostas por item**.

### 2.11 `/my_history?page=&filtro=&startDate=&endDate=` (resultado nosso)

`filtro`: `all`, `winner`, `partial_winner`, `lost`, `cancelled`, `failed`, `revoked`, `declined`. Retorno: `total_itens_vencidos` (37), `total_investimento` (R$ 1.372.057,84), `itens_vencidos[]` (`bidding_id`, `edital`, `objeto`, `orgao`, `estado`, `cidade`, `quantidade`, `valor_final`), agregados `licitacoes_por_modalidade/regiao/orgao/portal`, `count_bidding_monitored` (81). Cada exemplo: Inmetro/RJ, manutenção de climatização, itens a R$ 72.000 e R$ 54.924,72; Embrapa/DF, geradores a R$ 21.128,58.

### 2.12 Pesquisa de preços (`/price_intelligence/*`)

GET `health` e `saved` funcionam (base com 12.664.197 pontos de preço públicos). A busca em si é **POST** (`/price_intelligence/search` com `query`, `data_gte`, `ufs[]`, `queries[]`, `spec_assumida`, `tipo_query`; timeout de 100 s) e `analyze` (`query`); não chamados. Descrição apenas por bundle.

### 2.13 Histórico de contratação do órgão (Gestão IA)

`GET /gestao_ia/licitacoes/{id}/historico_contratacoes?page=&per_page=&q=` -> `items[{key,label,interesse,licitacoes,linhas,valor_medio,valor_mediano,gasto_total,ultima_compra}]`, `total`, `orgao.nome`; `.../licitacoes?item=`, `.../detalhe?bidding=&item=`, `.../ocorrencias?bidding=`. O `{id}` é o da licitação **no módulo Gestão IA** (card). Não testável sem card (404 com id de licitação comum).

---

## 3. O que serve para cada skill do agente

- **concorrencia** (skill atual): `/mercado/results` (quem vence e a que preço unitário, por objeto/UF/janela); `/participants/{cnpj}` (taxa de vitória, UFs, itens perdidos e último valor ofertado); `/get_company_data` (porte ME/EPP, CNAEs, capital, UF); `/strategic_aspects` (por que é desclassificado); `/contracts/search` (estimado x contratado, deságio); `/mercado/get_result_bidding` (preço dos vencedores por item); `/mercado/search_buyers` (quem compra). Fluxo sugerido: results (objeto+UF) -> agregar fornecedores por CNPJ -> `get_company_data` + `participants` para os 5 a 10 mais frequentes -> `contracts/search` para deságio por modalidade.
- **triagem**: `/bidding_desert/imminence` (baixa concorrência, deserta, fracassada, propostas por item); `participants` dos fornecedores recorrentes do órgão; `search_buyers` e `get_public_body` (perfil do órgão).
- **mapa de preço**: `/mercado/results` e `/mercado/products_services` (valor unitário adjudicado por item, região, período); `/contracts/search` (valor contratado); `/price_intelligence` (POST, 12,6 mi pontos); `historico_contratacoes` (só com card; valor médio/mediano e última compra do órgão); atas só com PDF.
- **adequação técnica**: `strategic_aspects` (motivos técnicos de desclassificação: exequibilidade, documentação); `contracts[].files` e `price_register` (links para contrato/ata no PNCP); `marca/modelo` quase sempre nulos.
- **cotação com fornecedor**: `/mercado/results` (quem entregou o item e a que preço) + `get_company_data` (CNAE, UF, porte, situação) para escolher fornecedor; `search_providers` como atalho (ruidoso). Dados de contato existem em `get_company_data`, tratar com cuidado.
- **precificação**: deságio por modalidade (`contracts/search`), preço dos vencedores (`results`), último lance perdido dos concorrentes (`participants.disputas_nao_vencidas`) cruzado com `get_result_bidding` do mesmo `bidding_id`, nossa taxa de vitória (`/participants/03496338000174`).
- **registro de resultado**: `/my_history` (nossos itens vencidos), `/participants/03496338000174`, `/mercado/get_result_bidding`, `/biddings/{id}.json` (contratos). `bidder_considerations` (observações da equipe) só por POST para gravar (não usado).

---

## 4. Limitações e riscos

- **Sem lances rodada a rodada nem ranking final por item.** Só existem preço homologado do vencedor, `valor_final` por participante em `/participants` (apenas Compras.gov.br) e nº de propostas por item em `bidding_desert`. Não há lista completa de participantes de uma licitação nem posição do segundo colocado.
- **Cobertura parcial de `/mercado/results`.** Para a própria REALMAK (24 meses) retornou só 2 licitações, contra 37 itens ganhos em `/my_history`. Não tratar a lista como universo completo. Para DL, a fonte principal é PNCP (`portal_id` 12).
- **Termos de busca:** `advanced_search=true` é obrigatório; `exact_search=true` é literal (frases diferentes zeram o resultado); `term` não filtrou; `item_input` busca a licitação, não só o item, então é preciso filtrar `item_descricao` no cliente. Rankings (`search_providers`) somam valor de todos os itens das licitações e são ruidosos.
- **Paginação:** 10 licitações por página, `per_page` ignorado em `/mercado/*`; páginas fundas (2000) devolvem 500; payloads chegam a 1,7 MB por página. `search_providers` e `search_buyers` têm teto de 100 registros.
- **Erros observados:** 500 em `/contracts/search` com `empresa=` ou `cnpj=` (busca de contratos por fornecedor indisponível); 401 em `/biddings/17991035.json` (acesso restrito); 404 em `historico_contratacoes` (depende de card na Gestão IA); `{"licitacao": ""}` em `get_result_bidding` sem resultado.
- **Qualidade dos dados:** outliers (valor unitário igual à quantidade, bilhões fantasmas); `valor_estimado = 0` frequente; `me_epp`/`exclusivo_regional` e marca/modelo nulos; `cnpj` numérico sem zero à esquerda; deságio por contrato pode cobrir só parte dos itens; `valor_final` de itens perdidos é interpretação (não confirmada).
- **ME/EPP** do concorrente só via `porte` cadastral (a Receita pode estar defasada; o benefício vale na data da licitação).
- **Cota:** nenhum bloqueio em 56 GETs; limites de plano não verificados (sem cabeçalhos de cota expostos por `cl.py`). As telas de Concorrentes, Mercado, Contratos e Imminência podem ter limites por assinatura; a conta testada tem acesso a todas.
- **Só tela / por POST:** pesquisa de preço (POST), `get_membership_data` (POST), gravar interesse/observações (POST/DELETE) e robô de lance não foram acionados. Download de edital e certidões APF/SP não têm chamada identificada.
- **Dados pessoais:** respostas de empresa trazem quadro societário (nomes de pessoas), e-mail e telefone. A skill deve evitar copiar esses campos.
