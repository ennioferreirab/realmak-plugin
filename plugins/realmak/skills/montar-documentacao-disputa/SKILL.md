---
name: montar-documentacao-disputa
description: Monta o pacote de envio de uma licitação na pasta DOCUMENTOS PARA DISPUTA do card. Gera o que precisa ser redigido (declarações, proposta) e junta os documentos de habilitação exigidos (certidões, atos, atestados, CAT/CAO, balanços), um PDF por exigência, na ordem e no formato pedidos pelo edital, com índice de envio e pendências. Use quando o card entra em "Preparando documentação" ou quando pedirem para montar a documentação da disputa.
---

# Montar a documentação da disputa

Objetivo: deixar em **DOCUMENTOS PARA DISPUTA** tudo o que a empresa vai anexar no portal, pronto para subir, com **nomes legíveis** (sem códigos internos como `H-01` ou `P-01`), organizado nas três etapas de envio (**Para participar da sessão**, **Proposta** e **Para a habilitação**) na ordem do edital (`ordem_edital`). Uma pessoa confere antes do envio; o agente **não envia nada ao portal**.

## 1. Regras de envio do edital

Leia a seção de habilitação e a de proposta do edital e anote:

- **Onde e como se envia.** Por exemplo, Compras.gov.br em "Enviar Anexo", quando o pregoeiro convoca, ou proposta anexada antes da sessão.
- **Prazo depois da convocação**, por exemplo 2 horas. Isso explica por que o pacote precisa estar pronto antes da sessão.
- **Formato:** PDF, assinatura digital (ICP-Brasil ou gov.br), arquivo único ou separado, tamanho máximo, cópia autenticada, ordem pedida.
- **O que o SICAF dispensa** (por exemplo, regularidade fiscal). Mesmo dispensado, junte o documento vigente como reserva, marcado "(SICAF)" no índice.
- **Proposta:** modelo anexo, planilha, validade, documentos que acompanham.

Cite o item do edital em cada regra que usar.

## 2. Lista de exigências

Uma linha por documento a enviar, na ordem do edital:

- **Habilitação:** parta de `habilitacao.json` (empresa disputante: exigências, situação, prova e ação) e complete pelo edital (itens de habilitação jurídica, fiscal, econômico-financeira e técnica).
- **Proposta:** parta do modelo de proposta (anexo) e dos documentos que a acompanham.
- **Check-list "A fazer" do card:** item marcado e anotação, por exemplo "RT: Rolando". Anotação humana prevalece sobre a sugestão da análise.

Categorias por etapa (`etapa_envio`) e ordem (`ordem_edital: 1..999`):
- **`"sessao"` (Para participar da sessão):** somente o que a plataforma prepara ou confere — documento exigido junto com a proposta inicial, garantia de proposta, vistoria obrigatória, amostra, SICAF ativo (quando houver consulta) ou valor aprovado na precificação quando o edital pede proposta anexada. **Nunca** crie item ou aviso para passo manual no portal (cadastrar proposta, marcar declarações no portal, clicar em enviar).
- **`"proposta"` (Proposta):** a proposta completa que o edital pede após o lance, um item por documento: proposta no modelo do edital, planilha de composição de custos, descrição detalhada dos serviços, regime de tributação, declarações que o edital exige com a proposta (por exemplo, sustentabilidade) e procuração, quando houver procurador. Veja a seção 4.1. A proposta inicial do portal (valor e declarações) continua em `"sessao"`.
- **`"habilitacao"` (Para a habilitação):** tudo o que se anexa após a convocação para habilitar a empresa, na ordem do edital (`ordem_edital: 1, 2, 3…`): habilitação jurídica → fiscal → econômico-financeira → técnica → declarações de habilitação. A proposta não entra aqui.

**Sem códigos internos para o usuário:** nunca use `H-xx`, `P-xx` ou `00 -` no nome dos arquivos, nas instruções, nos motivos de falta ou no resumo. Use nomes legíveis (ex.: `Certidão de falência.pdf`, `Declaração de indicação do RT.pdf`); a ordem na tela e no ZIP vem de `ordem_edital`, não de prefixo.

## 3. Checar cada documento (reutilizar → recriar → gerar)

Só depois de fechar a lista de exigências, formato e regras de envio (passos 1 e 2), cheque cada documento nesta ordem:

1. **Reutilizar recorrente vigente:** chame primeiro `documentos_recorrentes(empresa)` para listar os recorrentes do Cérebro (`cnd_federal`, `cnd_estadual`, `cnd_municipal`, `fgts`, `cndt`, `falencia`, `ato_constitutivo`, `crea_pj`, `balanco`, `declaracao_generica`). Se o documento recorrente estiver assinado e vigente na data da sessão, reutilize-o copiando para a disputa com `disputa_adicionar(..., sha256=...)`. Complemente na ordem:
   - **Prova já indicada pela análise** (`prova` da exigência, documentos encontrados pela IA em Documentos para disputa);
   - **Cérebro da empresa:** `cerebro_buscar` e `cerebro_provas` (prefira o mais recente e vigente);
   - **Pasta da licitação e acervo no Drive** (`/acervo-drive`, somente leitura).
2. **Recriar ou emitir certidão automaticamente (subagentes T2 em paralelo):** se uma ou mais **certidões públicas** estiverem ausentes, vencidas ou vencendo antes da sessão, use `emitir_certidoes_paralelo` para disparar **um subagente T2 em paralelo por certidão emitível** com a skill `emitir-certidoes` (determinando o emissor pela exigência + sede da empresa em `dados_empresa`, sem navegador e sem nunca contornar captcha ou login). Cada subagente emite ou reaproveita a vigente, confere CNPJ/nome/resultado/validade no PDF, grava com `disputa_adicionar` e registra em `registrar_recorrente` com a validade; onde houver captcha, login ou falha, abra `"reemitir"` como pendência com o link oficial direto e a instrução. Para outros recorrentes inadequados (por exemplo, declaração genérica quando o edital exige o modelo próprio ou cita o número do certame), **recrie** (redija novamente).
3. **Gerar o que não existe:** o que não existir vai para o passo 4 (redação).

Confira, antes de incluir:
- se é da empresa certa (CNPJ);
- a **validade na data da sessão** (só para documentos que vencem); vencido ou vencendo antes da sessão é pendência `"reemitir"`;
- se o profissional é o mesmo indicado (RT, atestados e CAT);
- se está legível e completo (todas as páginas).

Não use documento de outra empresa do grupo. Não altere originais: o pacote é feito de cópias.

## 4. Gerar o que precisa ser redigido

- **Dados da empresa faltando (`faltando` / `cadastro_pendencias` em `dados_empresa`):** se faltar dado cadastral necessário (por exemplo, conta bancária da NortFort ou da UNA), **não invente e não copie de documento antigo**. O CRM já mostra o item de `faltando` no card e na empresa; deixe o documento afetado (ex.: proposta) marcado como **pendente** nesse ponto e cite o item faltante no resumo.
- **Declarações:** use a skill `redigir-declaracoes`, com os dados e a assinatura de `dados_empresa`. Ela produz um DOCX/PDF com uma declaração por página. Para o pacote, separe em um PDF por declaração quando o edital pedir arquivos separados; senão, um PDF "Declarações".
- **Proposta:** siga a seção 4.1. Valor e lote **só** da precificação aprovada ou de instrução humana; sem isso, pendência.
- **Signatário sem assinatura cadastrada** (RT, contador, outro profissional): o documento sai com a assinatura da empresa já aplicada (quando aplicável) e a linha dele em branco. Envie obrigatoriamente `assinaturas: [{nome, papel, pagina, local, como_assinar, assinado: bool, forma: "modelo"|"retornado"}]` no `disputa_adicionar` (representante cadastrado: `assinado: true, forma: "modelo", como_assinar: "modelo do cadastro"`; terceiro sem assinatura: `assinado: false, forma: "modelo"`, com `pagina`, `local` ex. `"p. 1, linha 'Responsável técnico indicado'"` e `como_assinar` ex. `"gov.br ou ICP-Brasil"` ou `"à mão e escaneado em PDF"`). Ele não conta como Confirmado: fica **"Aguardando assinatura de <nome>"** e aparece no índice com página, local, como assinar, feitas e pendentes.
- **Classificação de bloqueio (`CONTRATO.md`, fonte única):** para exigências de habilitação, **herde** `bloqueia`, `momento`, `risco_inabilitacao` e `motivo_bloqueio` de `habilitacao.json`; classifique os itens de proposta (proposta inicial sem preço obrigatório → `bloqueia: true`, `etapa_envio: "sessao"`; proposta ajustada pós-lance e seus anexos → `bloqueia: false`, `momento: "ate_convocacao"`, `etapa_envio: "proposta"`, `ordem_edital: 1, 2, 3…`). Passe os campos em `plano.json` / `indice-envio.json` e em `disputa_adicionar`. `motivo_bloqueio` começa sempre pelo momento (`"Antes da sessão —"`, `"Até 2 h após a convocação —"`, `"Em diligência —"`, `"Orientação —"`, `"Antes do contrato —"`), cita a cláusula e nunca usa códigos internos (`H-xx`, `P-xx`).
- **Sem duplicar ações:** nunca repita a mesma ação em dois itens. Use o **rótulo exato** da exigência de `habilitacao.json` em `exigencia` quando vários arquivos atenderem a mesma ação; só crie dois itens quando forem ações distintas com conclusão própria (ex.: assinar declaração de indicação do RT × comprovar vínculo do RT).
- **Registrar recorrente:** quando um documento gerado ou reemitido servir para outras licitações, chame `registrar_recorrente(empresa, tipo, arquivo, nome?, validade?, substitui_sha256?)` para enviá-lo ao Cérebro da empresa.

