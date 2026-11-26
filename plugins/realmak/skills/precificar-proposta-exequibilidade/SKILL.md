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

Defina também **qual empresa do grupo vai disputar** (`aforca`, `realmak`, `una` ou `nortfort`). Tributos e encargos mudam de uma empresa para outra, então o mesmo contrato tem preço diferente em cada uma. Use estritamente a `empresa_escolhida` informada no pedido ou na decisão anterior (fallback: `mais_aderente` de `analisar-habilitacao`); nunca precifique a Realmak silenciosamente quando outra empresa tiver sido escolhida. Em `analise/precificacao.json`, grave obrigatoriamente `empresa_precificada` com o alias efetivamente precificado (`realmak`, `nortfort`, `aforca` ou `una`).

**Bloqueio para obra ou reforma sem planilha orçamentária:** nunca aplique premissas, custos de equipe ou a planilha-modelo de manutenção em licitações de **obra ou reforma** (por exemplo, reforma de cobertura/telhado, obra civil, estrutura metálica) sem uma planilha orçamentária válida do certame ou composição própria de obra. Explicite a limitação e a pendência orçamentária em vez de inventar margem de manutenção.

Se o trabalho for feito na plataforma de licitações, leia a skill `licitacao` para abrir a licitação, achar a análise, anexar os arquivos e registrar as pendências.

## Fontes de preço

| Preciso de | Onde buscar |
| --- | --- |
| Custo de mão de obra por cargo, encargos, benefícios e tributos de cada empresa | Base de custos do grupo (seção abaixo) |
| Preço de peças, insumos e materiais em fornecedores | No fluxo do agente, use `fontes/pecas.json`. Na análise manual, use a pesquisa já disponível ou rode `cotar-pecas-materiais-licitacoes` com a Tabela 5 de `analise-manutencao.md` |
| Preço praticado em compras públicas e valores homologados em certames parecidos | Skill `compras-publicas` |
| Custos que a base não tem (veículo dedicado, instrumentos, CMMS) | O analista informa; sem o dado, use premissa identificada |

No fluxo do agente, use as ofertas e estimativas de `fontes/pecas.json` com suas bases. Para peças incluídas no lance, multiplique o preço unitário pelo consumo mensal estimado de cada item e some os custos; marque o consumo estimado como **(P)** e declare a cobertura. Exemplo: filtro a R$ 80, consumo estimado de duas unidades por mês, reserva de R$ 160/mês. Na planilha, use quantidade anual equivalente para a aba de peças; o script leva o total à reserva operacional uma vez. Preserve os subtotais das peças com base individual. Para as demais, use uma reserva **(P)** fundamentada para os itens sem base e identifique o que ela cobre, sem duplicar custos. Use verba global quando a composição por item estiver indisponível. A entrega segue com a cobertura disponível.

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
- **Encargos sobre custo-hora já carregado:** nunca reaplique encargos sociais ou benefícios sobre o custo-hora ou custo mensal cheio já carregado na `base-custos.json` (use sempre a decomposição `C_salario_base`, `D_encargos_adicionais` e `E_beneficios` de `consultar_base.py`, ou o valor cheio sem multiplicar encargos de novo).
- **Alíquota de tributos pendente (ausente ou frágil `n=1`):** quando a empresa precificada (`empresa_precificada`) estiver na `base-custos.json` com `tributos.aliquota == null`, `tributos.pendente` preenchido, ou `tributos.notas == 1` sem `tributos.confirmada == true` (ex.: `una` ausente, `aforca` 12,68% `n=1`, `nortfort` 6% `n=1`):
  - **Não apresente uma margem única como definitiva:** deixe a margem definitiva em aberto (`null` ou condicionada) ou simule explicitamente uma faixa tributária (cenário com a alíquota observada e cenário conservador), sinalizando pendência de confirmação contábil.
  - Grave obrigatoriamente em `analise/precificacao.json`:
    - `"tributos_pendente": true`
    - `"tributos_pendente_motivo": "<motivo objetivo e curto, ex.: Alíquota tributária da UNA ausente na base de custos; confirmar com a contabilidade>"`
  - Quando a alíquota estiver confirmada (`tributos.aliquota != null` e (`tributos.notas > 1` ou `tributos.confirmada == true`)), grave `"tributos_pendente": false`.
  - **Na plataforma (quando a ferramenta `registrar_nota_urgente` estiver disponível):** chame diretamente `registrar_nota_urgente` ao encontrar alíquota ausente/não confirmada (`n=1`) ou base de custos defasada (> 12 meses), usando `chave` estável (ex.: `chave: "tributos:una"` ou `chave: "base_custos:defasada:<competencia>"`), `empresa`, `titulo`, `detalhe` (motivo + competência + ação de confirmar com a contabilidade e atualizar em Cadastros → Custos) e `link_destino: "/odoo/action-261"`.
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

## Vigência, prorrogação e reajuste

