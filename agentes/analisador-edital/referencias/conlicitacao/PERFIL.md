# Perfil — ConLicitação

Assinatura de licitações da REALMAK (até 2028-07-23). É a principal fonte externa do agente, ao lado do mcp-brasil (PNCP, Compras.gov.br) e das referências internas. Mapeado em 2026-10-15, **somente leitura**, por três subagentes; o detalhe está nos arquivos `ACHADOS-*.md` desta pasta.

## 1. Acesso

| Canal | Para quê | Como |
|---|---|---|
| **API oficial** (token `x-auth-token`, IPs liberados) | Boletins: chegada das licitações ao CRM (`/api/filtros`, `/api/filtro/{id}/boletins`, `/api/boletim/{id}`) | Já usada pelo realmak-crm (`scripts/conlicitacao.py`). Documentação oficial: PDF `/docs/documentacao-api-conlicitacao.pdf` no site (não lido). |
| **Site** (`https://consultaonline.conlicitacao.com.br`, sessão por cookie `_boletim_web_session`) | Tudo o mais: mercado, concorrentes, contratos, atas, resumo IA, estratégicas | Utilitário [cl.py](cl.py): `python3 cl.py GET "/rota?param=1"` ou `from cl import get_json`. Login com as credenciais do `.env` do realmak-crm, cookie em `~/.cache/agente-precificacao/` (chmod 600). |

- Empresa autorizada (`companyId`): **30933**. Filtro salvo (`filter_id`): **44760**, com atividades 0201 (manutenção predial), 0204 (ar-condicionado), 0408 (câmaras frigoríficas e cozinha industrial), 1203 (exaustão), 2206 (raio X e radiológicos), 2401.
- Contratados: Gerenciar Documentos, Monitorar Chat, Dr. Licita, ConLicita Go. **Não contratados:** Robô de Lance, Assinatura Digital.
- Para automação duradoura, preferir o token oficial (o site aceita `access_token` em `/biddings.json`) em vez do login por cookie. Formato a confirmar no PDF.

## 2. Regras de uso

1. **Somente GET.** Toda escrita (POST, PUT, PATCH, DELETE) altera a conta da empresa: favoritar, criar card/tarefa/comentário, salvar pesquisa, perguntar ao chat, rodar análise personalizada, enviar documento, dar lance. **Só com aprovação humana, caso a caso.**
2. **Rota com efeito colateral num GET:** `/chatbots/bidding_chat/bidding_user_chats` cria o chat da licitação ao ser lida (get-or-create). Bloqueada no `cl.py`. *Ocorrência registrada:* no mapeamento de 2026-10-15 criou um chat vazio da licitação 19482164 (id 777314, sem mensagens).
3. **Credenciais e tokens nunca aparecem** em relatório, log ou saída (incluindo `/conlicitacao_api/meus_tokens`).
4. **Dados pessoais:** não persistir sócios, CPFs, e-mails e telefones de pessoas (vêm em `/mercado/company`, `/get_company_data` e contatos de órgão). Razão social e CNPJ de empresas podem.
5. **Ritmo:** pausa de ~1 s entre chamadas e cache local. É uma API privada do frontend: o formato pode mudar sem aviso.
6. **Origem rotulada:** dado do ConLicitação entra no relatório como `ConLicitação (rota, data da consulta)`. O resumo IA é indício: conferir o trecho do edital que ele cita.

## 3. O que usar em cada skill

