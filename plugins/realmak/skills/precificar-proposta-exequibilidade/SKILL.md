---
name: precificar-proposta-exequibilidade
description: Use quando a equipe pedir preço, proposta comercial, planilha de custos, BDI, margem ou exequibilidade de uma licitação de serviço de manutenção (predial, climatização, equipamentos, inclusive hospitalares), com ou sem peças e materiais. Monta custos de mão de obra, operação, peças, tributos e margem, testa cenários e preenche a planilha-modelo em Excel. Usar depois de analisar-edital-manutencao, que dimensiona a equipe. Para cotar peças em fornecedores, use cotar-pecas-materiais-licitacoes. Para criticar a proposta de um concorrente, use auditar-proposta-concorrente-manutencao.
---

# Precificar proposta e exequibilidade

Atue como engenheiro sênior de manutenção, especialista em formação de preços e contratos administrativos. Esta skill responde a uma pergunta: **por quanto a empresa consegue executar este contrato, e em quais premissas esse preço se sustenta?**

## Antes de começar

O preço parte do escopo e do dimensionamento de equipe. Procure `analise-manutencao.md` na pasta do processo.

- Se existir, use os números dele. Não refaça contagens nem horas por conta própria, para que análise, proposta e eventual recurso falem dos mesmos dados.
- Se não existir, faça primeiro a análise com `analisar-edital-manutencao`. Preço formado sem carga de trabalho calculada é palpite.

Defina também **qual empresa do grupo vai disputar** (AForça, Realmak, UNA ou Nortfort). Tributos e encargos mudam de uma empresa para outra, então o mesmo contrato tem preço diferente em cada uma. Se a escolha ainda não foi feita, use a conclusão de `analisar-habilitacao` ou pergunte ao analista.

Se o trabalho for feito na plataforma de licitações, leia a skill `licitacao` para abrir a licitação, achar a análise, anexar os arquivos e registrar as pendências.

## Fontes de preço

| Preciso de | Onde buscar |
| --- | --- |
| Custo de mão de obra por cargo, encargos, benefícios e tributos de cada empresa | Base de custos do grupo (seção abaixo) |
| Preço de peças, insumos e materiais em fornecedores | No fluxo do agente, use `fontes/pecas.json`. Na análise manual, use a pesquisa já disponível ou rode `cotar-pecas-materiais-licitacoes` com a Tabela 5 de `analise-manutencao.md` |
| Preço praticado em compras públicas e valores homologados em certames parecidos | Skill `compras-publicas` |
| Custos que a base não tem (veículo dedicado, instrumentos, CMMS) | O analista informa; sem o dado, use premissa identificada |

No fluxo do agente, se `fontes/pecas.json` estiver ausente ou incompleto, registre cada lacuna e a premissa adotada. Prossiga com a precificação sem reabrir a pesquisa de peças neste item.

Preço de referência pública serve para situar a proposta diante do mercado. O custo da empresa vem dos custos reais dela.

## Base de custos do grupo

A base de custos sai da planilha de pessoal do grupo e tem, sem nome de ninguém:

- faixa de custo por cargo de execução, por empresa e no grupo: mínimo, mediana e máximo do salário, do custo mensal cheio e do custo-hora;
- alíquota de tributos sobre o faturamento e retenção típica de cada empresa;
- encargos sociais por grupo (A a E) e benefícios (VR e VT) de cada empresa;
- custo mensal da administração central de cada empresa;
- lucro e impostos que a empresa usa por segmento e as despesas mensais fixas, como referência.

O esquema completo está em `references/base-custos.md`.

### Onde está

A base real não vem com o plugin, porque traz salários e custos internos.

- Na plataforma de licitações: leia a skill `licitacao`; ela diz como buscar a base da competência mais recente (ou de outra) e gravá-la como `base-custos.json` para os scripts.
- Fora da plataforma: peça ao analista o `base-custos.json` da competência mais recente, ou o caminho dele no computador.

`assets/base-custos-exemplo.json` tem valores fictícios e serve só para testar os scripts; nunca forme preço com ele.

Antes de usar, confira a `competencia` e a lista `alertas`. Base com mais de 12 meses, empresa sem alíquota ou faixa marcada como larga vira pendência na síntese.

### Como consultar

Rode `scripts/consultar_base.py` (só Python, sem dependência):

```bash
python scripts/consultar_base.py base-custos.json --listar
python scripts/consultar_base.py base-custos.json --empresa aforca
python scripts/consultar_base.py base-custos.json --empresa aforca --cargo "Técnico de manutenção" --cenario base
```

