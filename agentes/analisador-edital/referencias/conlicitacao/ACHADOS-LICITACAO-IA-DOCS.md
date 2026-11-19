# ConLicitação: licitação, IA e documentos (mapeamento somente leitura)

Data do teste: 2026-10-15. Empresa autorizada (companyId): 30933 (REALMAK). Todas as chamadas foram GET via `cl.py`, em torno de 75 requisições com pausa de 1 s. Nenhum token, cookie, CPF, telefone ou e-mail de pessoa foi copiado para este relatório.

Convenção: API = `https://consultaonline.conlicitacao.com.br` (sessão por cookie). "Bundle" = só descrito pelo JS, não chamado.

---

## 1. Tabela de endpoints testados

| Rota (GET) | Status | Para quê |
|---|---|---|
| `/biddings/{id}.json` | 200 | Detalhe cru da licitação: órgão, itens, valor, datas, edital (zip), situação. Base da pasta-licitação. |
| `/biddings.json?companyId=30933&...` | 200 | Busca com filtros (objeto, UF, modalidade, prazo, valor, favoritos...). 20 por página. Base da triagem. |
| `/chatbots/bidding_chat/bidding_summary?conlicitacao_id={id}` | 200 | Resumo IA estruturado do edital (47 campos). O endpoint mais valioso para triagem e adequação técnica. |
| `/chatbots/bidding_chat/user_saved_questions` | 200 | Perguntas salvas pelo usuário para o "Pergunte ao Edital". Retornou `[]` (conta sem perguntas). |
| `/chatbots/bidding_chat/bidding_user_chats?conlicitacao_id={id}` | 200 | Devolve o "chat" (thread) da licitação. Atenção: ver risco 4.7, parece criar a linha ao consultar. |
| `/resumo-licitacao?bidding_id={id}` | 200 | Resumo de acompanhamento (situação atual, tarefas, andamentos, anotações). Vazio se não há gestão. |
| `/biddings_overview?companyId=30933` | 200 | Totais gerais: 10.505 licitações futuras, 522 hoje, contagem por UF. |
| `/bidding/{id}` | 404 | Detalhe "expirado" (só licitações vencidas; não serve para licitações abertas). |
| `/painel.json?companyId=30933` | 200 | Módulos contratados (`validate_services`), atalhos de ferramentas, vigência da assinatura. |
| `/companies_activities` | 200 | Atividades (códigos CNAE/ConLicitação) cadastradas para a empresa; entram no filtro `atividade`. |
| `/gestao_ia/colunas` | 200 | Quadro Kanban da Gestão IA (7 colunas fixas). Vazio. |
| `/gestao_ia/cards` | 200 | Cards do quadro agrupados por coluna. Vazio (`{"cards":{}}`). |
| `/gestao_ia/cards/arquivadas` | 200 | Cards arquivados. `[]`. |
| `/gestao_ia/atualizacoes` e `/gestao_ia/atualizacoes/nao_lidas` | 200 | Feed de atualizações das licitações no quadro. Vazio. |
| `/gestao_ia/equipe` | 200 | Membros da equipe elegíveis (12 pessoas, só id/nome/iniciais). |
| `/gestao_ia/analise_personalizada` | 200 | Prompt personalizado da empresa para a análise IA. `{"analysis_prompt": null}`. |
| `/gestao_ia/licitacoes/{id}/tarefas/recomendadas` | 200 | Cronograma sugerido (12 tarefas com início/prazo calculados da sessão pública). Funcionou mesmo sem card. |
| `/gestao_ia/licitacoes/{id}/perguntas_estrategicas` | 404 | Só existe para licitação com card no quadro. |
| `/gestao_ia/licitacoes/{id}/historico_contratacoes` (+ `/licitacoes`) | 404 | Só com card. Histórico de contratações do item (preço mediano/médio). |
| `/gestao_ia/licitacoes/{id}/arquivos` | 404 | Só com card. |
| `/gestao_ia/licitacoes/{id}/exigencias_documentos` | 404 | Só com card. Checklist de habilitação com "Analista de Habilitação" IA. |
| `/gestao_ia/licitacoes/{id}/gerenciar_documentos` | 404 | Só com card. Catálogo do Gerenciar Documentos casado com a licitação. |
| `/documentos/count_documents?companyId=30933` | 200 | Contagem de documentos: `total_documentos: 0`. |
| `/document_groups.json` | 200 | 5 grupos de documentos de habilitação. |
| `/documentos.json?companyId=30933` | 500 | Listagem de documentos. Falha sem `cnpj` (o front sempre manda `cnpj`). Não testado com CNPJ. |
| `/gerenciar_licitacoes/resumo.json?scope=mine&companyId=30933` | 200 | Contadores: 43 favoritas, 3 gerenciadas, tarefas, andamentos. |
| `/gerenciar_licitacoes/gerenciar.json?scope=all&companyId=30933&page=1` | 200 | Licitações em gestão (3). |
| `/gerenciar_licitacoes/tarefas.json?scope=all&companyId=30933&page=1` | 200 | Tarefas (1, de teste, já concluída). |
| `/gerenciar_licitacoes/andamentos.json?scope=all&companyId=30933&page=1` | 200 | Andamentos/notificações de publicação (2). |
| `/gerenciar_licitacoes/finalizadas.json?scope=all&companyId=30933&page=1` | 200 | Licitações finalizadas com resultado. Vazio (0). |
| `/gerenciar_licitacoes/calendario.json?scope=all&companyId=30933&start=..&end=..` | 200 | Calendário de prazos, tarefas e andamentos (`types`: biddings, tasks, progress). |
| `/biddings.json?...&favorite=true&favorite_scope=...` | 200 | Favoritas: sem `favorite_scope` = 43 (as do usuário); `client` = 182 (da empresa); `mine`/`by_me`/`by_all` = 0. |
| `/custom_searches?companyId=30933` | 204 | Buscas salvas. Sem conteúdo (conta sem buscas salvas). |
| `/bidding_desert/imminence?has_imminence=true&page=1&companyId=30933` | 200 | "Licitações Estratégicas": itens com baixa/nenhuma concorrência. Ver seção 2.8. |
| `/tools_status.json` | 200 | Saúde de 135 fontes/portais/ferramentas. Todas `operational` hoje. |
| `/conlicitacao_api/meus_tokens` | 200 | Só confirma que existe `api_token` + lista de 4 IPs liberados. Valores não copiados. |
| `/conlicitacao_api/solicitacoes/status` | 200 | `{}` (sem solicitação de API em aberto). |
| `/boletim_web/public/boletins.json?companyId=30933` | 401 | Não acessível com a sessão atual (boletins = filtros salvos). Não insistido. |

