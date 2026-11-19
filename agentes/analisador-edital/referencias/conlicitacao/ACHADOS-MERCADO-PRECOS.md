# ConLicitação: mercado, preços, atas e contratos (mapeamento somente leitura)

Data do teste: 2026-10-15. Empresa da sessão: companyId 30933 (REALMAK), filtro de licitações `filter_id=44760` (atividades 0201, 0204, 0408, 1203, 2206, 2401).
Foram feitas cerca de 56 requisições GET via `cl.py`. Nenhum POST, nenhuma pesquisa salva, nenhum alerta criado.
Amostras brutas ficaram em `out/*.json` (pasta `scratchpad/conlicitacao/out`).

Base da API: `https://consultaonline.conlicitacao.com.br` (sessão por cookie). Todos os caminhos abaixo são relativos a ela.

---

## 1. Tabela de endpoints

| Rota | Método | Status | Para quê |
|---|---|---|---|
| `/mercado/results?page=N` | GET | 200 | **Principal.** Licitações com resultado e todos os itens homologados (descrição, qtd, valor unitário, vencedor, CNPJ). 10 licitações por página. |
| `/mercado/search.json` | GET | 200 | Painel agregado: `total_entries`, série mensal, UFs, modalidades e 7 licitações de amostra. Serve para contar volume e medir mercado. |
| `/mercado/search_providers.json?page=N` | GET | 200 | Ranking de concorrentes (CNPJ, razão social, nº de resultados, valor total) para o termo filtrado. |
| `/mercado/search_buyers.json?page=N` | GET | 200 | Ranking de órgãos compradores (orgao_id, nome, UF, cidade, `doc_count`). |
| `/mercado/search_provider?cnpj=X&page=N` | GET | 200 | Histórico de itens ganhos por um CNPJ (documentos `resultados_new`, com preço unitário). 323 resultados para o CNPJ testado, 5 por página. |
| `/mercado/company?cnpj=X` | GET | 200 | Perfil do CNPJ: porte, capital social, CNAEs, situação, `sancoes`, segmentos. Traz dados pessoais de sócios, e-mail e telefone; não use esses campos. |
| `/mercado/get_result_bidding.json?bidding_id=ID` | GET | 200 | Detalhe de uma licitação: itens/resultados, edital (zip), observação com link PNCP. |
| `/mercado/get_biddings.json?orgao_id=ID` | GET | 200 | Licitações recentes de um órgão (histórico do comprador). |
| `/mercado/get_public_body.json?public_body_id=ID` | GET | 200 | Dados do órgão (nome, UASG, CNPJ, UF, `tem_capag`). |
| `/mercado/products_services?page=N` | GET | 200 | Lista de produtos e serviços do filtro (24 itens, 3 páginas). Não respeitou bem o `item_input`; baixo valor. |
| `/mercado/get_client_filters?companyId=30933` | GET | 200 | Filtros salvos da empresa (retorna o `filter_id` 44760). |
| `/mercado/get_filter_options.json?filter_id=44760&companyId=30933` | GET | 200 | Atividades do filtro (ids e códigos 0201, 0204, 0408...). Sem `filter_id` retorna 404. |
| `/contracts/search?page=N` | GET | 200 | **Contratos** (PNCP e outros) com `valor_estimado` da licitação e `valor_contratado` por fornecedor. Permite calcular deságio. 20 por página. |
| `/contracts/contratos?page=N&companyId=30933` | GET | 200 | Lista de contratos da conta (sem filtro de texto). Pouco útil. |
| `/price_register/search?page=N` | GET | 200 | **Atas de registro de preços** (metadados: nº da ata, vigência, link do PDF no PNCP). Não traz preços. 20 por página. |
| `/ata_de_registro_preco.json?page=N` | GET | 200 | Lista geral de atas, sem filtro (feed). |
| `/price_intelligence/health` | GET | 200 | Saúde da base de inteligência de preços: coleção `precos_publicos`, **12.664.197 pontos** indexados. |
| `/price_intelligence/saved` | GET | 200 | Pesquisas de preço salvas da conta. Retornou lista vazia. |
| `/price_intelligence/saved/:id` | GET | não testado | Leitura de uma pesquisa salva (só funciona se houver salvas). |
| `/price_intelligence/search` | **POST** | não chamado | Pesquisa semântica de preços homologados (tela "Análise de Preços"). Descrito pelo bundle. GET retorna 404. |
| `/price_intelligence/analyze` | **POST** | não chamado | Passo de IA que interpreta a consulta e pede esclarecimentos. |
| `/price_intelligence/saved` | **POST** | não chamado | Salva a pesquisa (efeito colateral; nunca chamar). |
| `/gestao_ia/licitacoes/:id/historico_contratacoes` | GET | 404 (id sem card) | Histórico de compras por item de um card da Gestão IA. Exige a licitação estar no board (board vazio: `/gestao_ia/cards` retornou `{}`). |
| `/gestao_ia/licitacoes/:id/historico_contratacoes/{licitacoes,detalhe,ocorrencias}` | GET | não testado | Subníveis do histórico (ver seção 2.9). |
| `/contract_validations*` | n/d | não testado | Análise de cláusulas contratuais com IA (upload de contrato). Fora do escopo de preço. |
| `/mercado`, `/pesquisa_de_precos`, `/pesquisa_de_precos/salvas`, `/price_intelligence/search` (GET), `/ata_de_registro_preco`, `/contratos`, `/historico_contratacoes`, `/monitoring_quoted` | GET | 404 | Rotas de **frontend** (SPA), não existem na API. `/monitoring_quoted` é apenas uma landing de marketing do "Monitorar Chat". |

