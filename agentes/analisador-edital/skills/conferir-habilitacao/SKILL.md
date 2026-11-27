---
name: conferir-habilitacao
description: Rechecagem manual de habilitação da empresa disputante comparando os documentos em DOCUMENTOS PARA DISPUTA, os novos envios da licitação e o Cérebro contra as exigências do edital.
---

# Conferir habilitação (rechecagem manual)

Refaça a conferência documental de habilitação **somente da empresa indicada no pedido**, sem refazer leitura do edital, análise técnica nem precificação.

## Entradas

1. `analise/edital.json` — exigências de habilitação e datas da licitação.
2. `analise/habilitacao.json` — análise anterior de habilitação (base a atualizar).
3. Pasta **DOCUMENTOS PARA DISPUTA** no Drive (caminho informado no pedido) — documentos novos adicionados pela equipe para a disputa (certidões emitidas, declarações assinadas, atestados, ARTs/CATs, comprovantes). Ignore arquivos `*.atalho-drive` e temporários (`~$*`, `.tmp-*`).
4. Textos extraídos de envios recentes na licitação (`extraidos/`).
5. Marcações do checklist **"A fazer"** feitas pela equipe no card (indicam quais itens a equipe já providenciou ou sinalizou).
6. Ferramentas do **Cérebro** (`cerebro_buscar`, `cerebro_fatos`, `cerebro_provas`) — para verificar se certidões, balanços, contratos ou atestados pendentes foram atualizados no `acervo-2.0` da empresa.

## Como conferir

1. Leia `analise/habilitacao.json` e localize o bloco da `empresa` solicitada dentro de `empresas[]`.
2. **Escopo por etapa (`etapa_envio`):** o pedido informa `etapa_envio`: `"sessao"` (**Para participar da sessão**), `"proposta"` (**Proposta**), `"habilitacao"` (**Para a habilitação**) ou `"todas"` (padrão).
   - Quando `etapa_envio` for `"sessao"`, `"proposta"` ou `"habilitacao"`, confira **somente os itens daquela etapa** (validade, assinaturas, nome da empresa, completude), preservando intactos os itens da outra etapa.
   - **Sem itens de ação manual no portal, em nenhuma etapa:** nunca crie item ou pendência para passo manual no portal (cadastrar proposta inicial, marcar declarações do sistema, clicar em enviar ou em "Enviar anexo"), seja em `"sessao"`, `"proposta"` ou `"habilitacao"`; item assim que já exista na análise, não o recrie nem o reative. Só entram documentos que a plataforma prepara ou confere.
   - **Sem códigos internos:** nunca escreva `H-xx`, `P-xx` ou `00 -` em motivos, ações, `conferencia` ou resumo. Escreva o motivo da falta em linguagem simples (ex.: `"Falta a assinatura de Fulano (p. 1, linha do RT)"`).