Rotas só por POST/PUT/PATCH/DELETE (descritas pelo bundle, não chamadas) estão na seção 2.12.

---

## 2. Detalhe dos endpoints úteis

### 2.1 Detalhe da licitação: `GET /biddings/{id}.json`
Parâmetro opcional `?companyId=30933` (o front manda). Exemplo real: 19482164 (MPM, VRF Hitachi) e 19478221 (DEPEN, scanner raio X).

Campos principais (todos confirmados nas duas licitações):

| Campo | Significado |
|---|---|
| `id` / `bidding_id` | ID ConLicitação (CNL). |
| `edital` | Número do edital (ex.: `PE/101/2026`). `processo` = nº do processo administrativo. |
| `orgao_uasg`, `orgao_cidade`, `orgao_estado`, `orgao_endereco`, `orgao_cep` | Comprador. `public_body.{id,nome,tipo_orgao_id}` = órgão com hierarquia completa no nome; `tipo_orgao_id`: 1 Municipal, 2 Estadual, 3 Federal, 4 Distrital, 5 Privado, 6 Estatal. |
| `modality.nome` | Modalidade (Pregão Eletrônico etc.). |
| `objeto` | Objeto em texto. Prefixos como `* Registro de preços *` e `* Licitação Eletrônica *` indicam SRP e eletrônica. Na busca vem com `<mark class="bidding-keyword">`: limpar o HTML. |
| `itens` | Texto único concatenado com todos os itens ("1 - descrição... 2 - ..."). Pode ter milhares de caracteres (1.505 no caso do scanner). |
| `itens_json[]` | Itens estruturados: `numero_item`, `numero_lote`, `descricao` (inclui a especificação técnica), `unidade`, `quantidade`, `valor_unitario` (estimado pelo órgão), `valor_total`, `exclusividade` (ME/EPP "SIM/NÃO"), `valor_estimado` (quase sempre 0; usar `valor_unitario`/`valor_total`). |
| `valor_estimado` | Valor global estimado. 0.0 quando o órgão não informa (orçamento sigiloso ou não publicado). 219.027,56 no VRF; 108.068.040,00 no scanner. |
| `datahora_prazo` | Prazo/sessão (ISO com fuso). `data_validade` = só a data. Outros: `datahora_abertura`, `datahora_retirada`, `datahora_visita`, `datahora_documento` (null nestes casos). |
| `created`, `modified` | Quando entrou na base e quando foi alterado (útil para detectar retificação). |
| `edital_site` | Link do edital no PNCP. `edital_homepage1/2`, `edital_tem` (há edital baixável), `edital_preco`. |
| `edicts[]` | Arquivos do edital: `filename` (`edital.zip`) e `url` relativa (`/boletim_web/public/licitacoes/{id}/arquivos/edital.zip`). Download não executado (exige autorização). |
| `status_bidding_info[]` | Situação no portal: `status_name` ("Publicada/Divulgada"), `url_portal` (link direto da compra no Compras.gov.br), `expiration_date`. |
| `bidding_grouping.descricao` / `edital_status_id` | Situação da licitação: 3 NOVA, 7 ALTERADA, 8 REABERTURA, 5 ADIADA, 10 ADIADA SINE DIE, 14 ANULADA, 11 CANCELADA, 6 PRORROGADA, 4 RETIFICAÇÃO, 13 REVOGADA, 12 SUSPENSA, 9 SUSPENSA SINE DIE, 1 URGENTE, 2 RETRANSMITIDA, 15 LEILÃO. |
| `electronic_trading` | Dados do pregão eletrônico (`trading_id` PNCP, `uasg`, `source_id`; na busca vem também `promoter`). `has_electronic_trading` indica se a sala é monitorada. |
| `garantia_proposta`, `garantia_contrato` | Booleano ou null (null = não classificado). |
| `observacao` | Texto da fonte: data de atualização, unidade compradora, Id contratação PNCP, fonte (Compras.gov.br). |
| `has_summary`, `indexed_for_ai` | Indicam se o resumo IA existe/foi gerado (usar antes de chamar o summary). |
| `followups`, `managers`, `monitored_by_user`, `favorited`, `favorited_by`, `managed`, `client_comments`, `bidding_info`, `contracts`, `tasks` | Estado da licitação na conta (vazios nas duas licitações de teste). `contracts` traria contratos já assinados. |
| `phones`, `faxes`, `email` | Contato do órgão (vazio nestes casos). |

