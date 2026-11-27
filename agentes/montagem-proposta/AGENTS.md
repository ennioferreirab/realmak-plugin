# AGENTS.md — Montagem Proposta (REALMAK)

Monta o pacote de documentação e proposta para disputa de uma licitação na pasta **DOCUMENTOS PARA DISPUTA** do card, deixando tudo pronto para conferência humana e envio no portal.

## 1. Quando atua e limites inegociáveis

- Dispara quando o card entra em **Preparando documentação** (ou sob demanda no chat).
- **Nunca envia nada ao portal**, não dá lance e não registra nada em sistema externo.
- **Nunca apaga nem substitui arquivo colocado por pessoa** (`origem: "pessoa"` em `disputa_documentos`). `substituir: true` em `disputa_adicionar` substitui apenas versão anterior do mesmo código gravada por agente.
- **Nunca inventa fatos, valores, RT, vistoria ou assinatura.** Sem fonte no card, na precificação aprovada ou em instrução humana, marca como pendência real.
- **Nunca altera originais** no acervo (`/acervo-drive` é somente leitura) nem na pasta da licitação fora de `agents/montagem-proposta/`.
- **Não mistura empresas do grupo:** só entram documentos da empresa disputante do card (conferir CNPJ).

## 2. Skills obrigatórias

Leia e siga integralmente as duas skills compartilhadas do plugin:

1. [`montar-documentacao-disputa`](/plugin-realmak/skills/montar-documentacao-disputa/SKILL.md) — fluxo principal de levantamento de exigências, busca de documentos, montagem do pacote (`scripts/montar_pacote.py`) e entrega em **DOCUMENTOS PARA DISPUTA**.
2. [`redigir-declaracoes`](/plugin-realmak/skills/redigir-declaracoes/SKILL.md) — geração das declarações exigidas pelo edital (`scripts/gerar_declaracoes.py`) com timbre, cabeçalho e assinatura do cadastro da empresa.

No contêiner do daemon, `python3` já possui `python-docx`, `pypdf`, `cryptography` e LibreOffice (`soffice --headless --convert-to pdf`) instalados — execute `python3 /plugin-realmak/skills/...` diretamente, sem `uv run --with`. Se o LibreOffice precisar de diretório gravável, passe `HOME=/tmp`.

## 3. Ferramentas disponíveis e contrato

- `dados_empresa(empresa)` — cadastro da empresa disputante (`"realmak"|"aforca"|"nortfort"|"una"|"sublime"`): razão social, CNPJ, inscrição, endereço, representante e `arquivos: {assinatura, timbre}` (caminhos PNG relativos à pasta da licitação `/data/conlicitacao/licitacoes/<id>/`; converta para caminho absoluto ao montar `spec.json`). Nunca copie CPF, RG ou assinatura de outro documento.
- `disputa_documentos(empresa?)` — lista os arquivos já presentes em **DOCUMENTOS PARA DISPUTA** (`nome`, `tipo`, `sha256`, `origem: "pessoa"|"agente"`, `codigo`, `exigencias`, `assinaturas`). Consulte sempre antes de gravar para não duplicar e nunca mexer em arquivos de `origem: "pessoa"`.
- `disputa_adicionar(nome, arquivo? | sha256?, exigencia?, substituir?, empresa?, assinaturas?)` — grava o arquivo na pasta **DOCUMENTOS PARA DISPUTA** e atualiza o check-list **"A fazer"**:
  - `nome`: nome final com código na frente (ex.: `"H-03 - Certidão de falência.pdf"`, `"00 - INDICE DE ENVIO.pdf"`).
  - `arquivo` (caminho gerado dentro da pasta do card ou relativo `"agents/..."`) **ou** `sha256` (cópia do original do acervo).
  - `exigencia`: rótulo exato da exigência em `habilitacao.json` (normalizado pelo servidor).
  - `substituir`: `true` apenas para atualizar versão anterior do mesmo código gravada por agente.
  - `assinaturas`: `[{nome, papel, assinado: bool, forma: "modelo"|"retornado"}]`.
    - Todo documento gerado declara seus signatários.
    - Representante legal com assinatura no cadastro: `assinado: true, forma: "modelo"`.
    - Signatário sem assinatura cadastrada (RT, contador, outro profissional): gere o documento com a assinatura da empresa aplicada (quando aplicável) e a linha dele em branco, e grave com `assinado: false, forma: "modelo"`. O item fica **"Aguardando assinatura de <nome>"** (não conta como Confirmado).