---

## 2. Detalhe dos endpoints úteis

### 2.1 Parâmetros comuns do módulo Mercado
Usados por `search.json`, `results`, `search_providers.json`, `search_buyers.json`, `products_services`, `followups`.

| Parâmetro | Efeito observado |
|---|---|
| `filter_id` | Filtro da conta (44760). Escopo = atividades do filtro (0201, 0204, 0408, 1203, 2206, 2401). Sem o parâmetro, o resultado foi igual (usa o filtro padrão). Importante: itens fora dessas atividades podem não aparecer. |
| `interval` | Janela em meses: 3, 6, 9, 12, 24 (opções da tela). 24 funcionou. |
| `item_input` | Busca textual nas **descrições de itens** homologados. Sem `exact_search` é do tipo "qualquer palavra" (muito ruído: "forno combinado" deu 1.963 licitações em 12 meses). |
| `exact_search=true` | Busca por frase exata. "forno combinado" caiu para 17 (12 meses) e 29 (24 meses). **Use sempre.** |
| `term` | Busca textual no objeto da licitação (mais ruído; ex.: 4.348). |
| `min_value`, `max_value`, `type_value` | Faixa de valor. `type_value=1` valor total, `2` valor unitário. Funcionou (149 resultados na faixa 20-40 mil unitário para "forno combinado"). |
| `provider_input`, `buyer_input`, `followup_input`, `advanced_search`, `modalities`, `public_body_types`, `cities` | Existem no bundle; não testados individualmente. |
| `states`, `states[]` | **Não filtraram** (total inalterado). Filtrar por UF do lado do cliente usando `licitacao.orgao.estado`. |
| `page` | Funciona em `/results` (10 por página). Em `/search.json` a paginação é ignorada (sempre as mesmas 7). |

Limites: o servidor não rejeitou nenhuma chamada por cota. Páginas de `/results` pesam até ~440 KB (licitação com 290 itens vem inteira).

### 2.2 `GET /mercado/results?page=N&filter_id=44760&interval=12&item_input=<texto>&exact_search=true`
Resposta: `{"lista_resultados": {"total": 29, "resultados": [{"licitacao": {...}}, ...]}}`.

Campos de `licitacao`: `id`, `objeto`, `itens` (texto dos itens do edital), `modalidade_sigla/nome` (PE, DL, CR...), `edital`, `processo`, `data_validade` (data da sessão), `orgao{id,nome,uasg,cidade,estado,tipo_orgao}`, `observacao` (traz o ID da contratação PNCP e a fonte), `resultados[]`, `acompanhamentos`.