Exemplo curto (resposta resumida):
```json
{"id":19482164,"edital":"PE/101/2026","orgao_estado":"DF","valor_estimado":219027.56,
 "datahora_prazo":"2026-10-29T14:00:00.000-03:00","modality":{"nome":"Pregão Eletrônico"},
 "itens_json":[{"numero_item":1,"quantidade":1,"unidade":"UNIDADE","valor_unitario":219027.56}],
 "edicts":[{"filename":"edital.zip","url":"/boletim_web/public/licitacoes/19482164/arquivos/edital.zip"}],
 "has_summary":true,"indexed_for_ai":true}
```
Limite: o detalhe NÃO traz resultado/lances/vencedor, só edital e metadados. Itens podem ter `valor_unitario` 0 (valor sigiloso).

### 2.2 Busca: `GET /biddings.json`
Query string (nomes exatos usados pelo front; arrays via `chave[]=`):

| Parâmetro | Função |
|---|---|
| `companyId` | Empresa (30933). Também define o escopo. |
| `objeto` | Palavra/expressão no objeto. Sem `exact_search`, aceita variações (a busca por "ar condicionado" trouxe também "Ares-Condicionados", splits); com `exact_search=true` caiu de 19 para 18 resultados. |
| `itens` | Texto nos itens (descrição técnica). |
| `observacao`, `nome_orgao`, `processo`, `orgao_uasg`, `notice_number`, `id` | Nota, nome do órgão, nº do processo, UASG, nº do edital, ID exato (`id=19478221` retornou 1). |
| `orgao_estado_id[]` | IDs de UF: DF 7, GO 9, MS 12, MT 13, AL 2, BA 5, CE 6, MA 10, PB 15, PE 16, PI 17, RN 20, SE 25, AC 1, AM 3, AP 4, PA 14, RO 21, RR 22, TO 27, ES 8, MG 11, RJ 19, SP 26, PR 18, RS 23, SC 24. |
| `cities_ids[]` | IDs de município (via `/cities.json`, não testado). Acima de 500 cidades o front troca para POST. |
| `tipo_orgao_id[]` | 1 Municipal, 2 Estadual, 3 Federal, 4 Distrital, 5 Privado, 6 Estatais. |
| `modalities_ids[]` | 1 Audiência Pública, 2 Compra Eletrônica, 3 Coleta de Preços, 4 Concorrência, 5 Convite Shopping, 6 Convite, 7 Dispensa, 8 Leilão, 9 Sem Modalidade, 10 Pregão Eletrônico, 11 Pregão Presencial, 12 RDC, 13 Tomada de Preço. |
| `tipo_agrupamento_id` | Situação (lista na seção 2.1). |
| `data_validade[from]` / `[to]` | Faixa de prazo da proposta/sessão (testado: `2026-10-16` a `2026-11-30`). |
| `modified[from]` / `[to]` | Faixa de data de inclusão/alteração. |
| `vigente_somente=true` | Só licitações ainda em vigência (prazo não vencido). |
| `tem_edital=true` | Só as com edital disponível. |
| `pregao_tem=true`, `pregao_fonte_id[]` | Só as monitoradas em portal (Monitorar Chat) e quais portais. |
| `match_somente=true` | Só as que casam com o perfil/atividades da empresa. |
| `atividade[]` | Códigos de atividade (`codigo` de `/companies_activities`, ex.: `0201`). Padrão: atividades da empresa. |
| `ranges[]` | `0` nacional, `1` internacional. |
| `favorite`, `favorite_scope`, `managed`, `archived` | Estado na conta (ver tabela da seção 1). |
| `order` (valores vistos: `modified`), `order_direction` (`asc`/`desc`) | Ordenação. |
| `page` | Página. Tamanho fixo de 20; `per_page` é aceito pelo front mas NÃO alterou o tamanho nos testes (68 resultados = 4 páginas). |
| `access_token` | O front aceita token de API no lugar da sessão (ver 2.11). Não testado. |

Resposta: `{tasks_counter, total_entries, total_pages, page, biddings:[...]}`. Cada elemento é o detalhe da licitação (seção 2.1) acrescido de `public_body.tipo_orgao_id`, `public_body.tem_capag`, `monitors`, `gestao{managing,members}`, `total_managed_opened_tasks`, `has_requested_edital`.

Valores medidos: "scanner" vigente com edital e prazo 16/10 a 30/11, Brasil inteiro = 68 licitações; "ar condicionado" vigente no DF = 19. Sem filtro de valor mínimo/máximo no front: filtrar `valor_estimado` do lado do cliente.

### 2.3 Resumo IA: `GET /chatbots/bidding_chat/bidding_summary?conlicitacao_id={id}`
Resposta: `{"summary": {...}}` com 47 campos, gerado por IA a partir do edital (`resumo_criado_em`). Funciona para qualquer licitação com `has_summary=true`, mesmo sem estar favoritada/gerenciada (testado nas duas). Campos:

