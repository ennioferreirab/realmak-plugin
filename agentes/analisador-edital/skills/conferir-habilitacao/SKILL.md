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
2. Liste todos os arquivos reais da pasta `DOCUMENTOS PARA DISPUTA` (se ela existir e tiver arquivos). Para PDFs, DOCX, XLSX e TXT adicionados pela equipe, leia o conteúdo (usando Python/bash com `fitz`/`pypdf`/`openpyxl` ou leitura direta) antes de concluir qualquer item.
3. Para cada exigência da empresa que não esteja `atende` (e também para qualquer exigência marcada como providenciada no checklist ou com validade próxima da data da sessão):
   - Verifique primeiro se há documento correspondente em `DOCUMENTOS PARA DISPUTA/`.
   - Se ainda faltar ou precisar de complemento, faça busca direcionada no Cérebro (`cerebro_buscar` / `cerebro_fatos`) para aquela empresa e exigência específica.
   - Confira no texto real do documento:
     - **CNPJ e razão social** compatíveis com a empresa disputante;
     - **Emissão e validade** frente à data atual e à data da sessão/envio da proposta, só para documento que vence (certidões, registro no conselho, balanço);
     - **Sem prazo de validade:** Atestado de capacidade técnica, CAT (Certidão de Acervo Técnico), CAO (Certidão de Acervo Operacional), ART, TRT, RRT, ato constitutivo, cartão CNPJ, inscrição ou cadastro de contribuinte (estadual, municipal ou distrital) e declarações da própria empresa **não têm prazo de validade**. Não procure nem cobre validade nesses documentos: deixe `validade` vazio, não escreva "sem validade", "sem prazo" nem "validade não encontrada", e não rebaixe a situação nem abra pendência por falta dessa data. Confira o que conta neles: titular e CNPJ, profissional, objeto, quantitativo, registro no conselho e, só quando o edital limitar, a data de emissão ou de execução (por exemplo, atestado dos últimos N anos). A certidão de registro e quitação no conselho (da empresa ou do profissional) e as certidões de regularidade fiscal, trabalhista e de falência têm validade e continuam conferidas.
     - **Assinatura / registro / autenticação** quando exigidos (declarações, balanço, ART/CAT, registro no conselho): quando o documento pede mais de um signatário (ex.: representante + RT ou contador), verifique cada signatário (usando `python3 /opt/realmak/agentes/scripts/assinaturas_pdf.py ARQUIVO.pdf "NOME"` quando disponível) e grave na exigência `assinaturas: [{nome, papel, assinado, forma}]` e `assinatura_motivo` (ex.: `"arquivo sem assinatura de X"`), mantendo `situacao: "parcial"` até todos assinarem;
     - **Quantitativos / capacidades técnicas** (TR, equipamentos, prazo mínimo) quando for atestado técnico.
4. Só mude `situacao` para `"atende"` quando houver prova lida e compatível:
   - Em `prova`, informe o nome do arquivo, os dados objetivos conferidos (emissão, validade, CNPJ/número/quantitativo) e:
     - para documento do Cérebro, mantenha ou inclua a URL `/brain/abrir/<brain>/<sha256>` (com o sha256 real do arquivo);
     - para documento adicionado na pasta da disputa, cite `DOCUMENTOS PARA DISPUTA/<nome_do_arquivo>`.
   - Quando `situacao` passar para `"atende"`, remova `acao` (ou deixe `null`) e `risco_principal: false`.
   - Quando o documento ainda estiver vencido, incompleto, com divergência ou ausente, mantenha `"parcial"` ou `"nao_atende"`, atualize `prova` com o que foi lido e deixe `motivo` e `acao` claros sobre o que ainda falta.

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