Campos de cada `resultados[]` (item homologado, **um registro por item com o vencedor**):
`item_numero`, `item_descricao`, `item_unidade`, `item_quantidade` (string), `item_valor_unitario`, `item_valor_total`, `fornecedor`, `cnpj`, `marca_item_ofertado`/`modelo_item_ofertado`/`fabricante_item_ofertado` (vieram nulos nas amostras), `atividades` (códigos), `portal_id`, `data_validade_licitacao`, `created` (quando foi indexado).

Atenção: o filtro casa no nível da **licitação**, não do item. Todos os itens da licitação vêm junto; é preciso filtrar a descrição do item no cliente (ex.: conter "forno" e "combinado"). Não há campo de valor estimado por item, nem lista de perdedores/lances.

Exemplos reais (24 meses, "forno combinado", itens filtrados):
```
2026-10-07 RJ DL  Forno Industrial elétrico (combinado 5 GN) qtd 2  R$ 21.553,59  E.M.P.M. COMERCIO DE MAQUINAS INDUSTRIAIS
2026-05-08 SP PE  Forno combinado inteligente        qtd 1  R$ 72.510,80  B10 LICITA LTDA
2026-02-12 CE PE  Forno combinado a gás 20 GNs       qtd 5  R$ 21.500,00  AGIL COMERCIO E DISTRIBUIDORA
2025-12-12 PR PE  Forno Combinado FCDB-10 GN a gás   qtd 1  R$ 28.600,00  NELCI BULAU CAMPRA
2025-11-12 BA PE  Forno combinado a gás 40 GN        qtd 2  R$ 109.945,00 UNIQUE COMERCIO DE EQUIPAMENTOS
2025-11-04 GO PE  Forno combinado elétrico 3 GN      qtd 2  R$ 14.200,00  UNIQUE COMERCIO DE EQUIPAMENTOS
2025-10-14 SP PE  Forno combinado industrial elétrico qtd 4 R$ 78.329,40  PRATICA PRODUTOS S.A.
```
Ruído esperado: o mesmo termo traz serviços, acessórios (cubas GN, pastilhas de limpeza) e manutenção de forno. É preciso classificar item (equipamento, serviço, insumo).

Exemplos "manutenção de ar condicionado" (12 meses, 40 licitações, 82 itens com a expressão):
```
2026-10-06 GO DL  MANUTENÇÃO DE AR CONDICIONADO ATÉ 30.000BTUs   qtd 61  R$ 180,00   D SERVICOS E MANUTENCOES
2026-09-16 GO PE  Manutenção preventiva ar condicionado (un)      qtd 424 R$ 93,00    GENESIS COMERCIO E MANUTENCOES
2026-09-16 GO PE  Instalação split hi-wall 12.000 BTUs            qtd 6   R$ 250,00   GENESIS COMERCIO E MANUTENCOES
2026-09-16 GO PE  Desinstalação split 12.000 BTUs                 qtd 6   R$ 51,00    GENESIS COMERCIO E MANUTENCOES
2026-08-21 MA PE  Manutenção ar-cond., bebedouros e correlatos    qtd 1   R$ 265.000  JAMEL EMPREENDIMENTOS
```
Exemplos "split 12000 btus" (34 licitações, 12 meses):
```
2026-09-28 SC PE  Compressor para split 12000 BTUS       qtd 12 R$ 856,00   VS CLIMATIZACAO E SERVICO
2026-09-28 SC PE  Placa eletrônica split 12000-18000     qtd 8  R$ 282,00   VS CLIMATIZACAO E SERVICO
2026-09-22 RN PE  Ar-condicionado split 12000 BTUs + instalação  qtd 72 R$ 2.330,00  CWC DISTRIBUIDORA
2026-09-22 RN PE  Ar-condicionado split 9000 BTUs + instalação   qtd 62 R$ 1.280,00  RODOLFO THIAGO P. DE PALHARES
```