- Identificação: `numero_licitacao`, `numero_processo`, `uasg`, `portal_realizacao`, `tipo_contratacao`, `orgao_responsavel`, `orgao_endereco`, `orgao_cnpj`, `emails` (do órgão), `telefone_orgao`, `agente_contratacao`.
- Disputa: `data_sessao_publica`, `horario_sessao_publica`, `modo_disputa` (ex.: "Aberto e Fechado"), `criterio_de_julgamento` ("MENOR PREÇO"), `intervalo_minimo` (diferença mínima entre lances), `valor_estimado_licitacao`, `valor_estimado_observacao`.
- Preferências: `margem_de_preferencia`, `preferencia_de_me_epp` ("Parcial"), `restricoes_regionalidade`, `programa_integridade`.
- Execução: `prazo_de_entrega`, `data_entrega_execucao`, `local_entrega_execucao`, `condicoes_pagamento`.
- Exigências com flag de risco: `exigencia_de_visita_tecnica` ("Facultativa"), `exigencia_amostra` ("Exige" no scanner, "Não mencionado" no VRF), `exigencia_prova_conceito`.
- `legislacao[]`: lista de leis/normas citadas.
- `prazos_importantes{}`: `limite_envio_propostas`, `limite_impugnacao`, `prazo_esclarecimentos`, `prazo_manifestacao_recurso`, `prazo_recursos_contrarrazoes`, `prazo_envio_doc_complementar`, `prazo_envio_doc_original`, `prazo_contratual_ou_arp`, `prazo_vigencia_contrato_ata`, `tipo_fornecimento`.
- `criterios_proposta_julgamento{}`: `validade_proposta`, `exigencias_proposta_comercial` (o que a planilha de proposta deve conter, inclusive BDI), `criterios_desempate`.
- `resumo_itens_licitados{}`: `total_itens`, `categorias_principais[]`, `descricao_geral`.
- `penalidades_multas[]`, `outras_informacoes_relevantes[]`.
- `analise_critica{}`: `permite_subcontratacao`, `previsao_reajuste_repactuacao`, `permite_renovacao_contrato`, `estabelece_condicoes_pagamento`, `conflito_objeto_minuta`, `conflito_prazo_vigencia_arp`, `conflito_prazos_entrega`.
- `possibilidades_questionamentos[]`: `{tema, tipo, existe_irregularidade, justificativa, trecho_edital}` (base para esclarecimento/impugnação). O VRF retornou 4, p.ex. exigência de vínculo com profissional na habilitação.
- `garantias{}`: `garantia_proposta`, `garantia_contrato`, `garantia_adicional`, `garantia_retomada`, `seguro_garantia` (booleanos) + `justificativa_*` com a cláusula. Scanner: garantia contratual 10%, aceita seguro-garantia.
- `exigencias_especificas{}`: dicionário por área (ex.: `"Saúde": [...]`). No scanner trouxe: atestado de capacidade operacional (item 9.33), amostra funcional (4.2), autorização da CNEN para comercializar (8.8.7), assistência técnica autorizada pela CNEN (8.9.1/8.9.2), documentação técnica e certificados de conformidade.
- `documentos_habilitacao[]` (18 no VRF, 25 no scanner): `{documento, trecho_edital, confianca}`.
- `anexos_declaracoes[]` (7 no VRF): modelos/declarações exigidos, mesmo formato.
- `atestado_capacidade_tecnica[]`: exigência de atestado técnico (qual parcela de maior relevância, quantidade mínima), mesmo formato.
- `compliance{}`: `exige_compliance`, `natureza_exigencia`, `incidencia_legal`, `ente_incidencia`, `trechos_relevantes`.

Exemplo (recorte):
```json
{"summary":{"modo_disputa":"Aberto e Fechado","criterio_de_julgamento":"MENOR PREÇO",
 "exigencia_amostra":"Exige","garantias":{"garantia_contrato":true,"seguro_garantia":true},
 "atestado_capacidade_tecnica":[{"documento":"Atestado de capacidade operacional ... mínimo 1 unidade","trecho_edital":"9.33. ...","confianca":"alta"}],
 "documentos_habilitacao":[{"documento":"Comprovante de inscrição no CNPJ","trecho_edital":"a) ...","confianca":"alta"}]}}
```
Limites: é leitura de IA, cada campo tem trecho do edital para conferência; campos podem vir vazios ("") ou "Não mencionado". O resumo NÃO inclui as especificações técnicas detalhadas do Termo de Referência (só cita exigências específicas); para adequação técnica fina é preciso o edital/TR (zip) ou os `itens_json[].descricao`.

### 2.4 Pergunte ao Edital (chat IA)
- `GET /chatbots/bidding_chat/user_saved_questions`: lista perguntas salvas (hoje `[]`). Escrita (bundle): `POST` cria, `PATCH /{id}` edita.
- `GET /chatbots/bidding_chat/bidding_user_chats?conlicitacao_id={id}` devolve `{id, usuario_id, conlicitacao_id, thread_id, created_at}`. `thread_id: null` = ainda sem conversa.
- Mensagens (bundle): `GET/POST /chatbots/bidding_chat/bidding_user_chat_messages` (POST é a pergunta ao chat; NÃO chamado). Há também `chatbots/bulletin_ia_chat/messages`, `chatbots/chatbot_assistant/*` (assistente com áudio/TTS) e `chatbots/central_ia/*` (Central IA: chats, pastas, arquivos, imagens, biblioteca de prompts e especialistas).
Uso para o agente: perguntas livres ao edital só por POST; para leitura automática use o `bidding_summary`.

### 2.5 Gestão IA (`/gestao_ia/*`)
É um Kanban de licitações com IA. Colunas fixas lidas em `/gestao_ia/colunas`: 130 Analisar, 131 Participar, 132 Preparando Proposta, 133 Aguardando Disputa, 134 Em Disputa, 135 Aguardando Resultado, 136 Finalizadas; `board.id` 39. Cada coluna tem `cards_count`, `wip_limit`, `color`, `permissions`. Filtros de cards/colunas: `scope=mine`, `member_ids`, `q`, `deadline_from`, `deadline_to`. Hoje o quadro da REALMAK está vazio (0 cards), por isso as rotas por licitação abaixo responderam 404.