### 4.1 Etapa Proposta

Cada documento sai como **item próprio** (`etapa_envio: "proposta"`, `ordem_edital` na ordem em que o edital lista os documentos que acompanham a proposta). **`exigencia` = rótulo exato do item de `habilitacao.json` com `etapa_envio: "proposta"`** (ex.: "Proposta ajustada ao lance final (Anexo II)", "Planilha de composição de custos"); rótulo inventado cria item duplicado no card que o agente não consegue apagar. Scripts em `scripts/gerar_proposta.py` (no contêiner do daemon, `python3` direto):

1. **Proposta no modelo do edital.** Monte `entrada.json` (formato no docstring do script) com:
   - `empresa` de `dados_empresa` (inclusive banco, agência e conta; se faltarem, o script avisa e a linha sai sem eles, e o item fica pendente);
   - `preco_mensal` do **preço de referência da precificação aprovada** (`precificacao.json`, G3 "seguir") ou do lance/instrução humana, nunca de proposta antiga;
   - `teto_mensal`, itens fixos da Administração, validade mínima, limite de exequibilidade e cláusulas, tudo lido do edital e do TR;
   - `regime_tributario` de `precificacao.json` (ou Cérebro); `dados_empresa` não traz o regime.

   Rode `python3 scripts/gerar_proposta.py proposta entrada.json "Proposta de preços.docx"`. Ele calcula subtotais, preço total por extenso, desconto D = [1 – (VP/VE)] × 100 (quando o edital aplica o desconto aos serviços sob demanda), e **recusa** (exit 2, nada é gerado) preço acima do máximo, abaixo do limite de exequibilidade (por exemplo, 75% do valor orçado), validade menor que o mínimo e regime ausente. Item fixo da Administração (por exemplo, serviços sob demanda e peças) aparece com valor anual e total da vigência, deixando claro o que entra no preço total. Use o **modelo do anexo do edital** quando houver (mesmos campos e ordem); sem modelo à mão, a estrutura do script. Grave o PDF como item enviável e o DOCX com `nao_enviar: true`; a assinatura é a do representante cadastrado (`assinaturas`).
2. **Planilha de composição de custos**, no modelo da skill `precificar-proposta-exequibilidade` (sem formato novo): `python3 scripts/gerar_proposta.py planilha agents/analisador-edital/analise/proposta-exequibilidade.xlsx <saida> --preco-mensal <o mesmo preço da proposta> --data AAAA-MM-DD`. O script recalcula o modelo com o preço informado e gera um PDF só com as abas de composição (mão de obra, custos operacionais e formação do preço), sem fontes, observações internas nem checks. **Nunca envie o workbook inteiro** (memória de exequibilidade, fontes e margem-alvo): ele fica só em "Entregas da IA". O JSON de saída traz `lucro_pct` e `checks_pendentes_ou_falhos`; se o lucro ficar ≤ 0 ou o preço divergir do da precificação, avise no resumo. Se o edital trouxer planilha própria, preserve esse formato em vez do modelo.
3. **Descrição detalhada dos serviços**, específica do edital, redigida a partir do TR, da análise técnica e da precificação (modelo em `redigir-declaracoes/references/modelos.md`). Não repita o TR: mostre como a empresa atende (Edital: repetir o TR sem comprovação pode desclassificar).
4. **Regime de tributação**, como documento próprio curto quando o edital pede, além da linha na proposta.
5. **Declarações exigidas junto com a proposta** (por exemplo, sustentabilidade): `etapa_envio: "proposta"`. As demais declarações são de habilitação.
6. **Procuração**, só quando o signatário não é o representante legal; sem os dados do outorgado, pendente.

Alerte no resumo quando o preço de referência estiver muito abaixo de cotações anteriores da empresa para o mesmo objeto ou da faixa praticada. O agente registra o alerta; a decisão é de uma pessoa.

## 5. Montar o pacote

Monte um `plano.json` (incluindo `assinaturas` em cada item que exige assinatura) e rode (no contêiner do daemon use `python3` direto; fora dele, `uv run --with pypdf --with python-docx python3`):

```bash
python3 scripts/montar_pacote.py plano.json
```