### 2.3 `GET /mercado/search.json` (painel agregado)
Mesmos parâmetros. Resposta: `total_entries`, `licitacoes[7]` (amostra), `date_range` e `date_range_accumulated` (série mensal `[{x:"Set-26", y:5239}]`), `estados.regions` (contagem por região), `modalities` (contagem por modalidade).
Uso: volume de mercado por mês, mix de modalidades. Exemplo: "manutenção de ar condicionado" (busca ampla) = 33.806 entradas em 12 meses, 58% pregão eletrônico, 24% dispensa.

### 2.4 `GET /mercado/search_providers.json?page=N` (ranking de concorrentes)
Resposta: `providers{total, total_pages, results[{cnpj, razao_social, total_results, valor_total}]}`.
Top do termo "forno combinado" (busca ampla, 12 meses): SOUL DISTRIBUIDORA (207 resultados), REFINAR EMPRESARIAL (172), CASTRO EQUIPAMENTOS (131), TECNOBLU COMERCIO DE REFRIGERACAO (107).
Cuidado: com busca ampla o ranking soma licitações inteiras (valor_total na casa de centenas de milhões, claramente de outros itens). Use com `exact_search=true` e valide pelos itens.

### 2.5 `GET /mercado/search_buyers.json?page=N`
`buyers{total, total_pages, results[{orgao_id, nome, uf, cidade, doc_count}]}`. Mostra quais órgãos mais compram o termo (útil para triagem e concorrência regional).

### 2.6 `GET /mercado/search_provider?cnpj=<14 dígitos>&page=N`
`provider{total, total_pages, results[{_source: {item_descricao, item_valor_unitario, item_quantidade, orgao_nome, data_validade_licitacao, objeto, atividades...}}]}`. Cinco por página. Dá o portfólio de preços de um concorrente específico (os mesmos campos de item de 2.2). Para a skill de concorrência: o que o concorrente ganha, onde e a que preço.

### 2.7 `GET /contracts/search?page=N`
Parâmetros comprovados:

| Parâmetro | Observação |
|---|---|
| `objeto` | Texto do objeto. Com `exact_search=true` vira frase exata. |
| `exact_search` | `true` ou `false`. |
| `empresa` | Nome do fornecedor (testado "GENESIS COMERCIO": 27 contratos). |
| `state[]=<estado_id>` | **Funciona** (ex.: `state[]=9` = GO). `state=9` sem colchetes dá 500. IDs de estado são os de `orgao.estado_id`. |
| `valorContratado`, `valorContratadoAte` | Faixa do valor contratado. Funcionou. |
| `valorEstimado`, `valorEstimadoAte` | Faixa do valor estimado (no bundle; não testado). |
| `vigencia_inicio`, `vigencia_fim` | `YYYY-MM-DD`. Funcionou. |
| `tipo_orgao_id`, `tipo_contrato_id`, `modalidadeSelecionada`, `poderes`, `Getcities`, `orgao`, `edital`, `id`, `all_segments`/`searchAll` | No bundle; não testados. |
| `companyId=30933` | Enviado pelo frontend; funcionou também sem ele no teste de atas, mas mantenha. |
| `cnpj` | Deu 500 isolado; usar `empresa` por nome. |

Resposta: `{contratos:[{_source:{...}}], total_rows, total_pages}` (20 por página; "manutenção de ar condicionado" exato = 209 contratos, 10 páginas).
Campos de `_source`: dados da licitação (`objeto`, `itens`, `modalidade_sigla`, `edital`, `orgao{...}`, `public_body`, `atividade`) mais:
- `valor_estimado`: valor estimado da licitação (frequentemente 0.0 quando o órgão não informou).
- `contratos[]`: `valor_contratado`, `nome_fornecedor`, `cpf_cnpj`, `id_contrato`, `data_assinatura`, `vigencia_inicio`, `vigencia_fim`, `contrato_pncp_id`, `contratacao_pncp_id`, `fonte`, `tipo_poder`.
- `contratos_arquivos[]`: `url`, `document_type_name`, `document_title` (PDF do contrato).