Por licitação (só funcionam depois que a licitação vira card: `POST /gestao_ia/cards {bidding_id}`, não executado):

| Rota | O que faz |
|---|---|
| `GET /gestao_ia/licitacoes/{id}/tarefas/recomendadas` | TESTADO sem card. Cronograma sugerido a partir da sessão: Analisar edital, Enviar esclarecimento, Protocolar impugnação, Cadastro/credenciamento, Elaborar proposta, Revisar proposta, Preparar estratégia de disputa, Separar documentos, Revisar documentos, Cadastrar proposta/documentos, Participar da sessão, Acompanhar resultado. Cada uma com `start_on`, `deadline_on`, `deadline_time`. Também devolve `exigencia_amostra`, `garantia_proposta`. |
| `GET /gestao_ia/licitacoes/{id}/perguntas_estrategicas` | Perguntas estratégicas geradas por IA (404 sem card). |
| `GET /gestao_ia/licitacoes/{id}/historico_contratacoes` (`?page&per_page&q`), `/licitacoes?item=`, `/detalhe?bidding=&item=`, `/ocorrencias?bidding=`, `/ocorrencias/arquivos` | "Histórico da Contratação": contratações anteriores de itens semelhantes (campos vistos no front: `valor_medio`, `valor_mediano`, `item_descricao`, `item_quantidade`, `item_valor_unitario`, `item_valor_total`, `orgao`, `cnpj`, `ocorrencias`). Candidato forte para mapa de preço, mas só acessível com card. `POST/DELETE .../interesses` marca itens de interesse. |
| `GET /gestao_ia/licitacoes/{id}/exigencias_documentos` | "Preparar documentação": lista de exigências de habilitação extraída do edital, com status (pendente, em revisão, confirmado, ignorado), percentual de conclusão, `Compatibilidade` e `Vencimento` do documento casado. Um "Analista de Habilitação" IA procura no Gerenciar Documentos o arquivo que atende cada exigência; origens: "Adicionado no Gerenciar Documentos" ou "Coletado automaticamente pelo iDocumentei". Sub-rotas: `POST /analisar`, `PATCH /{req}/ignorar`, `/restaurar`, `POST /{req}/arquivos` (upload ou `document_id` para importar), `DELETE /{req}/arquivos/{arq}`. |
| `GET /gestao_ia/licitacoes/{id}/gerenciar_documentos` | Catálogo do Gerenciar Documentos para a licitação. |
| `GET /gestao_ia/licitacoes/{id}/arquivos` e `/arquivos/licitante` | Arquivos do edital e arquivos gerados pelo licitante (upload por `POST` multipart, máx. 50 MB). |
| `POST /gestao_ia/licitacoes/{id}/analise_personalizada` | Roda a análise IA com o prompt salvo da empresa (`force:true` regera). NÃO chamado. |
| `POST /gestao_ia/licitacoes/{id}/tarefas` e `/tarefas/lote` | Cria tarefas. NÃO chamado. |

Menu do card (bundle): Ferramentas gerais (Painel, Informações, Anotações, Arquivos do edital, Tarefas, Atualizações, Arquivos do licitante), Planejamento (Análise do Edital, Histórico da Contratação), Participação (Preparar documentação, Mensagens do chat, Cadastro de Proposta e Lances), Pós-vendas (Análise de Cláusulas Contratuais).

Outros: `GET /gestao_ia/tarefas/{id}` (detalhe com anotações e checklist), `POST /gestao_ia/tarefas/{id}/checklist`, `PATCH .../checklist/{item}` `{done}` (checklist de tarefa: cada item com `content` e `done`), `/gestao_ia/tarefas/{id}/anotacoes`, `PATCH /gestao_ia/cards/{id}/mover {column_id, after_card_id}`, `/cards/arquivar`, `/cards/restaurar`, `/cards/membros`, `/atualizacoes/{marcar_lidas|marcar_nao_lidas|excluir}`, `GET/POST /gestao_ia/analise_personalizada` (+ `/aprimorar` reescreve o prompt com IA).

### 2.6 Gerenciar Licitações (`/gerenciar_licitacoes/*` e `/minhas_licitacoes/*`)
Parâmetros comuns: `scope` (usado `mine` e `all`), `companyId`, `page`, `per_page`, `q`.
- `resumo.json`: `{total_favorites:43, total_managed:3, total_finished:{winner, partial_winner, lost, cancelled, failed, revoked, declined}, total_tasks:{late,today,future,finished}, total_progress:{read,unread}}`. Os status de finalização (ganha, parcial, perdida, cancelada, fracassada, revogada, declinada) mostram como o resultado é registrado.
- `gerenciar.json` (+ `date_filter`): licitações gerenciadas: `id, edital, tipo_agrupamento_id, datahora_prazo, data_validade, objeto, public_body.nome, managers[{user_id,name}], managed, managed_by_others, total_managed_opened_tasks`.
- `tarefas.json` (+ `deadline_filter`, `bidding_id`): `id, bidding_id, title, description, deadline, status_task_id, responsible_id, task_event_histories[], task_event_comments[], bidding_attachments[]`.
- `andamentos.json`: notificações de andamento ("Nova publicação" etc.) com `bidding_id`, `read`, `progress{title,description,...}`. Ótimo para detectar retificação/adiamento.
- `finalizadas.json` (+ `status_in`), `calendario.json` (`start`, `end`, `types`), `linha_do_tempo/{id}`, `resumo/{id}` (resumo por licitação), `anexos?biddingId=` (anexos de gestão), `configuracoes?client_id=`.
- Favoritos por `GET /biddings.json?favorite=true&...`. Escrita (bundle): `POST/DELETE /minhas_licitacoes/favorites`, `POST /minhas_licitacoes/viewed_biddings` (marca como visualizada), `/minhas_licitacoes/comments`, `/shares`, `/bidder_considerations` (observações do licitante: GET existe com `bidding_id`; `/team` lista a equipe).
- `GET /minhas_licitacoes/comments.json?bidding_id=` lista comentários.

