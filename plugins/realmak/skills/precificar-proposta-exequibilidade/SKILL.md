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
| Preço de peças, insumos e materiais em fornecedores | Skill `cotar-pecas-materiais-licitacoes`, a partir da Tabela 5 (Peças, insumos e materiais) de `analise-manutencao.md` |
| Preço praticado em compras públicas e valores homologados em certames parecidos | Skill `compras-publicas` |
| Custos que a base não tem (veículo dedicado, instrumentos, CMMS) | O analista informa; sem o dado, use premissa identificada |

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

A base real fica na plataforma de licitações e não vem com o plugin, porque traz salários e custos internos. Peça ao analista o `base-custos.json` da competência mais recente, ou o caminho dele. `assets/base-custos-exemplo.json` tem valores fictícios e serve só para testar os scripts; nunca forme preço com ele.

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

Saem `base-custos.json` (o que a skill consulta) e `base-custos.xlsx` (a mesma base para conferência, com a aba Alertas). Confira os alertas e a aba Tributos, depois envie os dois arquivos para a plataforma. Não grave a base dentro do plugin nem num repositório.

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

Monte o cenário-base. Quando a incerteza for relevante, acrescente um cenário conservador e um crítico. Faça sensibilidade para os vetores que mais mexem no resultado: volume de corretivas, peças, horas técnicas, tributos, reajuste, mobilização e prazo de pagamento.

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

Use `assets/Modelo_Proposta_Comercial_Exequibilidade_Manutencao.xlsx`. Copie o arquivo para a pasta do processo e trabalhe na cópia; o modelo original fica intacto.

- Preserve abas, arquitetura, fórmulas, verificações e cores. Amarelo é entrada, verde é resultado favorável, vermelho e laranja são alertas.
- Preencha apenas com dados confirmados ou com premissas identificadas como premissas.
- Substitua os textos genéricos pelos dados do processo sem quebrar fórmulas.
- Mantenha as fórmulas vivas e as referências entre abas. Não grave resultado calculado como número fixo, porque o avaliador precisa conseguir auditar a conta.
- Preencha a aba Fontes com arquivo e seção, página ou aba. Para pesquisa externa, registre a URL em texto simples.

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