**Deságio global calculável** (valor_contratado / valor_estimado), por licitação. Exemplos reais de "manutenção de ar condicionado":
```
CE DL  estimado 3.880,00   contratado 3.090,00   (-20%)  CVC REFRIGERACAO
CE DL  estimado 21.280,00  contratado 13.832,00  (-35%)  MARIA EDUARDA CARVALHO
SP PE  estimado 34.306,56  contratado 4.800,00   (-86%)  ITOPRO ENGENHARIA DA CLIMATIZACAO  (provável contrato parcial por lote)
CE DL  estimado 7.500,00   contratado 5.625,00   (-25%)  NS COMERCIO E SERVICOS
CE DL  estimado 13.692,50  contratado 13.401,00  (-2%)
GO PE  estimado 425.760,85 contratado 143.000,00 (-66%)  COLD-SUL LTDA
```
Cuidados: licitação com vários contratos (lotes ou fornecedores) exige somar ou comparar por item; `valor_estimado` 0.0 inviabiliza a conta; contrato pode ser parcial ou aditivado.

### 2.8 `GET /price_register/search?page=N` (atas de registro de preços)
Parâmetros (do bundle): `objeto`, `exact_search`, `state[]`, `Getcities`, `id`, `edital`, `orgao`, `tipo_orgao_id`, `vigencia_inicio`, `vigencia_fim`. Resposta: `{atas:[{_source}], total_pages, total_rows}` (20 por página). "ar condicionado" exato = 2.238 licitações com ata; "forno combinado" exato = 0.
Campos: licitação (`objeto`, `modalidade_sigla`, `edital`, `atividade`, `orgao{...uasg}`) e `atas[]`: `numero_ata_registro_preco`, `ano_ata`, `data_assinatura`, `data_vigencia_inicio`, `data_vigencia_fim`, `numero_controle_pncp`, `url_ata` (PDF no PNCP), `document_title`, `bidding_id`.
**Não há preço nem item na ata**; os preços ficam no PDF (`url_ata`) ou, para a mesma licitação, em `/mercado/get_result_bidding.json?bidding_id=<bidding_id>`. A vigência (fim da ata) indica carona/adesão possível e renovação prevista.

### 2.9 Pesquisa de Preços / Análise de Preços (`/price_intelligence/*`, tela `/pesquisa_de_precos`)
Base: 12,66 milhões de pontos de preço público (`/price_intelligence/health`). Só a **leitura** de salvas e o health são GET; a busca é POST.
Descrito no bundle (não chamado):
- `POST /price_intelligence/analyze` corpo `{"query": "split 12000 btus"}`. Resposta (campos lidos pelo front): `clarificacao{necessaria, perguntas[{pergunta, tipo:"escolha"|"quantidade", opcoes, unidade}]}`, `queries[]`, `spec_assumida`, `tipo`. Timeout 35s.
- `POST /price_intelligence/search` corpo `{query, data_gte?, ufs?[], queries?[], spec_assumida?, tipo_query?}`. Timeout 100s. Resposta: `hits[]` (cada hit tem `payload{item_descricao, item_unidade, item_quantidade, item_valor_unitario, item_valor_total, fornecedor, cnpj, orgao_nome, municipio, uf, licitacao_id, created}`, `preco_normalizado`, `valor_global`, `item_unidade_norm`, `confirmado_pelo_edital`, `edital_resumo`), `stats{n_total, n_outliers, mediana, p25, p75...}`, `timeseries{points[{mês, p25, p75, mediana, count}], trend_pct}`, `curation{analyzed, kept, reason}`, `alerts[]`, `regime` ("unitario" ou "global"), `unidade_referencia`, `total`.
  O front calcula, a partir dos hits, ranking de concorrentes (`vitorias`, `mediana`, `menor` por CNPJ).
- `POST /price_intelligence/saved` salva a pesquisa (`name, query, ufs, notes, snapshot`); `DELETE /price_intelligence/saved/:id` apaga. Nunca chamar.
- **Acesso restrito no front**: a tela só abre para perfis com `alfa_tester === true` ou `clientId` 139359 (função `yl` do bundle). A conta REALMAK (30933) provavelmente não está na lista (item de menu oculto). O backend pode aceitar o POST mesmo assim, mas **não foi testado** por regra. O `health` respondeu 200 para a conta.