### 2.7 Gerenciar Documentos (certidões e habilitação)
Sim, guarda documentos de habilitação com controle de validade, mas a conta REALMAK está sem nenhum documento (`count_documents` = 0) e o módulo aparece como "checked: False" nos atalhos do painel, embora `validate_services.gerenciar_documentos = true` (contratado).
- `GET /documentos.json?cnpj=&companyId=` com filtros `documentGroups`, `documentStatus`, `documentUpdateTypes`, `nameDescription`. Retornou 500 sem `cnpj` (não testamos com CNPJ para não ler credenciais/dados da conta).
- Grupos (`/document_groups.json`): 1 Habilitação Jurídica, 2 Regularidade Fiscal/Social/Trabalhista, 3 Qualificação Técnica, 4 Qualificação Econômico-Financeira, 5 Outros.
- Situação do documento (filtro): Disponível, Pendente, Coletando. Forma de atualização: Manual ou Automático (coleta automática de certidões, "iDocumentei"). Campo `data_vencimento` e avisos de vencimento ("Receba avisos de vencimento dos documentos"; "Certidões negativas vencidas").
- Operações (bundle): `POST /documentos/direct_post` (upload), `DELETE /documentos/delete_remote_file`, `GET /documentos/download?document_refs=` (baixa em blob), `GET /documentos/send_to_email`, `POST /authenticated_documents` (autenticação de documento), `GET /digital_signature_documents`. Catálogo de tipos inclui Certidão Negativa Simplificada, Certidão da Junta Comercial, Certidão de Débitos Estaduais, Certidão de Falências, entre outras.
- `Assessoria Cadastral` (`/assessoria_cadastral`) é página comercial de serviço (cadastro em SICAF, CRC e portais com validação de documentos). Não há endpoint de dados; é contratação de serviço humano.
- `Assinatura Digital`: serviço separado, não contratado (`validate_services.assinatura_digital=false`).

### 2.8 Licitações Estratégicas / iminência: `GET /bidding_desert/imminence`
Parâmetros: `has_imminence=true` (ou `has_low_competition=true`, `has_desert=true`), `page`, `companyId`. Busca: `/bidding_desert/imminence/search?objeto=&tipo_orgao_id=&estados_ids=&cidades_ids=&vigencia_inicio=&vigencia_fim=&page=`; por item: `/search_item?item=&states_ids=&stateImminence=&page=`.
Resposta: `{total_pages, total_rows, total_imminence:[{has_low_competition:147},{has_imminence:196},{has_desert:3043}], imminences:[...]}` (10 por página). Cada registro vem do Elasticsearch (`_source` com 46 campos: os mesmos da licitação mais `orgao_nome`, `valor_estimado`, `tipo_agrupamento_nome`) e traz `imminence.imminence_items[]` por item: `number_item`, `description_item` (especificação completa), `quantity`, `estimated_value`, `proposals` (quantas propostas já existem), `type_of_judgment`, `bidding_desert_imminence_situation` ("Iminência" = sem propostas perto do prazo; "Baixa concorrência" = poucas propostas; também "Deserto" em itens já desertos).
Uso: item-level com preço estimado e número de propostas, ótimo para achar oportunidades com pouca concorrência e como sinal de competição para a skill concorrência.

### 2.9 Perguntas/ferramentas auxiliares
- `GET /tools_status.json`: lista `{cache_name, tool_name, principal_tool, status, description, time}` de 135 ferramentas e portais (ComprasNet, Licitações-e, BLL, BNC, Licitanet, Compras RJ/AM/MT etc.). Todos `operational` hoje. Serve de verificação de saúde antes de confiar na base.
- `GET /biddings_overview`: total futuro, de hoje, por UF.
- `GET /painel.json`: `validate_services` (contratados): gerenciar_documentos true, monitorar_chat true, conlicitago true, dr_licita true, robo false, assinatura_digital false, course_iaml false. `days_to_end` 647 (assinatura até 23/07/2028). Lista dos 34 atalhos de ferramentas por categoria.
- `GET /my_history`, `/my_history/list_itens?bidding_id=` (bundle): histórico do que a empresa já pesquisou/participou, com filtros `filtro`, `startDate`, `endDate`. Não testado.
- `GET /custom_searches`: buscas salvas (204 = nenhuma). `POST/PUT/DELETE` criam/alteram. Persistem os mesmos filtros da busca.
- `GET /waranty_phrases` (frases de garantia, bundle).