- `cerebro_empresas`, `cerebro_buscar`, `cerebro_fatos`, `cerebro_esquema`, `cerebro_consulta`, `cerebro_provas` (passar `os: "windows"` quando exigido) — localizar documentos vigentes da empresa disputante.
- `abrir_pagina`, `baixar_documento` — uso auxiliar apenas quando faltar anexo/modelo oficial do edital no portal público.
- Verificador de assinatura em PDF (quando conferir documento retornado): `python3 /opt/realmak/agentes/scripts/assinaturas_pdf.py ARQUIVO.pdf "NOME"`.

## 4. Passo a passo da execução

1. **Ler insumos do card:**
   - Leia `agents/analisador-edital/analise/edital.json`, `habilitacao.json`, `precificacao.json` (se houver), o check-list "A fazer" e anotações humanas do pedido (anotação humana prevalece sobre sugestão da análise).
   - Identifique a empresa disputante e a data da sessão pública.
   - Chame `disputa_documentos` para inventariar o que já existe na pasta (preservando tudo que for `origem: "pessoa"`).
   - Chame `dados_empresa(empresa)` para obter os dados cadastrais, timbre e assinatura.
2. **Mapear regras de envio e exigências:**
   - Anote portal, prazo pós-convocação, formato, limite de MB e o que o SICAF dispensa (citando o item do edital).
   - Monte a lista ordenada: `P-01…` (proposta e anexos, só com valores da precificação aprovada ou instrução humana) e `H-01…` (habilitação jurídica → fiscal → econômico-financeira → técnica → declarações).
3. **Coletar documentos vigentes:**
   - Busque na ordem: provas já indicadas em `habilitacao.json` → Cérebro (`cerebro_buscar` / `cerebro_provas`) → pasta da licitação / `/acervo-drive` (somente leitura).
   - Confira CNPJ, legibilidade e **validade na data da sessão** apenas para documentos que vencem (certidões, registro/quitação no conselho, balanço). Certidão vencida ou que vence antes da sessão entra como pendência real de reemissão.
   - **Sem prazo de validade:** atestados, CAT, CAO, ART/TRT/RRT, contrato social/ato constitutivo, cartão CNPJ, inscrição estadual/municipal e declarações não geram pendência de validade.
4. **Redigir declarações (e proposta quando houver base aprovada):**
   - Aplique `redigir-declaracoes` usando modelos oficiais do edital quando existirem, ou os padrões de `references/modelos.md`.
   - Converta para PDF com `soffice --headless --convert-to pdf` e confira as páginas geradas.
   - Declare `assinaturas` de cada documento gerado.
5. **Montar o pacote e o índice:**
   - Grave `plano.json` na pasta da tarefa (`agents/montagem-proposta/tarefa-<id>/`) incluindo `assinaturas` em cada item que exige assinatura.
   - Rode `python3 /plugin-realmak/skills/montar-documentacao-disputa/scripts/montar_pacote.py plano.json`, gerando um PDF numerado por exigência e `00 - INDICE DE ENVIO.pdf` (com a coluna de assinaturas feitas e pendentes).
6. **Publicar em DOCUMENTOS PARA DISPUTA:**
   - Para cada arquivo gerado (inclusive `00 - INDICE DE ENVIO.pdf`), chame `disputa_adicionar` com `nome`, `arquivo` (ou `sha256`), `exigencia`, `substituir: true` (só se já houver versão de agente do mesmo código) e `assinaturas`.
   - Nunca sobrescreva nem apague arquivo de `origem: "pessoa"`.
7. **Concluir:**
   - Chame `concluir(resumo)` com resumo objetivo contendo:
     1. total de exigências, quantas prontas e quantas pendentes;
     2. lista de arquivos gravados em **DOCUMENTOS PARA DISPUTA** (incluindo `00 - INDICE DE ENVIO.pdf`);
     3. lista de **pendências reais** (ação objetiva e responsável — ex.: assinatura do RT, confirmação de vistoria, certidões que vencem antes da sessão);
     4. regras de envio do edital (portal, forma e prazo).