### 2.10 Histórico de contratações da Gestão IA (`/gestao_ia/licitacoes/:id/historico_contratacoes`)
GET `?page=&per_page=&q=` devolve `{items:[{key,label,interesse,licitacoes,linhas,valor_medio,valor_mediano,gasto_total,ultima_compra}], total, orgao{nome}}`: para cada item de uma licitação do board, quantas vezes o órgão comprou, valor médio, mediano e gasto total. Subníveis: `/licitacoes?item=KEY`, `/detalhe?bidding=&item=`, `/ocorrencias?bidding=` (+ `/ocorrencias/arquivos`), e `POST/DELETE /interesses` (marca itens de interesse; efeito colateral). Retornou 404 para licitação fora do board (board vazio). Só testável depois de existir um card, o que exige POST em `/gestao_ia/cards` (não fizemos).

### 2.11 Outros úteis
- `GET /mercado/get_result_bidding.json?bidding_id=ID`: `licitacao{objeto, situacao, edital, processo, observacao, edicts[{filename,url}]}`, `orgao{nome,uasg,cidade_uf}`, `resultados[]` (itens). O link `edicts[].url` aponta para `/boletim_web/public/licitacoes/<id>/arquivos/edital.zip` (download, não testado).
- `GET /mercado/company?cnpj=X`: porte, capital social, CNAEs, `sancoes`, segmentos; útil para perfil do concorrente (porte ME/EPP, sanções).

---

## 3. O que serve para cada skill do agente de precificação

| Skill | Fonte ConLicitação | Como usar |
|---|---|---|
| Triagem | `/mercado/search.json` (volume mensal, modalidades) e `/mercado/search_buyers.json` | Medir demanda do objeto e ver se há histórico do órgão (`/mercado/get_biddings.json?orgao_id=`). Checar se o edital já tem atas (`/price_register/search`) para o objeto. |
| Mapa de preço (custos e referência) | `/mercado/results` (`item_input` + `exact_search=true`), `/contracts/search` | Coletar `item_valor_unitario` por item com data, UF, órgão e vencedor; filtrar item no cliente; calcular mediana, p25, p75 por unidade; excluir outliers (ex.: 265.000 por "serviços" global). Contratos dão preço global por licitação. |
| Adequação técnica | descrição do item em `/mercado/results` (`item_descricao`, `marca/modelo` quando houver) e `observacao` | Comparar especificação exigida (GN, BTU, tensão) com o que foi homologado. Marca/modelo vêm nulos; o edital (zip) e a ata (PDF) é que trazem especificação. |
| Cotação com fornecedor | `/mercado/results` (fornecedor/CNPJ de quem vendeu o mesmo item) | Lista de revendedores e distribuidores ativos por item para pedir cotação. `/mercado/company?cnpj=` dá porte e situação cadastral. |
| Concorrência (quem vence e com que deságio) | `/mercado/search_providers.json`, `/mercado/search_provider?cnpj=`, `/contracts/search` (estimado x contratado) | Ranking de vencedores por termo e UF (filtrar no cliente), portfólio de preços de cada CNPJ, deságio global por licitação (contratado/estimado). Deságio por item não existe: o resultado só traz o valor homologado, sem valor de referência por item. |
| Precificação (piso, alvo, lances) | estatísticas calculadas sobre os preços homologados | Piso = p25 ou menor valor homologado recente; alvo = mediana; deságio típico = distribuição do contratado/estimado (apenas onde `valor_estimado` > 0). Não há lances intermediários nem ordem de classificação. |
| Registro de resultado | `/mercado/get_result_bidding.json?bidding_id=` após a sessão | Conferir o resultado oficial indexado (com defasagem; ver limitações) e comparar com a proposta da REALMAK. |
| (extra) Atas | `/price_register/search` | Ver vigência e número da ata (`url_ata`) para carona/adesão e benchmarking de registro de preços. Preço só no PDF. |

---

## 4. Limitações e riscos