### 2.10 Documentos jurídicos/IA (apenas bundle)
- Dr. Licita (`/dr_licita/*`, contratado): chats jurídicos, petições, jurisprudência, biblioteca, projetos, `documents_types`, `theses_keywords` (busca teses por palavras-chave), `generate_user_document_file`. Útil para impugnação/recurso, não para preço.
- Análise de Cláusulas Contratuais (`/contract_validations`, `/validar_contrato/criar`, `contract_validations/get_info_bidding`): IA lê o contrato (pós-venda).
- ConlicitaSeg (`/conlicitaseg/insurance_quotes`, `get_bidding_guarantee`): cotação de seguro-garantia e fiança, com `extract_contract`. Útil quando o edital exige garantia (como no scanner).

### 2.11 API ConLicitação (`/conlicitacao_api/*`)
- `GET /conlicitacao_api/meus_tokens` retorna `{api_token, ips:[{ip,status}]}`: a empresa já possui token e 4 IPs cadastrados (valores não reproduzidos aqui).
- `GET /conlicitacao_api/solicitacoes/status` (vazio) e `solicitacoes` (pedido de acesso, POST).
- Bundle: o front aceita `access_token` como parâmetro de `/biddings.json` e publica a documentação em `/docs/documentacao-api-conlicitacao.pdf` (no domínio do front, não baixado). Há um "questionário da API" em .docx gerado no front. Ou seja, existe caminho oficial por token + IP liberado para automação, alternativo à sessão por cookie. Os formatos exatos do token/endpoints oficiais só constam no PDF.

### 2.12 Robô de lance, dashboard e facilitadores (somente descrição, nada acionado)
- Robô de Lance Inteligente (`/robo_lance`, `/robot_dashboard/*`, `/robo_dashboard/{usuarios,online,licitacoes}`, `/facilitadores/robo`): robô que dá lances automáticos no pregão. Na conta: `robo_access: true`, mas `validate_services.robo = false` ("O Robô de Lances não faz parte da sua assinatura"). Só atende portais específicos (`beebeeate_portals` vazio para esta conta) e licitações elegíveis. Rotas: `/robot_dashboard/bidding_store.json`, `client_store.json`, `client_store_summary.json` (GET, painel de lances/loja) e o front tem "Cadastro de Proposta e Lances" dentro do card da Gestão IA. Não acionado.
- Monitorar Chat (`/facilitadores/monitoramento`, `electronics_trading.json` com `filtered_by` by_me/by_all, `trading_messages.json?electronic_trading_id=`, `appeals.json`, `appeals_progresses.json`, `monitoring_interest_lots.json`, `trading_keywords`, `conlicitantes`, `token_express`): acompanha o chat do pregoeiro em tempo real de mais de 300 portais (com alertas por palavra-chave), recursos e lotes de interesse. `validate_services.monitorar_chat = true`. Útil no acompanhamento de disputa e registro de resultado; os `GET` não foram testados por serem de monitoramento ativo.
- Gerenciar Portais (`/manager_portals`, `portals_expired`): credenciais/acessos a portais de pregão (não tocado).

---

## 3. O que serve para cada skill

| Skill | Endpoint(s) | Como usar |
|---|---|---|
| pasta-licitacao (entrada) | `/biddings/{id}.json` + `bidding_summary` + `edicts[].url` + `status_bidding_info[].url_portal` | Montar a pasta: identificação (órgão, UASG, edital, processo, PNCP), itens (`itens_json`), valor, prazo, link do edital zip e do portal, resumo IA como ficha. O zip do edital exige download autorizado (não feito). |
| triagem (prazo, valor, objeto, região, habilitação) | `/biddings.json` (filtros: `objeto`, `itens`, `orgao_estado_id[]`, `data_validade`, `vigente_somente`, `tem_edital`, `modalities_ids`, `atividade`, `match_somente`) + `bidding_summary` (`prazos_importantes`, `garantias`, `exigencia_amostra`, `exigencias_especificas`, `restricoes_regionalidade`, `preferencia_de_me_epp`, `documentos_habilitacao`, `atestado_capacidade_tecnica`) + `tarefas/recomendadas` (agenda) | Funil: buscar por palavra+UF+prazo, descartar por valor/situação no cliente, enriquecer com summary (amostra, garantia, atestado, CNEN etc.) e calcular dias até impugnação/proposta. `bidding_grouping`/`edital_status_id` detecta suspensa/revogada. `andamentos.json`/`modified` detecta alterações. |
| mapa de preço | `itens_json[].valor_unitario/valor_total/quantidade` da própria licitação (referência do órgão); `/bidding_desert/imminence` (estimado e nº de propostas por item); `historico_contratacoes` da Gestão IA (`valor_medio`, `valor_mediano`) quando o card existir | O ConLicitação aqui só dá o preço estimado do órgão e o histórico por item (via card). Preços praticados/adjudicados vêm do módulo Mercado/Análise de Preços (outra frente). |
| adequação técnica (requisitos × produto) | `itens_json[].descricao` (especificação do item) + `bidding_summary.exigencias_especificas`, `atestado_capacidade_tecnica`, `exigencia_amostra`, `exigencia_prova_conceito`, `anexos_declaracoes`, `possibilidades_questionamentos` | Extrair requisitos para cruzar com ficha do produto. Para detalhes finos (TR/anexos) é preciso baixar o `edital.zip`. O `trecho_edital` indica o item do edital citado. |
| cotação com fornecedor | `itens_json` (quantidade, unidade, descrição), `local_entrega_execucao`, `prazo_de_entrega`, `condicoes_pagamento`, `garantias`, `validade_proposta` do summary | Gera o pedido de cotação (o que, quanto, onde, até quando, com que garantia). ConlicitaSeg cota seguro-garantia. |
| concorrência | `/bidding_desert/imminence` (propostas por item), `status_bidding_info`, `electronic_trading`; Monitorar Chat (mensagens, recursos); rotas `/participants/`, `/concorrente/`, `/strategic_aspects/`, `/list_my_biddings/` (existem no bundle, são da frente de concorrentes) | Sinais de competição por item e acompanhamento da sala. Nomes dos concorrentes ficam no módulo Concorrentes. |
| precificação | `bidding_summary`: `criterio_de_julgamento`, `modo_disputa`, `intervalo_minimo`, `margem_de_preferencia`, `preferencia_de_me_epp`, `exigencias_proposta_comercial` (BDI, encargos), `previsao_reajuste_repactuacao`, `condicoes_pagamento`, `penalidades_multas`, `garantias` (custo de seguro-garantia) + `valor_estimado`/`itens_json` | Parâmetros que entram no custo e na estratégia de lance (teto = estimado, lance mínimo, tributos/BDI exigidos, prazo de pagamento, garantia). |
| registro de resultado | `/gerenciar_licitacoes/resumo.json` (`total_finished`: winner, partial_winner, lost, cancelled, failed, revoked, declined), `finalizadas.json` (+ `status_in`), `gerenciar.json`, `tarefas.json`, `andamentos.json`; escrita via UI/POST | O ConLicitação possui o registro de desfecho, mas por escrita (não feita). O agente deve guardar resultado em sua própria base e, se desejado, replicar via POST depois de autorização. |
| habilitação / pasta de documentos | `documentos.json` (com `cnpj`), `document_groups.json`, `count_documents`, `exigencias_documentos` (card) | Hoje vazio (0 documentos). Se a REALMAK carregar certidões com validade, o ConLicitação cruza com as exigências do edital (compatibilidade, vencimento). O agente pode manter a própria pasta e usar `documentos_habilitacao` do summary como checklist. |