Sem `--cargo`, sai o resumo da empresa. Com `--cargo`, sai a linha pronta para a aba Custos MO:

| Campo da consulta | Onde vai no modelo |
| --- | --- |
| `C_salario_base` | Custos MO, coluna C (salário com periculosidade) |
| `D_encargos_adicionais` | Custos MO, coluna D (encargos sociais da empresa) |
| `E_beneficios` | Custos MO, coluna E (VR, VT e demais itens da folha) |
| `aliquota_tributos` | Premissas, B17 (alíquota tributária efetiva) |

Regras da consulta:

- **Cenários.** `base` usa a mediana, `conservador` o máximo e `otimista` o mínimo da faixa. Monte o cenário-base com `base` e o conservador com `conservador`.
- **Cargo que a empresa não tem.** A consulta usa a faixa do grupo e aplica os encargos da empresa escolhida. Registre isso como premissa.
- **Prestador de serviço.** Use `--prestador`; o honorário vai inteiro na coluna C, sem encargos.
- **Avisos.** Leia `avisos` em toda consulta. Custo com mais de 25% fora da composição legal (horas extras, gratificações) só entra se o contrato tiver esses itens.
- **Administração central.** O custo mensal da empresa é a base do rateio; o percentual em Premissas B18 sai desse custo dividido pelo faturamento ou pelo número de contratos que o analista informar. Sem esse dado, use premissa identificada.
- **Markup por segmento.** O lucro e os impostos de cada segmento mostram como a empresa costuma formar preço. Servem de comparação, não substituem a conta de tributos pela alíquota da empresa.

### Como atualizar

Quando chegar a planilha nova de pessoal, rode a ingestão com a planilha original (`.xls` precisa do LibreOffice instalado):

```bash
uv run --with openpyxl python scripts/ingerir_custos.py TODOS_FUNCIONARIOS_2026.xls pasta-saida --competencia 2026-01
```

Saem `base-custos.json` (o que a skill consulta) e `base-custos.xlsx` (a mesma base para conferência, com a aba Alertas). Confira os alertas e a aba Tributos, depois envie os dois arquivos para a plataforma (a skill `licitacao` diz como). Não grave a base dentro do plugin nem num repositório.

A base é dado interno do grupo. Na proposta e nos anexos da licitação entra só a composição usada no preço, nunca a base inteira nem as faixas das outras empresas.

## O que entregar

1. **Planilha de proposta e exequibilidade** em `.xlsx`, verificada, na pasta do processo.
2. **Síntese executiva** curta: preço mensal, anual e global, intervalo seguro de preço, principais premissas, riscos e pendências.

Se o analista não indicar a pasta do processo, use a pasta onde estão os documentos do certame e informe o caminho.

## Passo 1: custos

Organize os custos em três blocos. Percorra todos os itens e, para cada um, decida entre incluir o valor ou registrar por que não se aplica ao escopo. Item ignorado sem registro vira custo escondido.

### Mão de obra

Cada cargo da equipe dimensionada vira uma linha da aba Custos MO, com os valores da base de custos da empresa que vai disputar.

- salários, pró-labore ou contratos de prestação;
- encargos, benefícios, férias, 13º, FGTS, adicionais e horas extras;
- responsável técnico, ART, registros e profissionais de cobertura;
- produtividade, rateio e custo de oportunidade;
- sobreaviso, acionamentos fora do horário e substituições.

### Operação

- veículo, combustível, estacionamento, pedágio, frete e remoção;
- ferramentas, analisadores, padrões, calibrações, manutenção e depreciação;
- EPIs, uniformes, crachás, comunicação e informática;
- sistema de gestão da manutenção: licenças, implantação, suporte, armazenamento e contingência;
- peças, insumos e materiais incluídos no preço, kits preventivos, estoque mínimo, perdas e logística (itens da Tabela 5 da análise marcados como "Incluído no preço");
- treinamentos, documentação, impressão, etiquetas e descarte;
- mobilização.

### Financeiro e preço

- administração central compatível com o contrato;
- garantia contratual, seguros e capital de giro;
- tributos pela alíquota efetiva da empresa que vai disputar, tirada da base de custos;
- contingência ligada aos riscos identificados na análise;
- margem coerente com a exposição e com a competição;
- arredondamento e desconto, reconciliados ao preço final.

Duas regras valem para os três blocos:

