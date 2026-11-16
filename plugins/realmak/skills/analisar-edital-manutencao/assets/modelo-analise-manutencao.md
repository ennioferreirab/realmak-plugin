# Análise de manutenção: [ÓRGÃO] · [MODALIDADE] nº [NÚMERO/ANO]

| Campo | Dado |
| --- | --- |
| Órgão / unidade | [ÓRGÃO E UNIDADE COMPRADORA] |
| Edital e processo | [NÚMERO DO EDITAL E DO PROCESSO] |
| Objeto | [OBJETO, COMO CONSTA NO EDITAL] |
| Vigência | [MESES E REGRA DE PRORROGAÇÃO] |
| Valor estimado | [R$ VALOR OU "SIGILOSO"] |
| Data desta análise | [DATA] |

Marcação usada neste documento: **(D)** dado do documento, **(C)** cálculo, **(P)** premissa, **(R)** recomendação.

Prazos do certame, habilitação jurídica, fiscal e econômica, declarações e impugnação estão na análise geral do edital, não aqui.

## 1. Conclusão de exequibilidade operacional

**Conclusão: [ATENDE | ATENDE COM CONDIÇÕES | NÃO ATENDE]**

[JUSTIFICATIVA EM ATÉ CINCO LINHAS: O QUE O SERVIÇO EXIGE, SE A EQUIPE COBRE A CARGA E ONDE ESTÁ O RISCO.]

| Indicador | Valor |
| --- | --- |
| Horas requeridas por mês | [H] |
| Horas disponíveis por mês | [H] |
| Cobertura da equipe | [%] |
| Folga por mês | [H] |

### Condições para atender

- [CONDIÇÃO 1, OU "NENHUMA"]

### Gargalos de capacidade

- [GARGALO, COM O NÚMERO DA SEÇÃO 5 QUE O DEMONSTRA]

### Obrigações de maior risco

| Obrigação | Requisito | Por que é risco | Como reduzir |
| --- | --- | --- | --- |
| [OBRIGAÇÃO] | [R-00] | [MOTIVO] | [MEDIDA] |

### Pontos para a analista decidir

- [PONTO E PRAZO]

## 2. Requisitos de execução

### 2.1 Documentos analisados

| ID | Arquivo | Tipo de documento | Versão ou data |
| --- | --- | --- | --- |
| D-01 | [NOME DO ARQUIVO] | [EDITAL, TR, ETP, MINUTA, INVENTÁRIO...] | [VERSÃO OU DATA] |

### 2.2 Requisitos

| ID | Grupo | Requisito | Fonte | Quantidade | Unidade de medição | Periodicidade | Custo afetado | Risco | Pendência |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| R-01 | [EXECUÇÃO, SLA E PENALIDADES, PEÇAS E MATERIAIS OU QUALIFICAÇÃO TÉCNICA] | [EXIGÊNCIA] | [D-01, SEÇÃO/ITEM/PÁGINA/ABA] | [NÚMERO] | [UNIDADE] | [MENSAL, ANUAL...] | [MÃO DE OBRA, PEÇAS, LOGÍSTICA...] | [ALTO, MÉDIO OU BAIXO] | [P-00 OU "—"] |

### 2.3 Divergências de contagem

| Item | Contagem A (fonte) | Contagem B (fonte) | Adotada | Motivo |
| --- | --- | --- | --- | --- |
| [ITEM] | [NÚMERO (D-00)] | [NÚMERO (D-00)] | [A OU B] | [MOTIVO] |

## 3. Estrutura do escopo

| Bloco | Tipo de carga | Atividade | Requisito | Frequência anual | Volume | Tempo por execução (h) | Horas por ano | Profissional | Recurso necessário |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| [PREVENTIVA, CORRETIVA, DOCUMENTAÇÃO, SISTEMA DE GESTÃO, TREINAMENTO E SUPORTE, LOGÍSTICA, RESPONSABILIDADE TÉCNICA OU MOBILIZAÇÃO] | [PROGRAMADA, NÃO PROGRAMADA OU INDIRETA] | [ATIVIDADE] | [R-00] | [NÚMERO] | [NÚMERO E UNIDADE] | [H] | [H] | [PERFIL] | [INSTRUMENTO, VEÍCULO, SOFTWARE...] |