3. Liste todos os arquivos reais da pasta `DOCUMENTOS PARA DISPUTA` (se ela existir e tiver arquivos). Para PDFs, DOCX, XLSX e TXT adicionados pela equipe, leia o conteúdo (usando Python/bash com `fitz`/`pypdf`/`openpyxl` ou leitura direta) antes de concluir qualquer item.
4. Para cada exigência da empresa no escopo de `etapa_envio` que **não esteja `atende`, que tenha `acao` preenchida ou que seja registro legado sem `bloqueia`/`momento`/`risco_inabilitacao`/`etapa_envio`** (e também para qualquer exigência marcada como providenciada no checklist ou com validade próxima da data da sessão) — **preservando sempre qualquer classificação alterada manualmente por pessoa**:
   - Verifique primeiro se há documento correspondente em `DOCUMENTOS PARA DISPUTA/`.
   - Se ainda faltar ou precisar de complemento, faça busca direcionada no Cérebro (`cerebro_buscar` / `cerebro_fatos`) para aquela empresa e exigência específica.
   - Confira no texto real do documento:
     - **CNPJ e razão social** compatíveis com a empresa disputante;
     - **Emissão e validade** frente à data atual e à data da sessão/envio da proposta, só para documento que vence (certidões, registro no conselho, balanço);
     - **Sem prazo de validade:** Atestado de capacidade técnica, CAT (Certidão de Acervo Técnico), CAO (Certidão de Acervo Operacional), ART, TRT, RRT, ato constitutivo, cartão CNPJ, inscrição ou cadastro de contribuinte (estadual, municipal ou distrital) e declarações da própria empresa **não têm prazo de validade**. Não procure nem cobre validade nesses documentos: deixe `validade` vazio, não escreva "sem validade", "sem prazo" nem "validade não encontrada", e não rebaixe a situação nem abra pendência por falta dessa data. Confira o que conta neles: titular e CNPJ, profissional, objeto, quantitativo, registro no conselho e, só quando o edital limitar, a data de emissão ou de execução (por exemplo, atestado dos últimos N anos). A certidão de registro e quitação no conselho (da empresa ou do profissional) e as certidões de regularidade fiscal, trabalhista e de falência têm validade e continuam conferidas.
     - **Classificação de bloqueio (`CONTRATO.md`, fonte única):** grave em cada exigência revisada `bloqueia: true|false`, `momento` (`"ate_convocacao"|"diligencia"|"contrato"|"orientacao"`), `risco_inabilitacao: true|false` e `motivo_bloqueio` começando pelo momento (`"Antes da sessão —"`, `"Até 2 h após a convocação —"`, `"Em diligência —"`, `"Orientação —"`, `"Antes do contrato —"`) e citando a cláusula do edital:
       - `bloqueia: true` **somente** para o que impede cadastrar a proposta e dar lance na sessão; `situacao: "atende"` nunca bloqueia (`bloqueia: false`).
       - Todo o resto leva `bloqueia: false`, `momento` e `risco_inabilitacao` (`true` se não resolver até o momento levar à inabilitação; na dúvida, `bloqueia: false` com `risco_inabilitacao: true` e motivo citando `"verificar (<item>)"`).
       - Nunca repita a mesma ação em dois itens; só mantenha dois itens quando forem ações distintas com conclusão própria (ex.: assinar declaração de indicação do RT × comprovar vínculo do RT).
     - **Categoria por etapa (`etapa_envio`, `ordem_edital`, `item_edital`):** preencha ou preserve `etapa_envio` (`"sessao"|"proposta"|"habilitacao"`), `ordem_edital` (`1..999`) e `item_edital` (até 80 chars) em cada exigência revisada.
     - **Documento incompleto / minuta nunca confirma:** se o arquivo for minuta, tiver campos ou valores em branco (ex.: proposta com preços vazios), contiver `"MINUTA"` no nome ou no texto, ou constar como `PENDENTE` em `agents/montagem-proposta/indice-envio.json`, **não confirme o item** (ele segue em "A fazer"), mas a `situacao` é `"atende"` quando a empresa cumpre o requisito e só falta coletar ou preencher; deixe `acao` clara e `motivo` em linguagem simples (ex.: `"Proposta ajustada ao lance pendente após a disputa"`).
     - **Documento que depende do valor do lance (proposta ajustada, planilha de composição de custos e qualquer anexo com preço) nunca confirma enquanto a pessoa não informar o lance:** grave com `pendente: true` e `motivo: "Gerada com o preço de referência; refazer com o lance final"` (também no `status: "pendente"` do plano e na `situacao: "PENDENTE"` do índice), mesmo que o preço de referência esteja preenchido e o arquivo pareça completo. Só use `pendente: false` quando o preço vier do lance informado por uma pessoa. Na conferência, não confirme esse item enquanto o lance não constar; a `situacao` segue `"atende"`, com `acao` e esse motivo.
     - **Checagem de assinaturas (`assinaturas[]` e `conferencia`):** para cada signatário pendente em declarações, balanço, ART/CAT ou registro no conselho:
       - procure no PDF devolvido a assinatura digital (nome no certificado usando `python3 /opt/realmak/agentes/scripts/assinaturas_pdf.py ARQUIVO.pdf "NOME"` quando disponível) **ou** a assinatura visível na `pagina` e no `local` indicados;
       - registre em `assinaturas[].conferencia` (até 300 chars) exatamente o que viu (ex.: `"IA: assinatura gov.br de X conferida na p. 1"`) e marque `assinado: true, forma: "retornado"`;
       - sem certeza, mantenha `assinado: false`, explique por quê em `conferencia` e em `assinatura_motivo` (ex.: `"arquivo sem assinatura de X"`), e mantenha `acao` pedindo a assinatura até todos os signatários obrigatórios assinarem; falta de assinatura é coleta, então a `situacao` é `"atende"` (não `"parcial"`);
     - **Quantitativos / capacidades técnicas** (TR, equipamentos, prazo mínimo) quando for atestado técnico.