- **Sem dedicação exclusiva não quer dizer sem custo.** Toda hora produtiva, responsabilidade técnica, disponibilidade, sobreaviso, deslocamento, retrabalho e gestão tem custo direto, rateado ou de oportunidade. Se o recurso já existe na empresa, demonstre o rateio.
- **Margem não absorve custo omitido.** Cada custo aparece na sua própria linha. Uma margem que esconde custos parece maior do que é e não resiste a uma diligência.

## Passo 2: cenários e exequibilidade

Use o dimensionamento do órgão (TR, ETP e planilhas) no cenário-base, com as fontes da análise técnica. Confira se a equipe e as horas da planilha de custo correspondem à base documentada. Se a análise técnica tiver usado **(P)** onde há dado do órgão, corrija o dimensionamento antes de fechar o preço. Use **(P)** do agente para lacuna documental e identifique a fonte ou a razão da hipótese.

Quando uma **(P)** muda o tamanho da equipe ou a recomendação, calcule-a apenas como cenário alternativo. Se faltar insumo decisivo para um preço-base conclusivo, diga qual condição falta e deixe o resultado condicionado. A hipótese isolada não sustenta “inexequível”, recomendação de não disputar nem nota 1 por trava. Nos dados do card, sinalize `premissa_decisiva: true` se a conclusão-base ainda depender de uma **(P)** decisiva. Propague a marca da análise técnica se o custo ainda usar a equipe condicionada por essa mesma premissa. Uma hipótese que afeta só o cenário alternativo não torna o cenário-base inconclusivo. Quando a incerteza for relevante, acrescente um cenário conservador e um crítico. Faça sensibilidade para os vetores que mais mexem no resultado: volume de corretivas, peças, horas técnicas, tributos, reajuste, mobilização e prazo de pagamento.

**Exemplo.** O TR fixa a referência de 28 h/mês para corretivas. Precifique o cenário-base com a equipe calculada para essa carga e as demais horas documentadas. Se uma hipótese de volume maior exigir quatro técnicos e produzir margem negativa, mostre esse risco só no cenário alternativo. Preserve a equipe do cenário-base e calcule a margem com esse custo; a margem negativa do alternativo não dispara a trava.

Indicadores mínimos:

- preço mensal, anual e global;
- custo mensal total e por bloco;
- margem de contribuição e operacional, em valor e em percentual;
- desconto sobre o orçamento oficial;
- horas requeridas, horas disponíveis e cobertura;
- reserva de contingência;
- ponto de equilíbrio, quando útil.

A conclusão diz em quais premissas a proposta é exequível e quais controles operacionais são indispensáveis para que continue sendo.

## Passo 3: planilha

Prepare apenas o JSON com os números, premissas e fontes, seguindo [o formato de entrada](references/planilha.md). Execute o preenchimento do modelo:

```bash
python scripts/preencher_planilha.py dados.json proposta.xlsx
```

No ambiente manual sem openpyxl, use `uv run --with openpyxl python scripts/preencher_planilha.py dados.json proposta.xlsx`. O script usa o modelo original e preserva abas, fórmulas, verificações e cores. Corrija os dados no JSON e rode de novo. Não edite nem descompacte o XLSX para preencher entradas. Quando o edital exigir planilha própria, preserve esse formato na proposta oficial; use o modelo da skill para a memória de exequibilidade.


## Passo 4: verificação

Antes de entregar:

- corrija todo erro apontado na aba Checks;
- reconcilie mensal, anual e global;
- procure custos negativos, células vazias indevidas e erros de fórmula;
- confira fórmulas e totais por amostragem, refazendo a conta fora da planilha;
- renderize e olhe todas as abas. Em listas longas, confira trechos do início, do meio e do fim.

## Regras

- **Tipos de afirmação.** Diferencie dado do edital, cálculo, premissa de mercado e recomendação. Marque as premissas como editáveis e explique o impacto das mais relevantes.
- **Escopo.** Inclua somente custos compatíveis com o que o certame exige.
- **Tema tributário e jurídico.** Confirme alíquotas e normas vigentes em fonte oficial na data do trabalho. Não prometa resultado do certame.
- **Originais.** Não altere os documentos do certame nem o modelo da skill.

## Pronto quando

- a empresa que vai disputar está definida, e a mão de obra e os tributos vêm da base de custos dela, com a competência informada;
- todos os itens dos três blocos de custo têm valor ou justificativa de não aplicação;
- a aba Checks não aponta erro e mensal, anual e global fecham entre si;
- a síntese traz preço, intervalo seguro, premissas críticas e pendências;
- o arquivo está salvo na pasta do processo e o caminho foi informado.