Blocos sem aplicação neste certame: [BLOCOS E MOTIVO, OU "NENHUM"].

## 4. Peças, insumos e materiais

| Item | Tipo | Requisito | Como é pago | Quantidade estimada por ano | Unidade | Base da estimativa | Regra do edital |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [ITEM] | [PEÇA, INSUMO, MATERIAL OU KIT PREVENTIVO] | [R-00] | [INCLUÍDO NO PREÇO, COBRADO À PARTE, FORNECIDO PELO ÓRGÃO OU EDITAL NÃO DIZ] | [NÚMERO] | [UNIDADE] | [HISTÓRICO, LISTA DO EDITAL OU PREMISSA] | [AUTORIZAÇÃO, TETO, ESTOQUE MÍNIMO] |

Esta seção lista o que o serviço exige. Preço e cotação ficam para a precificação.

## 5. Dimensionamento

### 5.1 Premissas

| Premissa | Valor | Tipo | O que muda se estiver errada |
| --- | --- | --- | --- |
| [PREMISSA] | [VALOR] | [(D), (C) OU (P)] | [IMPACTO] |

### 5.2 Carga de trabalho

| Bloco de carga | Horas por ano | Horas por mês | Base do cálculo |
| --- | --- | --- | --- |
| Programada | [H] | [H] | [QUANTIDADE × FREQUÊNCIA × TEMPO] |
| Não programada | [H] | [H] | [HISTÓRICO OU PREMISSA] |
| Indireta | [H] | [H] | [ITENS CONSIDERADOS] |
| **Total requerido** | **[H]** | **[H]** | |

### 5.3 Capacidade da equipe

| Profissional | Quantidade | Horas brutas por mês (por pessoa) | Descontos por mês (h, por pessoa) | Horas produtivas por mês | Descontos considerados |
| --- | --- | --- | --- | --- | --- |
| [PERFIL] | [N] | [H] | [H] | [H] | [FÉRIAS, FERIADOS, PAUSAS, DESLOCAMENTO, RESERVA] |
| **Total disponível** | | | | **[H]** | |

### 5.4 Resultado

| Indicador | Valor |
| --- | --- |
| Horas requeridas por mês | [H] |
| Horas disponíveis por mês | [H] |
| Cobertura (disponíveis ÷ requeridas) | [%] |
| Folga (disponíveis − requeridas) | [H] |

### 5.5 Testes

| Teste | Exigência | Carga | Capacidade | Resultado |
| --- | --- | --- | --- | --- |
| Primeiro ciclo | [PRAZO E VOLUME (R-00)] | [H] | [H] | [ATENDE OU NÃO ATENDE] |
| Pior SLA | [SLA (R-00)] | [CENÁRIO TESTADO] | [RECURSO DISPONÍVEL] | [ATENDE OU NÃO ATENDE] |

### 5.6 Conclusão sobre a equipe

Mínimo exigido na qualificação técnica: [EQUIPE (R-00)].
Equipe necessária pelo cálculo de carga: [EQUIPE].

[UMA A TRÊS LINHAS EXPLICANDO A DIFERENÇA, SE HOUVER.]

## 6. Pendências

| ID | Tipo | Descrição | Fonte | Impacto | Ação sugerida | Prazo |
| --- | --- | --- | --- | --- | --- | --- |
| P-01 | [DIVERGÊNCIA, DADO AUSENTE, ESCLARECIMENTO OU LEVAR À ANÁLISE GERAL] | [DESCRIÇÃO] | [D-00, SEÇÃO] | [O QUE AFETA] | [AÇÃO] | [DATA] |