| Skill | Rotas | O que dá |
|---|---|---|
| **pasta-licitacao** | `/biddings/{id}.json` | Itens (`itens_json`, com quantidade e valor estimado), órgão/UASG, edital, link do portal, `contracts[]` após a disputa |
| **analisar-edital** | Resumo IA (`bidding_summary`): **baixado uma vez pelo CRM**, lido do arquivo `resumo_conlicitacao.json` da pasta (pasta-licitacao, passo 2). O agente só chama essa rota se o CRM não tiver o resumo (uma vez, com aviso). É sugestão externa, sem conhecimento estratégico da Realmak | **Resumo IA com 47 campos e trecho do edital**: prazos (impugnação, esclarecimento, recurso), garantias, amostra, visita, atestados, documentos de habilitação, ME/EPP, margem de preferência, `possibilidades_questionamentos` (base para esclarecimento) |
| | `/gestao_ia/licitacoes/{id}/tarefas/recomendadas` | Cronograma sugerido até a sessão (funciona sem card) |
| | `/bidding_desert/imminence?has_low_competition=true` (e `has_imminence`, `has_desert`, `/search`) | **Nº de propostas por item** e itens com baixa concorrência, desertos ou fracassados |
| | `/biddings.json` | Busca por objeto, itens, UF, modalidade, prazo, atividade (20 por página) |
| **precificar-proposta-exequibilidade** · **analisar-edital-fornecimento** (referência de compra pública) | `/mercado/results?advanced_search=true&exact_search=true&item_input=<frase>&interval=24&states[]=<id>` | **Preço unitário homologado por item, com vencedor e CNPJ** (10 licitações por página; filtrar o item no cliente) |
| | `/contracts/search?objeto=<frase>&exact_search=true&state[]=<id>` | Valor estimado × contratado por licitação |
| **analise-tecnica** | Resumo IA do arquivo da pasta, sugestão externa (`exigencias_especificas`, `atestado_capacidade_tecnica`, `exigencia_amostra`, `exigencia_prova_conceito`, `possibilidades_questionamentos`) | Exigências com trecho do edital. A especificação fina continua no TR (edital) |
| | `/strategic_aspects/{cnpj}` | Por que concorrentes foram desclassificados ou inabilitados (riscos a evitar) |
| **cotacao-fornecedor** | `/mercado/results` + `/get_company_data?cnpj=` | Quem já vendeu o item, a que preço, e se é fabricante ou revendedor (CNAE, porte, situação) |
| | ConlicitaSeg (`/conlicitaseg/insurance_quotes`) | Cotação de seguro-garantia (só por POST: com aprovação) |
| **precificar-proposta-exequibilidade** (mercado, sem item próprio desde 16/11/2026) | `/mercado/results` (agregar por CNPJ) | Quem vence o objeto na região e a que preço |
| | `/participants/{cnpj}` | Participações, vitórias, taxa, UFs e modalidades; `valor_final` dos itens perdidos (provável último lance, a confirmar) |
| | `/get_company_data?cnpj=` | Porte ME/EPP/DEMAIS, CNAEs, capital, UF |
| | `/strategic_aspects/{cnpj}` | Desclassificações e motivos |
| | `/contracts/search` | Deságio por licitação: `1 − contratado/estimado` (excluir estimado 0 e contratos parciais) |
| | `/mercado/search_buyers.json` | Órgãos que mais compram o objeto |
| **precificacao** | Resumo IA do arquivo da pasta, sugestão externa (`criterio_de_julgamento`, `modo_disputa`, `intervalo_minimo`, `exigencias_proposta_comercial`, `condicoes_pagamento`, `garantias`) | Regras e custos que entram no preço |
| | `/contracts/search`, `/participants/{cnpj}` | Deságio típico e onde concorrentes param |
| **registro de resultado** (futura) | `/my_history?filtro=winner|lost|...`, `/participants/03496338000174`, `/mercado/get_result_bidding.json?bidding_id=`, `/biddings/{id}.json` (`contracts`) | Nossos resultados (692 participações, 37 vitórias), preço dos vencedores, contratos |

## 4. Limitações que mudam a leitura

- **Sem lance a lance** e sem lista completa de participantes. Há só o preço do vencedor por item, o `valor_final` por participante em `/participants` (só Compras.gov.br) e o nº de propostas em `bidding_desert`.
- **Cobertura parcial** de `/mercado/results`: para a própria REALMAK achou 2 licitações contra 37 vitórias no `/my_history`. Não é o universo.
- **Busca:** `advanced_search=true` obrigatório; `exact_search=true` é literal (variações de frase zeram); o filtro casa a licitação inteira, então filtrar `item_descricao` no cliente. UF: `states[]` no mercado (com `advanced_search`), `state[]` em contratos.
- **Dados sujos:** outliers (quantidade lida como preço, bilhões fantasmas), `valor_estimado = 0` frequente, marca/modelo nulos, unidades em texto livre, itens globais (ex.: R$ 265 mil "serviços") que distorcem a mediana.
- **Paginação:** 10 por página no mercado, 20 em busca/contratos/atas; páginas muito fundas dão erro 500.
- **Atas** (`/price_register/search`) só trazem metadados e o PDF no PNCP, sem preço.
- **Travados para esta conta:** Pesquisa de Preços com IA (`/price_intelligence/search`, POST, base de 12,6 milhões de preços; tela liberada só para perfis de teste) e o histórico de contratação do órgão (exige a licitação como card na Gestão IA, criado por POST).
- **Vazios hoje:** Gestão IA (0 cards) e Gerenciar Documentos (0 documentos). Se a empresa cadastrar as certidões lá, o site cruza automaticamente exigências × documentos com vencimento.

## 5. Decisões

| Data | Decisão | Por |
|---|---|---|
| 2026-10-15 | Uso do ConLicitação com as credenciais do realmak-crm autorizado, para varredura e uso pelas skills. | Ennio |
| 2026-10-15 | Resumo IA: só o CRM baixa (uma vez); o agente lê o arquivo da pasta; sem ele, baixa uma vez com aviso. É sugestão externa. Ver pasta-licitacao DECISOES #8 e #9. | Ennio |
| 2026-10-15 | Uso somente leitura; escrita na conta só com aprovação humana caso a caso; rota `bidding_user_chats` bloqueada. | Claude (a confirmar) |

## 6. Em aberto

- [ ] Ler o PDF da API oficial e decidir se o agente usa token em vez de cookie.
- [ ] Liberar ou não, com aprovação, as rotas por POST de maior valor: Pesquisa de Preços com IA e criação de card na Gestão IA (destrava o histórico de contratação do órgão e o cruzamento de documentos).
- [ ] Apagar ou manter o chat vazio criado na licitação 19482164 (id 777314).