- **Prorrogação é bilateral (Lei 14.133/2021, art. 107):** a empresa pode renegociar ou recusar a prorrogação. O preço precisa se sustentar apenas na **vigência inicial** (12 meses ou até 5 anos, art. 106). Nunca embutir inflação de prorrogações no lance.
- **Unidade do lance e custos únicos:** o lance segue a unidade de julgamento do edital (mensal, unitário ou global de 12/30/60 meses). Custos únicos (mobilização, implantação, ferramentas) amortizam na vigência inicial.
- **Data-base:** no reajuste por índice, conta da data do orçamento estimado (arts. 25, § 7º e 92, § 3º); na repactuação (serviços contínuos com dedicação exclusiva ou predominância de mão de obra, art. 135), usa a CCT para mão de obra e a data da proposta para os demais custos.
- **Defasagem (sem projeção ano a ano):** leia `empresas.<slug>.dissidio` na base de custos (`percentual_esperado` em pp/ano e `data_base_mes` de 1 a 12).
  - *Com `percentual_esperado` informado:* calcule `peso da MO × (dissídio esperado − índice do edital)` apenas sobre os anos da vigência inicial, somada à perda dos meses entre `data_base_mes` e o primeiro aniversário de reajuste ou repactuação, e grave `defasagem_reais` e `defasagem_pp` como o **total da vigência inicial** (nunca por mês), sempre com o **mesmo sinal**: positivo (`> 0`) = perda para a empresa (custo sobe mais que o índice do contrato); negativo (`< 0`) = favorável (índice cobre o dissídio). O índice futuro do edital (IPCA, INCC, INPC) continua como premissa **(P)** com fonte citada.
  - *Sem valor (ou base sem a chave):* mantenha `defasagem_reais` e `defasagem_pp` em `null`, informe quanto aumento de custo o preço absorve e registre a pendência de informar o dissídio da empresa em Cadastros → Custos; na plataforma, chame `registrar_nota_urgente` com chave estável `dissidio:<empresa>` (mesmo padrão da alíquota ausente, `link_destino: "/odoo/action-261"`).
- **Casos:**
  - *Até 12 meses:* inclua o dissídio se a data-base da CCT cair dentro do período.
  - *Vigência inicial acima de 12 meses:* precifique com a defasagem projetada.
  - *Edital omisso ou com vedação:* a cláusula de reajuste é obrigatória por lei — peça esclarecimento ou impugne; enquanto isso, monte cenário-base sem correção e registre alerta.
  - *Ata de registro de preços (ARP):* validade de 1 ano, prorrogável por mais 1 se vantajoso (art. 84); reajuste ou repactuação só se o edital previr (Decreto 11.462/2023, art. 25, III) — sem previsão, cabe apenas revisão; o contrato derivado tem vigência e reajuste próprios e a ata não garante volume. Registre expressamente em `recomendacao` (e no `resumo`) que o contrato derivado tem vigência e reajuste próprios e que a ata não garante volume.
- **Cenário conservador:** inclua cenário conservador com colchão apenas quando a defasagem empurrar a margem abaixo do piso. Não faça projeção ano a ano.
- **Saída:** inclua obrigatoriamente 1 linha sobre vigência, reajuste, prorrogação e defasagem calculada (ou sensibilidade, quando sem dissídio) na síntese executiva **e no campo `resumo` de `analise/precificacao.json`** (que é a síntese exibida ao usuário). Exemplo: `"Preço vale para os 12 meses iniciais; primeiro reajuste pelo INCC em 03/2027; prorrogável até 10 anos, sem efeito no lance; defasagem estimada na vigência inicial de R$ 4.200 (perda de 1,35 pp de margem) ou cada +1% na mão de obra tira 0,55 ponto de margem."` Na planilha (`dados.json`), preencha apenas `premissas.vigencia_meses` e `proposta.reajuste` (sem aba nova).

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

Em `analise/precificacao.json`, grave a margem operacional do cenário-base em `margem_pct`, a alíquota efetiva usada em `tributos_pct` e a margem mínima aplicada, quando definida, em `margem_minima_pct`. Use pontos percentuais (ex.: `19.29`, e não `0.1929`). Cite a fonte dos tributos e da margem mínima. Exemplo: se a base da empresa informa 19,29% e o preço calculado deixa 4,82%, grave `tributos_pct: 19.29` e `margem_pct: 4.82`.

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

## Campos opcionais do card

- Informe `piso_sugerido` como valor mensal quando o cálculo o sustentar. Em `sensibilidade`, use `{rotulo, margem_pct}` com margem em pontos percentuais de cada hipótese calculada. Em `condicoes`, use `{id, texto}` para condições concretas da recomendação, com ID estável.
- Resuma peças em `pecas_grupos` com `{rotulo, itens, valor_anual, situacao}`. Use `itens` como contagem, `valor_anual` em reais quando calculável e `situacao` como texto curto que indique a base ou a pendência. Não conte os mesmos itens em dois grupos nem use zero para representar valor desconhecido.
- Em `vigencia_precificacao`, grave um objeto plano opcional com `{meses_iniciais, prorrogavel_ate_meses, mecanismo, indice_ou_cct, data_base, clausula, defasagem_reais, defasagem_pp, base_fechamento, recomendacao}` resumindo o tratamento de vigência, correção e defasagem usado no preço:
  - `mecanismo`: use exatamente os mesmos valores de `vigencia.mecanismo_correcao` (`"reajuste_indice"|"repactuacao"|"ambos"|"omisso"|"vedado"|null`), nunca frase longa.
  - `defasagem_reais` e `defasagem_pp`: perda total para a empresa na **vigência inicial** (nunca mensal), sempre com o **mesmo sinal** — positivo (`> 0`) quando o custo sobe mais que o índice (perda de margem), negativo (`< 0`) quando o índice cobre o dissídio (favorável).
  - `base_fechamento`: informe apenas para qual período e unidade o preço foi fechado (ex.: `"vigência inicial de 12 meses, valor mensal"`).
  - `recomendacao`: traga a sensibilidade/defasagem e a orientação prática (em ata, cite também que o contrato derivado tem vigência e reajuste próprios e que a ata não garante volume).