4. **Critério de `situacao` (`CONTRATO.md`):** `"atende"` = a empresa cumpre o requisito, inclusive quando falta só **coletar** (assinatura, documento a emitir ou reemitir, confirmar vigência, preencher a proposta com o lance), com a providência em `acao`; `"parcial"` só para dúvida real de equivalência; `"nao_atende"` só para impedimento comprovado. **Promova `"parcial"` para `"atende"`** quando o `motivo` for só coleta, sem dúvida sobre a empresa cumprir. Itens com `etapa_envio: "proposta"` não entram na conta da habilitação. Só mude `situacao` para `"atende"` quando houver prova lida e compatível ou quando a empresa comprovadamente cumprir e faltar só coletar:
   - Em `prova`, informe o nome do arquivo, os dados objetivos conferidos (emissão, validade, CNPJ/número/quantitativo) e:
     - para documento do Cérebro, mantenha ou inclua a URL `/brain/abrir/<brain>/<sha256>` (com o sha256 real do arquivo);
     - para documento adicionado na pasta da disputa, cite `DOCUMENTOS PARA DISPUTA/<nome_do_arquivo>`.
   - Quando `situacao` passar para `"atende"` e nada mais faltar coletar, remova `acao` (ou deixe `null`) e `risco_principal: false`; se ainda falta coletar, mantenha `acao`.
   - Quando o documento ainda estiver vencido, incompleto ou ausente, mas a empresa cumprir o requisito, mantenha `"atende"` com `acao` clara sobre o que falta coletar; use `"parcial"` só para dúvida real de equivalência (ou divergência que a pessoa precise decidir) e `"nao_atende"` só para impedimento comprovado. Atualize `prova` com o que foi lido e deixe `motivo` e `acao` claros.

## Saída obrigatória

1. **`analise/habilitacao.json`** atualizado (JSON válido, UTF-8):
   - **Preserve intactas** todas as demais empresas em `empresas[]` e todos os campos globais do contrato (`versao`, `mais_aderente`, `resultado`, `emitiveis`, `perguntas_tecnico`, `pesquisa_incompleta`, `cobertura`).
   - Atualize `gerado_em` com o timestamp ISO-8601 atual e atualize apenas o objeto da empresa conferida dentro de `empresas[]` (suas `exigencias`, `pendencias`, `validade` e eventual resumo).
   - Inclua/atualize o campo `ultima_conferencia` na raiz:
     ```json
     {
       "em": "2026-11-24T20:30:00Z",
       "empresa": "realmak",
       "comprovadas_antes": 8,
       "comprovadas_depois": 14,
       "total_exigencias": 19,
       "resolvidas": ["Inscrição no CNPJ", "..."],
       "ainda_pendentes": ["Atestados em TR por item", "..."],
       "resumo": "6 exigências comprovadas com os novos documentos; 5 seguem pendentes."
     }
     ```
2. Responda com um resumo curto em português listando o que foi comprovado e o que segue pendente.