O script:
- converte DOC/DOCX/XLSX/imagens com o LibreOffice;
- junta numa só peça as várias fontes de uma exigência (por exemplo, contrato social mais alterações);
- gera arquivos com **nome legível** sem prefixo interno (ex.: `Certidão de falência.pdf`, nunca `H-03 - ...`) e ordena por `etapa_envio` e `ordem_edital`;
- avisa sobre arquivos acima do `limite_mb` do portal;
- **não gera** `00 - INDICE DE ENVIO.pdf` em `DOCUMENTOS PARA DISPUTA` (o índice em PDF deixou de entrar no pacote);
- quando `indice_json` for informado no `plano.json` (use `agents/montagem-proposta/indice-envio.json`, na área do agente no card — **nunca** em `DOCUMENTOS PARA DISPUTA`), grava o índice estruturado `{"itens": [{"etapa_envio", "ordem_edital", "item_edital", "exigencia", "arquivo", "situacao": "OK"|"PENDENTE", "motivo", "nao_enviar?", "bloqueia", "momento", "risco_inabilitacao", "motivo_bloqueio"}]}` lido diretamente pelo Odoo na checagem.

Use `saida` em diretório temporário (por exemplo, `/tmp/pacote-<id>`) ou remova as cópias dos PDFs da pasta da tarefa depois de chamar `disputa_adicionar`, para não duplicar documentos de disputa fora de **DOCUMENTOS PARA DISPUTA**. Arquivos de trabalho (`plano.json`, `spec*.json`, `.md`, logs e `agents/montagem-proposta/indice-envio.json`) são **intermediários**: vão para `IA/INTERMEDIÁRIOS/montagem-proposta/` e **não** aparecem em `"Entregas da IA"`.

Marque `status: "pendente"` com `obs` em linguagem simples, `etapa_envio`, `ordem_edital`, `item_edital`, `bloqueia`, `momento`, `risco_inabilitacao` e `motivo_bloqueio` em toda exigência sem documento, vencida, sem assinatura ou com dúvida. Se algum item tiver signatário com `assinado: false`, o script força `status: "pendente"` automaticamente.

## 6. Entregar em DOCUMENTOS PARA DISPUTA

Grave cada arquivo do pacote com a ferramenta `disputa_adicionar(nome, arquivo? | sha256?, exigencia?, substituir?, empresa?, assinaturas?, pendente?, motivo?, etapa_envio?, ordem_edital?, item_edital?, nao_enviar?, bloqueia?, momento?, risco_inabilitacao?, motivo_bloqueio?)`, informando:
- `nome` legível sem prefixos `H-xx`/`P-xx`;
- `exigencia` (rótulo exato de `habilitacao.json`), `etapa_envio` (`"sessao"|"proposta"|"habilitacao"`), `ordem_edital` (`1..999`), `item_edital` (até 80 chars) e `nao_enviar: true` apenas quando for rascunho `.docx` ou duplicado;
- classificação de bloqueio e a lista `assinaturas` completa (`nome`, `papel`, `pagina`, `local`, `como_assinar`, `assinado`, `forma`) de todo documento gerado.
- `"Entregas da IA"` exibe apenas relatórios finais para leitura humana (`.xlsx`, `.pdf` de relatório), nunca arquivos intermediários nem cópias do que já foi gravado em **DOCUMENTOS PARA DISPUTA**.
- **Item pendente no plano (`status: "pendente"`):** minuta, valores em branco, falta assinatura ou falta reemitir **não pode confirmar o item**. Passe obrigatoriamente `pendente: true` e `motivo` em linguagem simples (ex.: `"Falta a assinatura de Fulano (p. 1, linha do RT)"` ou `"Proposta ajustada ao lance pendente após a disputa"`). O arquivo é gravado com `confirmado: false` e o item permanece em **"A fazer"** com o motivo visível (arquivos com `"MINUTA"` no nome nunca confirmam no servidor).
- Item completo e assinado fica **Confirmado**; item com signatário com `assinado: false` fica **Aguardando assinatura de <nome>**.
- Use `disputa_documentos` para ver o que já está na pasta e não duplicar. Use `substituir: true` apenas para atualizar a versão anterior do mesmo documento gravada por agente (o servidor casa pelo nome exato, código se houver, ou `exigencia`).

Nunca apague nem substitua arquivos que uma pessoa colocou na pasta (`origem: "pessoa"`).

## 7. Resposta

Responda em poucas linhas (sem códigos internos `H-xx`/`P-xx`):
1. progresso de cada etapa (**Para participar da sessão**, **Proposta** e **Para a habilitação**: prontos e faltas);
2. a lista de **pendências** em linguagem simples, cada uma com a ação e o responsável, por exemplo "Reemitir CND municipal (vence 29/11, sessão 30/11)" ou "Falta a assinatura do RT na declaração de indicação do RT";
3. as regras de envio, com prazo e portal.