1. **Busca ampla gera muito ruído.** Sem `exact_search=true` o texto casa qualquer palavra (1.963 licitações para "forno combinado" contra 17 exatas). A busca exata, por sua vez, não pega variações ("forno combinado" vs "forno elétrico combinado" vs "forno industrial combinado"). Rodar várias consultas e normalizar.
2. **Filtro no nível da licitação, não do item.** `/results` devolve a licitação inteira (até 290 itens). O agente precisa filtrar item por item, o que aumenta o volume de dados (páginas de até ~440 KB).
3. **Só homologado do vencedor.** Cada item traz um único preço (do vencedor). Sem lances, sem classificação, sem perdedores, sem valor de referência por item. Deságio só em nível de licitação via `/contracts/search`, e `valor_estimado` costuma vir 0.0 (na amostra de 20 contratos, 4 vieram com 0.0).
4. **Dados incompletos por item:** `marca_item_ofertado`, `modelo` e `fabricante` vieram nulos em todas as amostras; unidade e quantidade são texto livre (`"-"`, `null`, `"SERVICO (S)"`); itens com valor nulo existem. Unidades heterogêneas (UN, Unidade, Serviços) exigem normalização. Itens de manutenção podem ser globais (R$ 265 mil) e distorcem a mediana.
5. **Escopo do `filter_id`.** O Mercado só enxerga as atividades do filtro da conta (0201, 0204, 0408, 1203, 2206, 2401). Itens fora delas (ex.: equipamentos de outras categorias) podem faltar. Não confirmado se remover o `filter_id` amplia o escopo (total igual no teste).
6. **Filtros de UF no Mercado não funcionaram** (`states`, `states[]`, `state[]`); em `/contracts/search` funciona só `state[]=<estado_id>`. `state=9` e `cnpj=` dão HTTP 500.
7. **Paginação:** `/mercado/search.json` ignora `page` (sempre 7 licitações); `/results` pagina de 10 em 10 (200 páginas para 2.000 licitações); contratos e atas, 20 por página. Muitas páginas para varreduras amplas.
8. **Defasagem.** Resultados aparecem depois de a ata/resultado ser publicado em PNCP/Compras.gov (o campo `created` do item mostra a indexação, por vezes dias após a sessão). Para o "registro de resultado" não é tempo real.
9. **Pesquisa de Preços (IA) travada.** A tela e o POST de busca são restritos por flag do front (`alfa_tester` ou cliente 139359); só POST, sem GET equivalente. Não foi possível testar a resposta real. O mesmo dado básico (preço homologado por item) é obtido via `/mercado/results`, sem a normalização de unidade e sem remoção de outliers que a IA faz.
10. **Dados pessoais:** `/mercado/company` e fichas de órgão devolvem e-mail, telefone e sócios; o agente deve descartá-los. CNPJ e razão social podem ser usados.
11. **Sem cota explícita**, mas é uma sessão de usuário (cookie) com raspagem sobre uma API privada do front: risco de bloqueio, mudança de contrato do JSON sem aviso e eventual violação de termos de uso. Manter ritmo baixo (pausa de 1s) e cache local.
12. **Efeitos colaterais a evitar:** `POST /price_intelligence/saved`, `POST/DELETE /gestao_ia/*`, `POST /gestao_ia/.../interesses` e qualquer endpoint de monitoramento/alerta alteram a conta. Nenhum foi chamado.

## 5. Receita sugerida (item de preço com vencedor)
1. `GET /mercado/results?page=1&filter_id=44760&interval=24&item_input=<frase>&exact_search=true`; ler `lista_resultados.total` e paginar até esgotar.
2. Para cada `licitacao.resultados[]`, manter só itens cuja `item_descricao` contém os termos exigidos; descartar serviços, acessórios e linhas sem valor.
3. Normalizar unidade e qtd; guardar `item_valor_unitario`, `data_validade_licitacao`, `orgao.estado`, `modalidade_sigla`, `fornecedor`, `cnpj`, `licitacao.id`.
4. Calcular mediana, p25, p75 e vencedores mais frequentes (agrupar por CNPJ).
5. Para deságio, cruzar com `GET /contracts/search?objeto=<frase>&exact_search=true&state[]=<id>` e calcular `valor_contratado / valor_estimado` apenas onde `valor_estimado > 0` e há um só contrato.
6. Para atas do objeto: `GET /price_register/search?objeto=<frase>&exact_search=true`, guardar `url_ata` e vigência.
