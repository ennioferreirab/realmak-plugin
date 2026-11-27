---
name: montar-documentacao-disputa
description: Monta o pacote de envio de uma licitação na pasta DOCUMENTOS PARA DISPUTA do card. Gera o que precisa ser redigido (declarações, proposta) e junta os documentos de habilitação exigidos (certidões, atos, atestados, CAT/CAO, balanços), um PDF por exigência, na ordem e no formato pedidos pelo edital, com índice de envio e pendências. Use quando o card entra em "Preparando documentação" ou quando pedirem para montar a documentação da disputa.
---

# Montar a documentação da disputa

Objetivo: deixar em **DOCUMENTOS PARA DISPUTA** tudo o que a empresa vai anexar no portal, pronto para subir. É um arquivo por exigência, no formato e na ordem do edital, mais o `00 - INDICE DE ENVIO`, que diz o que está pronto e o que falta. Uma pessoa confere antes do envio; o agente **não envia nada ao portal**.

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

Códigos de ordem:
- `P-01…`: proposta e anexos da proposta.
- `H-01…`: habilitação, na ordem do edital (jurídica → fiscal → econômico-financeira → técnica → declarações).

## 3. Checar cada documento (reutilizar → recriar → gerar)

Só depois de fechar a lista de exigências, formato e regras de envio (passos 1 e 2), cheque cada documento nesta ordem:

1. **Reutilizar recorrente vigente:** se a empresa já tem documento recorrente assinado e vigente na data da sessão (certidões, ato constitutivo, CREA PJ, balanço, declaração genérica), reutilize-o. Procure na ordem:
   - **Prova já indicada pela análise** (`prova` da exigência, documentos encontrados pela IA em Documentos para disputa);
   - **Cérebro da empresa:** `cerebro_buscar` e `cerebro_provas` (prefira o mais recente e vigente);
   - **Pasta da licitação e acervo no Drive** (`/acervo-drive`, somente leitura).
2. **Recriar recorrente inadequado ou vencido:** se o recorrente estiver vencido, vencendo antes da sessão ou não atender ao que o edital pede (por exemplo, declaração genérica quando o edital exige o modelo próprio ou cita o número do certame), **recrie** (redija novamente ou marque `"reemitir"` como pendência).
3. **Gerar o que não existe:** o que não existir vai para o passo 4 (redação).

Confira, antes de incluir:
- se é da empresa certa (CNPJ);
- a **validade na data da sessão** (só para documentos que vencem); vencido ou vencendo antes da sessão é pendência `"reemitir"`;
- se o profissional é o mesmo indicado (RT, atestados e CAT);
- se está legível e completo (todas as páginas).

Não use documento de outra empresa do grupo. Não altere originais: o pacote é feito de cópias.

## 4. Gerar o que precisa ser redigido

- **Dados da empresa faltando (`cadastro_pendencias` em `dados_empresa`):** se faltar dado cadastral necessário (por exemplo, conta bancária da NortFort ou da UNA), **não invente e não copie de documento antigo**. Crie a pendência no "a fazer" `"Cadastrar <campo> da <empresa>"` (ex.: `"Cadastrar conta bancária da NortFort"`) e deixe o documento afetado (ex.: proposta) marcado como **pendente** nesse ponto.
- **Declarações:** use a skill `redigir-declaracoes`, com os dados e a assinatura de `dados_empresa`. Ela produz um DOCX/PDF com uma declaração por página. Para o pacote, separe em um PDF por declaração quando o edital pedir arquivos separados; senão, um PDF "Declarações".
- **Proposta:** preencha o modelo do anexo do edital (ou o padrão da casa, como no exemplo da Nortfort PE 85/2026) com os valores da precificação aprovada do card. Valor e lote **só** da precificação aprovada ou de instrução humana; sem isso, pendência.
- **Signatário sem assinatura cadastrada** (RT, contador, outro profissional): o documento sai com a assinatura da empresa já aplicada (quando aplicável) e a linha dele em branco. Declare todos os signatários em `assinaturas: [{nome, papel, assinado: bool, forma: "modelo"|"retornado"}]` (representante cadastrado: `assinado: true, forma: "modelo"`; terceiro sem assinatura: `assinado: false, forma: "modelo"`). Ele não conta como Confirmado: fica **"Aguardando assinatura de <nome>"** e aparece no índice com as assinaturas feitas e as que faltam.
- **Registrar recorrente (passo condicionado à ferramenta):** quando um documento gerado ou reemitido servir para outras licitações, registre-o como recorrente da empresa com sua vigência assim que a ferramenta de documentos recorrentes estiver disponível no daemon.

## 5. Montar o pacote

Monte um `plano.json` (incluindo `assinaturas` em cada item que exige assinatura) e rode (no contêiner do daemon use `python3` direto; fora dele, `uv run --with pypdf --with python-docx python3`):

```bash
python3 scripts/montar_pacote.py plano.json
```

O script:
- converte DOC/DOCX/XLSX/imagens com o LibreOffice;
- junta numa só peça as várias fontes de uma exigência (por exemplo, contrato social mais alterações);
- nomeia `H-03 - Certidão de falência.pdf`;
- avisa sobre arquivos acima do `limite_mb` do portal;
- gera o `00 - INDICE DE ENVIO` com ordem, documento, item do edital, arquivo, assinaturas (feitas e pendentes) e situação.

Marque `status: "pendente"` com `obs` em toda exigência sem documento, vencida, sem assinatura ou com dúvida. Se algum item tiver signatário com `assinado: false`, o script força `status: "pendente"` automaticamente.

## 6. Entregar em DOCUMENTOS PARA DISPUTA

Grave cada arquivo do pacote com a ferramenta `disputa_adicionar(nome, arquivo? | sha256?, exigencia?, substituir?, empresa?, assinaturas?)`, informando a exigência correspondente e a lista `assinaturas` de todo documento gerado. Assim o item do "A fazer" fica **Confirmado** (quando completo e assinado) ou **Aguardando assinatura de <nome>** (quando houver signatário com `assinado: false`). Use `disputa_documentos` para ver o que já está na pasta e não duplicar. Use `substituir: true` apenas para atualizar a versão anterior do mesmo código gravada por agente.

Nunca apague nem substitua arquivos que uma pessoa colocou na pasta (`origem: "pessoa"`).

## 7. Resposta

Responda em poucas linhas:
1. quantas exigências e quantas prontas;
2. a lista de **pendências**, cada uma com a ação e o responsável, por exemplo "Reemitir CND municipal (vence 29/11, sessão 30/11)" ou "Assinatura do RT nas declarações H-05 e H-06";
3. as regras de envio, com prazo e portal.
