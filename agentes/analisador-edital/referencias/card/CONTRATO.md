# Contrato do card (agente → card)

O card da licitação lê estes quatro arquivos, gravados pelos itens do fluxo em `licitacoes/<id>/agents/analisador-edital/analise/`. As skills do realmak-plugin não conhecem este contrato: o [AGENTS.md](../../AGENTS.md#skills-do-realmak-plugin) diz como o item o preenche a partir das entregas delas.

O agente grava em `licitacoes/<id>/agents/analisador-edital/analise/`. Toda lista pode vir vazia. `fonte` é o rótulo curto (`Edital 8.3`, `TR 9.15`). Datas `AAAA-MM-DD` ou `AAAA-MM-DDTHH:MM` (Brasília). Valores em reais, número.

`edital.json` (skill `analisar-edital`):

```json
{"versao": 1, "gerado_em": "AAAA-MM-DDTHH:MM",
 "cabecalho": {"modalidade": "", "orgao": "", "uasg": "", "objeto": "", "tipo_objeto": "manutencao|fornecimento|outro_servico|misto",
   "valor_estimado": 0, "valor_sigiloso": false, "criterio": "", "modo_disputa": "", "portal": "", "link": ""},
 "atencao": [{"ponto": "", "gravidade": "alta|media|baixa", "fonte": "", "o_que_fazer": ""}],
 "prazos": [{"prazo": "", "data": "", "fonte": "", "observacao": ""}],
 "habilitacao": [{"grupo": "juridica|fiscal|trabalhista|economico_financeira|tecnica", "exigencia": "", "fonte": "", "observacao": ""}],
 "declaracoes": [{"declaracao": "", "tipo": "padrao|especifica", "fonte": ""}],
 "proposta": [{"topico": "", "texto": "", "fonte": ""}],
 "impugnacao": [{"restricao": "", "fundamento": "", "prazo": "", "fonte": "", "prazo_passou": false}],
 "perguntas_tecnico": [{"pergunta": "", "fonte": ""}],
 "avisos": [{"data": "", "tipo": "aviso|esclarecimento|impugnacao|retificacao", "resumo": "", "mudou": ""}],
 "avisos_consultados": true,
 "nao_lido": [{"arquivo": "", "motivo": ""}],
 "documentos": [{"arquivo": "", "origem": "plataforma|pncp|portal|anexo"}]}
```

`habilitacao.json` (skill `analisar-habilitacao`):
Quando houver original de habilitação, `prova` cita arquivo, página, seção ou aba, trecho literal e confronto com os dados aplicáveis à exigência (titular/CNPJ, datas, validade, exercício ou escopo). A mesma prova indica o endereço permanente da cópia na licitação. Sem leitura do original, a exigência documental fica `verificar` se não houver outra prova válida, com “Validação pendente” e a lacuna documental descrita. Uma cópia disponível permite download mesmo com a conferência pendente. O Odoo acrescenta `controle_validacao[]` à resposta da habilitação somente a partir do dossiê privado do usuário autenticado, sem anexá-lo ao JSON compartilhado. Cada registro vincula empresa, SHA-256 e exigência ao original. Inclui arquivo, localizador, trecho literal, parecer `confere|diverge|pendente`, conclusão ou motivo e modelo efetivo. O parecer do leitor não substitui a avaliação de habilitação.


Se houver diferença material na ordenação, indique em `mais_aderente` a primeira empresa, inclusive se a avaliação continuar indeterminada. Use `null` em empate material ou impedimento demonstrado em todas. Declare a situação em `resultado`. No card, `mais_aderente` vira a sugestão de empresa que disputa (`empresa_disputante`, origem `ia`). A escolha de uma pessoa (origem `manual`) não é sobrescrita por nova análise.

```json
{"versao": 1, "gerado_em": "", "mais_aderente": "aforca|realmak|una|nortfort|null", "resultado": "",
 "empresas": [{"empresa": "aforca|realmak|una|nortfort", "aderencia": "alta|media|baixa|nao_atende", "resumo": "",
   "exigencias": [{"exigencia": "", "fonte": "", "situacao": "atende|parcial|nao_atende|verificar", "prova": "", "validade": "",
    "grupo": "juridica|fiscal|trabalhista|economico_financeira|tecnica", "motivo": "",
    "acao": {"o_que": "", "quem": "", "ate": ""}}],
   "pendencias": [""]}],
 "emitiveis": [""], "perguntas_tecnico": [{"pergunta": "", "fonte": ""}],
 "pesquisa_incompleta": [{"empresa": "realmak", "motivo": "<tentativas e impacto>"}]}
```

### Campos opcionais da habilitação

O contrato segue na versão 1. Os quatro campos são opcionais tanto no consolidado quanto nos parciais.

- `grupo` vem de `edital.json`, com o mesmo enum de `habilitacao[].grupo`, e agrupa as exigências no card.
- `motivo` resume em até 120 caracteres a lacuna documental ou o impedimento quando `situacao` for diferente de `atende`.
- `acao` indica uma providência concreta. Informe `o_que`, `quem` e `ate` em `AAAA-MM-DD` ou vazio se o prazo estiver em aberto. Com `acao`, o card exibe “Ação necessária”. Sem ela, o card interpreta `atende` como “Comprovado”, `parcial` como “Ação necessária” e `nao_atende` ou `verificar` como “Não comprovado”. `prova` permanece como evidência na coluna Prova.
- `pesquisa_incompleta` reúne por empresa, no topo do card, falhas de acesso, teto ou tempo que deixaram itens sem pesquisa suficiente. Informe o alias, o que foi tentado e o impacto. Guarde os detalhes operacionais só aqui. Preserve a marcação `cobertura[].estado: "falha"` e os dados de consulta para o G2. Em saídas antigas sem `pesquisa_incompleta`, o card usa os registros de cobertura com estado `falha`.

### Parciais de habilitação

A [pesquisa, aquisição e leitura](../habilitacao-aquisicao.md) geram os insumos de cada parcial. Estes insumos são operacionais e ficam fora do contrato v1 do card.

Cada `analise/habilitacao/<alias>.json` usa o mesmo envelope v1, com apenas a empresa do item, `mais_aderente: null` e uma avaliação por exigência do edital. Acrescente `cobertura[]` na raiz; a consolidação reúne os registros dos quatro parciais, preserva os campos por linha e reúne os motivos de pesquisa incompleta por alias sem duplicar.

```json
{"empresa":"realmak","exigencia":"<texto do edital>","fonte":"TR 8.3","eliminatoria":true,
 "estado":"prova_lida|vias_esgotadas|falha|pendente",
 "tentativas":[{"via":"cerebro_buscar","consulta":"<termo ou identificador>","resultado":"<motivo, achado ou via esgotada>"}]}
```

`prova_lida` indica que a cópia foi aberta e confrontada, independentemente do parecer. `vias_esgotadas` exige registro das vias aplicáveis consultadas e mantém `verificar` se faltar prova. Use `falha` para erro, teto, tempo ou executor interrompido e `pendente` para etapa ainda não executada. Nem saída ausente nem lacuna documental vira `nao_atende` sem evidência de impedimento. A consolidação só altera a síntese e a indicação da mais aderente, preservando as provas e as lacunas. Use `atende` para prova aplicável conferida; `parcial` para dúvida de equivalência ou atendimento condicionado a ação demonstrável; `nao_atende` para impedimento comprovado; `verificar` se faltar prova, leitura ou cobertura. Para certidão emitível ou declaração a preparar, descreva o canal, a ação e o responsável sem afirmar que já existe documento válido.

Se o item da empresa não concluir nesta rodada, o daemon pode entregar a última avaliação válida (`empresas[]` não vazio) no parcial `analise/habilitacao/<alias>.json`, com `rodada_anterior: {avaliado_em, motivo}` na raiz. Preserve os pareceres, provas, ações e cobertura desse parcial. Inclua a empresa na avaliação de `mais_aderente` pelos mesmos critérios e indique em `empresas[].resultado` que a avaliação vem da rodada anterior, com a data quando disponível.

Somente para empresas cujo item não concluiu e que não têm avaliação válida entregue, recrie as linhas `verificar` a partir do edital, com grupo e lacuna documental. Em ambos os casos, registre a falha operacional da rodada atual em `pesquisa_incompleta`, sem substituir uma avaliação válida por uma lacuna.

### Pesquisa de peças

`fontes/pecas.json` contém `versao: 1`, `estado: "concluida"|"parcial"|"nao_se_aplica"`, `cotacoes_online` com a linha de oferta descrita em `tecnica.json` e `pendencias` com `item` e `motivo`. Cada oferta identifica a peça ou kit e preserva compatibilidade, embalagem e frete em `observacao`. Preço sem oferta confirmada fica em `pendencias` sem valor fictício. Se a análise técnica ainda não existir, extraia o escopo do edital/TR e use os identificadores dele; a precificação faz a correspondência. Peças sob demanda fora do lance ficam identificadas à parte em `pendencias` e não entram no custo recorrente. Registre em `estimativas[]` cada referência sem oferta confirmada com `item`, `preco_unit`, `unidade`, `base`, `data` se conhecida e `observacao`. A base identifica a faixa, o histórico ou o produto análogo. Use `cobertura` com `total`, `com_oferta`, `com_estimativa` e `sem_referencia`, contando cada item uma vez. A precificação usa as duas listas e declara a cobertura; o campo de ofertas mantém o formato atual.

`tecnica.json` (`analisar-edital-manutencao` ou `analisar-edital-fornecimento`):

```json
{"versao": 1, "gerado_em": "", "tipo": "manutencao|fornecimento",
 "conclusao": {"viavel": "sim|com_ressalvas|nao", "resumo": "", "ressalvas": [""]},
 "itens": [{"item": "", "descricao": "", "quantidade": 0, "unidade": "", "exigencias": [""], "atende": "sim|nao|verificar", "fonte": ""}],
 "cotacoes_online": [{"item": "", "preco_unit": 0, "unidade": "", "fornecedor": "", "link": "", "data": "", "observacao": ""}],
 "escopo": [{"frente": "", "descricao": "", "fonte": ""}],
 "equipe": [{"funcao": "", "quantidade": 0, "jornada": "", "fonte": ""}],
 "sla": [{"indicador": "", "exigido": "", "viavel": "sim|nao|verificar", "fonte": ""}],
 "entrega": {"prazo": "", "local": "", "fonte": ""},
 "dimensionamento": {"carga_horas_mes": 0, "horas_disponiveis_mes": 0, "cobertura_pct": 0, "folga_pct": 0, "primeiro_ciclo": "", "pior_sla": ""},
 "arquivos": [{"rotulo": "", "caminho": ""}]}
```

`itens` vale para fornecimento e para peças da manutenção; `escopo`, `equipe` e `sla` só para manutenção. `cotacoes_online` é a pesquisa de preço por item na internet (preço real, link individual da oferta, data), que vinha do relatório antigo e passa a ser parte de `analisar-edital-fornecimento`.

`precificacao.json` (`precificar-proposta-exequibilidade`; preços de peças por `cotar-pecas-materiais-licitacoes`):

```json
{"versao": 1, "gerado_em": "", "valor_estimado": 0,
 "custo_mensal": 0, "preco_mensal": 0, "preco_global": 0, "bdi_pct": 0, "margem_pct": 0,
 "exequivel": "sim|no_limite|nao", "resumo": "",
 "cenarios": [{"nome": "", "preco_global": 0, "margem_pct": 0, "exequivel": "sim|no_limite|nao"}],
 "componentes": [{"componente": "mao_de_obra|operacao|pecas|tributos|margem", "valor_mensal": 0, "fonte": ""}],
 "cotacoes_online": [{"item": "", "preco_unit": 0, "unidade": "", "fornecedor": "", "link": "", "data": "", "observacao": ""}],
 "arquivos": [{"rotulo": "", "caminho": ""}]}
```

Em `precificacao.json`, `tributos_pct` e `margem_minima_pct` opcionais registram os pontos percentuais efetivamente usados no cenário-base, e `margem_pct` fica com a margem calculada. O score lê esses valores e só identifica como hipótese o padrão utilizado por falta de dado. Na ausência de alíquota explícita, o score pode calculá-la com o componente mensal de tributos e o preço mensal do mesmo cenário-base.

Em `tecnica.json` e `precificacao.json`, `premissa_decisiva` (booleano opcional) indica que a conclusão-base ainda depende de hipótese que muda equipe ou recomendação. Marque `true` somente se a hipótese ainda afetar a conclusão publicada. Cite a hipótese e a lacuna no resumo e mantenha o seu efeito em cenário alternativo. O score trata essa dimensão como inconclusiva. Saídas antigas continuam válidas.

Acréscimos:

- `cotacoes_online[]`: uma linha por oferta usada; `item` é o de `itens[].item`; `observacao` leva condição comercial, frete, embalagem, "BASE DE CUSTO … compatibilidade não confirmada" e referência de compra pública. Em `tecnica.json`, fornecimento; em `precificacao.json`, peças da manutenção.
- `dimensionamento` (só manutenção): os números que o script da skill imprimiu (carga, horas disponíveis, cobertura, folga), mais o primeiro ciclo e o pior SLA em texto. Desconhecido é `null`.
- `arquivos[]` (`tecnica.json` e `precificacao.json`): entregas da skill para o analista abrir pelo card, `caminho` relativo à pasta do agente (`analise/…`). O daemon publica à vista os `.html` e as planilhas `.xlsx`; ignora o resto, caminho com `..` e arquivo fora da pasta. Na manutenção, o relatório principal é o painel `analise/analise-manutencao.html`; o Odoo só roda o script dele se for o do `painel.py` da skill.

Exemplo dos quatro arquivos: [exemplo/analise/](exemplo/analise/).
