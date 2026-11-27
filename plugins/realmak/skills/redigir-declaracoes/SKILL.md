---
name: redigir-declaracoes
description: Redige as declarações exigidas por um edital (nepotismo, art. 7º XXXIII, responsável técnico, estrutura, vistoria, ME/EPP etc.) em nome da empresa que disputa, no padrão de timbre, cabeçalho e assinatura das empresas do grupo Realmak, e salva DOCX e PDF em "DOCUMENTOS PARA DISPUTA" do card. Use na montagem da documentação de uma licitação.
---

# Redigir declarações

Base do agente Montagem Proposta. O resultado é **um DOCX com uma declaração por página**, mais o PDF, pronto para conferência humana antes do envio.

## 1. Levantar o que o edital pede

1. Leia a habilitação já analisada do card (`habilitacao.json`, empresa disputante): toda exigência com "Declaração" no rótulo ou com `acao.tipo` igual a `emitir`/`redigir` vira uma declaração.
2. Confira no edital (itens de habilitação, proposta e anexos) se falta alguma. Anote, para cada uma, o **item do edital** e o **anexo com modelo**, se houver.
3. Procure o arquivo do modelo na pasta do card no Drive (por exemplo, "ANEXO III - MODELO DE DECLARAÇÃO DE VISTORIA.pdf"). O texto do edital extraído nem sempre traz os anexos.

## 2. Escolher o texto de cada declaração

Siga esta ordem:

1. **O órgão deu modelo** (anexo): use o texto do modelo **literalmente**, só preenchendo as lacunas. Preserve o título do anexo, por exemplo "ANEXO IV – DECLARAÇÃO DE INEXISTÊNCIA DE NEPOTISMO".
2. **O edital pede a declaração sem modelo**: use o texto padrão de [references/modelos.md](references/modelos.md) e cite o item do edital (por exemplo, "para fins do item 10.6.4.2 do Edital do PREGÃO ELETRÔNICO Nº 35/2026").
3. **O modelo não serve ao caso**: por exemplo, o modelo é de "vistoria realizada", mas a empresa não vistoriou. Nesse caso, redija pelo item do edital que admite a alternativa e cite-o.

Não invente fato. Decisões que mudam o texto precisam de fonte no card (check-list, anotação, marcador) ou de resposta de uma pessoa:
- quem é o responsável técnico;
- se a vistoria foi feita;
- se a empresa emprega aprendiz;
- se é ME/EPP;
- se tem escritório local.

Sem fonte, gere a versão mais provável, marque **PENDENTE** no resumo e diga qual informação falta.

## 3. Dados da empresa e assinatura

- Os dados vêm do **cadastro da empresa no CRM** (Cadastros → Empresas do grupo; ferramenta `dados_empresa`): razão social, CNPJ, inscrição, sede, CEP, representante (nome, cargo, RG, CPF, tratamento), imagem da **assinatura**, imagem do **timbre** e a flag `assinatura_inclui_nome`.
- Nunca copie CPF, RG ou assinatura de outro documento nem os grave fora do cadastro.
- **Signatário sem imagem de assinatura**, como o responsável técnico: o gerador coloca uma linha de assinatura com nome, registro e CPF. Ele assina à mão ou digitalmente. Liste esse documento no resumo como "falta assinatura de …".

## 4. Modelo de assinatura

Use o `scripts/gerar_declaracoes.py`, que aplica o padrão:

- **Timbre** da empresa no cabeçalho de todas as páginas, com 17 cm de largura.
- **Cabeçalho da página:** cidade e data à direita; depois, à esquerda e em negrito, "AO", o órgão (uma linha por nível), a modalidade e o número, e o processo.
- **Título** centralizado em negrito; **texto** justificado, com recuo de 1,25 cm, Arial 11.
- **Qualificação** padrão: `{qualificacao}` monta "A empresa RAZÃO, inscrita no CNPJ sob o nº …, CF/DF nº …, com sede na …, CEP …, por intermédio de seu representante legal, o Senhor …, portador(a) da carteira de identidade nº … e do CPF nº …".
- **Assinatura do representante:** imagem centralizada com 6,5 cm de largura; abaixo, a razão social. Se a imagem não traz o nome impresso (`assinatura_inclui_nome: false`), o gerador acrescenta o nome em maiúsculas, o cargo e o CPF.
- **Outros signatários:** passe `{"nome", "linhas": [registro, CPF, papel]}` em `assinaturas`. A ordem da lista é a ordem na página. Por exemplo, a declaração de vistoria assinada pelo RT leva o RT primeiro.

Especificação: veja o docstring do script e o exemplo em [references/exemplo-spec.json](references/exemplo-spec.json). Execute:

```bash
uv run --with python-docx python3 scripts/gerar_declaracoes.py spec.json "Declaracoes_<Empresa>_<MOD>-<num>-<ano>_<Orgao>.docx"
```

## 5. Converter, salvar e conferir

1. Converta para PDF com LibreOffice: `soffice --headless --convert-to pdf`.
2. Salve o DOCX e o PDF na pasta **DOCUMENTOS PARA DISPUTA** do card (pasta da licitação no Drive). Assim aparecem no card em "Documentos para disputa → Adicionados para a disputa".
3. Abra o PDF e confira cada página:
   - nada cortado;
   - a assinatura certa;
   - o número do certame e do processo iguais aos do edital;
   - a data do dia.
4. Responda com:
   - a lista das declarações, cada uma com o item do edital e a origem do texto (modelo do órgão, padrão da casa ou redação pelo item);
   - as pendências, como "falta assinatura do RT" ou "confirmar se houve vistoria";
   - os dois arquivos.
