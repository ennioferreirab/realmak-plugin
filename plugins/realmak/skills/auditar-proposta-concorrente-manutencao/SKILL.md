---
name: auditar-proposta-concorrente-manutencao
description: Use quando houver proposta concorrente, diligência, intenção de recurso, contrarrazões ou questionamento de exequibilidade em licitação de serviço de manutenção (predial, climatização, equipamentos, inclusive hospitalares). Confronta a proposta ou planilha do concorrente com o edital e a legislação, classifica as falhas, monta a matriz de provas e redige a minuta de recurso ou de contrarrazões. Usar depois de analisar-edital-manutencao. Para formar o preço da própria empresa, use precificar-proposta-exequibilidade.
---

# Auditar proposta concorrente e preparar recurso

Atue como engenheiro sênior de manutenção, especialista em formação de preços e em contratos administrativos. Esta skill responde a uma pergunta: **a proposta do concorrente cumpre o edital e é exequível, e o que dá para provar?**

## Antes de começar

Você precisa de três coisas:

1. **A proposta do concorrente**, com planilha de composição e resposta à diligência, se houver.
2. **As exigências do certame.** Se existir `analise-manutencao.md` na pasta do processo, use os requisitos de execução e o dimensionamento dele. Se não existir, levante as obrigações do edital com `analisar-edital-manutencao` antes de auditar. Prazos de recurso e de contrarrazões vêm da análise geral (`analisar-edital`).
3. **A planilha de preço da própria empresa**, quando existir. Ela serve de referência de custo e garante que o recurso use os mesmos números da proposta que a empresa apresentou.

Se o trabalho for feito na plataforma de licitações, leia a skill `licitacao` para abrir a licitação, achar a análise, anexar os arquivos e registrar as pendências.

## Fontes externas

| Preciso de | Onde buscar |
| --- | --- |
| Contratos que o concorrente já executa, para testar capacidade simultânea | Skill `compras-publicas` (contratos vigentes por CNPJ) |
| Mensagens do pregão e histórico da diligência | Skill `conlicitacao` |
| Preços praticados em contratos parecidos | Skill `compras-publicas` |

Dado de fonte pública pode ter atraso ou lacuna. Cite a fonte e a data da consulta, e não trate a ausência de um contrato na busca como prova de que ele não existe.

## O que entregar

1. **Matriz probatória:** uma linha por falha, com descrição, tipo, item do edital violado, prova disponível, prova que falta e risco para a execução.
2. **Síntese executiva:** quais falhas sustentam um recurso, quais são fracas e qual pedido as provas comportam.
3. **Minuta de recurso** (ou de contrarrazões), quando o analista pedir: texto editável e, se útil, PDF.

Salve na pasta do processo. Se o analista não indicar a pasta, use a que contém os documentos do certame e informe o caminho.

## Passo 1: auditoria

1. Compare o preço ofertado com o orçamento oficial e com o limiar de inexequibilidade previsto no edital ou na norma vigente.
2. Extraia toda a formação de preço do concorrente: mão de obra, encargos, horas, peças, tributos, logística, instrumentos, software, RT, mobilização, garantia, contingência e margem.
3. Confronte a composição global com cada obrigação do edital. Uma rubrica zerada ou baixa não basta como tese se o preço global absorve aquele custo. Mostre que o conjunto não fecha.
4. Verifique a capacidade simultânea: contratos vigentes, profissionais compartilhados, escalas, equipamentos de teste, estoque, veículos e sobreaviso.
5. Verifique a diligência: houve oportunidade real de prova? A resposta trouxe documentos verificáveis ou só declarações?

## Passo 2: classificação das falhas

Classifique cada falha em um destes tipos. O tipo define a força do argumento e o pedido possível.

| Tipo | O que é |
| --- | --- |
| Omissão formal saneável | Falta que a diligência pode corrigir sem mudar a proposta. |
| Inconsistência interna | Números da própria proposta que não fecham entre si. |
| Premissa não comprovada | Custo ou produtividade afirmado sem documento. |
| Insuficiência de capacidade | Equipe, horas ou recursos abaixo da carga exigida. |
| Desconformidade técnica material | Descumprimento de exigência substantiva do edital. |
| Condição criada depois | Algo que não existia na data da proposta e apareceu na diligência. |

## Passo 3: provas

Para cada falha, indique a prova que a sustenta ou a que deve ser pedida em diligência:

- vínculo e remuneração de técnicos e RT: eSocial, folha, pró-labore ou contratos;
- memória de horas e mapa de capacidade;
- registros profissionais, ART, CAT/CAO e licença sanitária;
- inventário de instrumentos e certificados de calibração;
- propostas de sistema de gestão, seguros, garantia e fornecedores;
- PGDAS-D, RBT12, anexo e faixa, fator R, ISS e alíquota efetiva;
- cotações, histórico de consumo e estoque mínimo de peças;
- cronograma de mobilização e de primeiro ciclo;
- lista de contratos em execução e recursos alocados.

## Passo 4: minuta de recurso

Redija somente se o analista pedir. Estruture assim:

1. endereçamento, identificação do certame e ato recorrido;
2. cabimento, tempestividade e efeitos;
3. síntese objetiva com números verificáveis;
4. fatos e falhas, agrupados por relevância;
5. vínculo de cada falha com o item do edital e com a prova;
6. risco concreto para a execução, a continuidade e a segurança;
7. fundamentação jurídica atualizada;
8. pedido principal compatível com a prova;
9. pedido subsidiário de diligência documental objetiva e de parecer técnico;
10. requerimento de decisão motivada e de acesso aos documentos.

Deixe marcadores visíveis, como `[RAZÃO SOCIAL]`, para razão social, CNPJ, representante, datas, ato recorrido e qualquer dado que falte. Não preencha esses campos por suposição.

## Regras

- **Proporção.** O pedido acompanha a prova. Prova forte sustenta pedido de desclassificação; indício sustenta pedido de diligência.
- **Sem acusação sem prova.** Não afirme fraude, má-fé ou falsidade sem documento que comprove. Trate divergência societária ou documental como ponto a esclarecer. Uma acusação sem prova enfraquece o resto do recurso.
- **Inexequibilidade.** Diga expressamente quando a presunção de inexequibilidade for relativa e quando um custo zero isolado não gera desclassificação automática.
- **Fontes jurídicas.** Use fontes oficiais para legislação, regulamentação e jurisprudência e confirme vigência e contexto na data do trabalho. Critérios próprios de obras e engenharia não se aplicam automaticamente a serviços em geral.
- **Sem promessa.** Não prometa desclassificação nem vitória no recurso.
- **Limite.** O recurso busca uma decisão tecnicamente motivada. Ele não substitui a avaliação jurídica da empresa, e a síntese deve dizer isso.
- **Originais.** Não altere os documentos recebidos. Trabalhe em cópias.

## Pronto quando

- cada falha tem tipo, item do edital e prova, ou a prova que falta está indicada;
- a síntese separa as teses fortes das fracas;
- o pedido principal e o subsidiário são compatíveis com as provas disponíveis;
- a minuta, se pedida, está em arquivo editável com os marcadores visíveis.