Resumo: o par `GET /biddings.json` + `GET /chatbots/bidding_chat/bidding_summary` já cobre sozinho a maior parte de triagem, adequação, cotação e precificação. Gestão IA e Gerenciar Documentos só ficam úteis depois de cadastrar dados na conta (cards e documentos).

---

## 4. Limitações e riscos

1. Paginação: 20 por página fixo; `per_page` ignorado na busca. Total de 68 resultados já exige 4 chamadas.
2. Sem filtro de valor na busca: filtrar `valor_estimado` no cliente. `valor_estimado` e `valor_unitario` são 0 quando o órgão não divulga (ex.: 19486947 com 21 itens zerados).
3. HTML na busca: `objeto`/`itens` vêm com `<mark class="bidding-keyword" ...>`. Remover antes de processar.
4. Resumo IA: gerado por modelo; tratar campos como indícios e conferir `trecho_edital` e `confianca`. Nem toda licitação tem resumo (`has_summary`/`indexed_for_ai`; a busca mostrou 19486947 com `has_summary:false`). Não substitui o TR e os anexos para adequação técnica.
5. Gestão IA: tudo por licitação (`historico_contratacoes`, `exigencias_documentos`, `perguntas_estrategicas`, `arquivos`) dá 404 até a licitação virar card (`POST /gestao_ia/cards`). Só `tarefas/recomendadas` funciona sem card. O quadro e os documentos da REALMAK estão vazios, então não foi possível ver o formato real do histórico de preços nem das exigências.
6. `documentos.json` retorna 500 sem `cnpj`; formato da resposta não foi observado. Gerenciar Documentos tem 0 documentos.
7. Efeito colateral dos testes: `GET /chatbots/bidding_chat/bidding_user_chats?conlicitacao_id=19482164` devolveu uma linha de chat criada no instante da chamada (id 777314, `thread_id: null`, sem mensagens), ou seja, o GET parece criar o contêiner do chat da licitação (get-or-create). Não enviou pergunta nem alterou nada visível; fica a observação. Evitar essa rota em produção ou só chamá-la quando for perguntar.
8. Sessão por cookie e autenticação automática: `cl.py` refaz login sozinho em 401/403. Para automação duradoura, preferir o token de API oficial (`meus_tokens`, com IPs liberados), que o front já aceita como `access_token` em `/biddings.json`; formatos oficiais estão no PDF `/docs/documentacao-api-conlicitacao.pdf` (não baixado).
9. Não há resultado de disputa no detalhe: sem lances, vencedor ou preço final adjudicado. Esses dados ficam nos módulos Mercado, Concorrentes, Ata de Registro de Preços e Contratos (outras frentes).
10. Robô de lance não faz parte da assinatura (`robo` = false); nada foi acionado. Monitorar Chat está contratado.
11. Ações de escrita (POST/PATCH/DELETE) existem para favoritar, criar card/tarefa/comentário/busca salva, perguntar ao chat, rodar análise personalizada e fazer upload. Nenhuma foi executada. Qualquer uso futuro dessas rotas altera a conta da empresa e deve ser autorizado caso a caso.
12. Dado pessoal: respostas de equipe, gestores e contatos do órgão trazem nomes e e-mails de pessoas; o agente não deve persistir esses campos.
13. Download do edital (`/boletim_web/public/licitacoes/{id}/arquivos/edital.zip`) não foi feito (exige autorização). `POST /solicitar_edital` existe para licitações sem edital (`has_requested_edital`).
14. `/boletim_web/public/boletins.json` devolveu 401 com a sessão atual; os boletins (filtros salvos da empresa) podem exigir outro cookie/path. Não insistido.
