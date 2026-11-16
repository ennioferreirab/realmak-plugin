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

Se o trabalho for feito na plataforma de licitações, leia a skill `licitacao` para abrir a licitação, achar a análise, anexar os arquivos e registrar as pendências.

## Fontes de preço

| Preciso de | Onde buscar |
| --- | --- |
| Preço de peças, insumos e materiais em fornecedores | Skill `cotar-pecas-materiais-licitacoes`, a partir da Tabela 5 (Peças, insumos e materiais) de `analise-manutencao.md` |
| Preço praticado em compras públicas e valores homologados em certames parecidos | Skill `compras-publicas` |
| Custos próprios da empresa (salários, encargos, veículos, instrumentos) | O analista informa; sem o dado, use premissa identificada |

Preço de referência pública serve para situar a proposta diante do mercado. O custo da empresa vem dos custos reais dela.

## O que entregar

1. **Planilha de proposta e exequibilidade** em `.xlsx`, verificada, na pasta do processo.
2. **Síntese executiva** curta: preço mensal, anual e global, intervalo seguro de preço, principais premissas, riscos e pendências.

Se o analista não indicar a pasta do processo, use a pasta onde estão os documentos do certame e informe o caminho.

## Passo 1: custos

Organize os custos em três blocos. Percorra todos os itens e, para cada um, decida entre incluir o valor ou registrar por que não se aplica ao escopo. Item ignorado sem registro vira custo escondido.

### Mão de obra

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
- tributos pela alíquota efetiva demonstrada;
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

- todos os itens dos três blocos de custo têm valor ou justificativa de não aplicação;
- a aba Checks não aponta erro e mensal, anual e global fecham entre si;
- a síntese traz preço, intervalo seguro, premissas críticas e pendências;
- o arquivo está salvo na pasta do processo e o caminho foi informado.
