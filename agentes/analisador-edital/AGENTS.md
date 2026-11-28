# AGENTS.md — Analisador de Edital (REALMAK)

Regras comuns a todas as skills. Uma skill nunca contraria este arquivo.

**Princípio central: qualidade da análise em 1º lugar.** Não criar tetos artificiais de chamadas nem prazos curtos que cortem pesquisa válida.

O agente recomenda, com fonte, **se e a que preço disputar**; decisão e envio são humanos. O daemon roda um gestor por licitação ([GESTOR.md](GESTOR.md)), que decide nos portões do `fluxo.json`; o fluxo define a ordem. Cada skill roda como item, lê as fontes de `agents/<nome_agente>/` e grava só a sua saída. As skills de análise e precificação vêm diretamente do realmak-plugin ([§7](#skills-do-realmak-plugin)); o item de cada uma grava as entregas da skill e o JSON que o card mostra em `analise/`. A análise publica sem esperar cotação; e-mail a fornecedor só quando o analista pede no card.

## 1. Mapa

| Necessidade | Skill ou artefato |
|---|---|
| Coletar documentos e campos mínimos faltantes no portal (E0) | [coletar-edital](skills/coletar-edital/SKILL.md) → `fontes/coleta.json` |
| Ler a licitação e saber onde gravar | [pasta-licitacao](skills/pasta-licitacao/SKILL.md) |
| Onde está cada informação no edital | [guia-leitura-edital](skills/guia-leitura-edital/SKILL.md) → `fontes/mapa_leitura.json` |
| Análise geral do edital: atenção, prazos, habilitação exigida, declarações, proposta, impugnação, perguntas ao técnico, avisos | [analisar-edital](../../plugins/realmak/skills/analisar-edital/SKILL.md) (plugin) → `analise/edital.json` |
| Qual empresa do grupo atende à habilitação (AForça, Realmak, UNA, Nortfort; nunca Sublime) | [analisar-habilitacao](../../plugins/realmak/skills/analisar-habilitacao/SKILL.md) (plugin) → parciais das empresas selecionadas em `analise/habilitacao/` e consolidação em `analise/habilitacao.json` |
| Análise técnica pelo tipo de objeto (herda atestados/CATs validados de `habilitacao.json`) | [analise-tecnica](skills/analise-tecnica/SKILL.md) (do agente) → [analisar-edital-manutencao](../../plugins/realmak/skills/analisar-edital-manutencao/SKILL.md) ou [analisar-edital-fornecimento](../../plugins/realmak/skills/analisar-edital-fornecimento/SKILL.md) (plugin) → `analise/tecnica.json` e o relatório HTML da skill |
| Preço online de peças e itens, com link da oferta | [cotar-pecas-materiais-licitacoes](../../plugins/realmak/skills/cotar-pecas-materiais-licitacoes/SKILL.md) (plugin; item `pecas` em paralelo em E2 → `fontes/pecas.json`) |
| Preço, cenários e exequibilidade | [precificar-proposta-exequibilidade](../../plugins/realmak/skills/precificar-proposta-exequibilidade/SKILL.md) (plugin) → `analise/precificacao.json` (com `empresa_precificada`) e a planilha da proposta |
| E-mails de cotação a fornecedores, só a pedido do analista; leitura das respostas | [cotacao-fornecedor](skills/cotacao-fornecedor/SKILL.md) |
| Score e nota | `score.py` (T0, em E3 após `precificacao`); regras em [score](skills/score/SKILL.md) |
| Triagem estruturada no Cérebro das 4 empresas ativas | [cerebro](../../plugins/realmak/skills/cerebro/SKILL.md) → `fontes/triagem_cerebro.json` (E1, após `edital`). Os itens de habilitação selecionados pesquisam pelo alias do item e usam as pistas de `fontes/triagem_cerebro.json`. |
| Contrato das saídas (o card lê) | [referencias/card/CONTRATO.md](referencias/card/CONTRATO.md) · [exemplo](referencias/card/exemplo/analise/) |
| Modelo de esclarecimento e impugnação | [referencias/MODELO-ESCLARECIMENTO.md](referencias/MODELO-ESCLARECIMENTO.md) |
| Catálogos e datasheets | [referencias/BIBLIOTECA-TECNICA.md](referencias/BIBLIOTECA-TECNICA.md) |
| Táticas de preço da Luciene | [referencias/TATICAS-LUCIENE.md](referencias/TATICAS-LUCIENE.md) |
| Habilitações e certificados da empresa | [referencias/habilitacoes-certificados/](referencias/habilitacoes-certificados/) |
| Categorias de interesse (foco, adjacente, fora) e equipamentos | [referencias/categorias.yaml](referencias/categorias.yaml) |
| Preços de disputas anteriores | [referencias/precos/](referencias/precos/) |
| ConLicitação (mercado, concorrentes, contratos), só leitura | [referencias/conlicitacao/PERFIL.md](referencias/conlicitacao/PERFIL.md) |
| Resumo IA do ConLicitação (sugestão externa) | `<pasta>/resumo_conlicitacao.json`; pasta-licitacao, passo 2 |
| Skill nova | [templates/SKILL.md](templates/SKILL.md) e [templates/DECISOES.md](templates/DECISOES.md) |

## 2. Parâmetros

As skills leem estes valores e nunca os repetem fixos no texto.

```yaml
empresa: do_cartao                 # a empresa da análise é a da linha "Empresa deste cartão" do pedido, nunca fixa; REALMAK só se a linha faltar
empresas:                          # regime tributário: simples | lucro_real | a_confirmar (use o da empresa do cartão)
  REALMAK SERVIÇOS E COMÉRCIO LTDA: {regime: simples}
  FORÇA COMERCIAL E SERVIÇOS LTDA: {regime: lucro_real}
  UNA ENGENHARIA: {regime: a_confirmar}
  NORTFORT COMERCIO E SERVICOS LTDA: {regime: a_confirmar}
  SUBLIME: {regime: a_confirmar}
grupo:                             # não são concorrentes; só uma empresa do grupo disputa cada licitação. Profissionais (RT, CAT) podem atuar em mais de uma empresa: não é risco de conluio nem alerta
  - {nome: REALMAK SERVIÇOS E COMÉRCIO LTDA, cnpj: "03.496.338/0001-74"}
  - {nome: FORÇA COMERCIAL E SERVIÇOS LTDA, cnpj: a_confirmar}
  - {nome: UNA ENGENHARIA, cnpj: a_confirmar}
  - {nome: NORTFORT COMERCIO E SERVICOS LTDA, cnpj: "02.479.932/0001-94"}
  - {nome: SUBLIME, cnpj: a_confirmar}
nome_agente: analisador-edital          # saída em <licitacao>/agents/<nome_agente>/
pasta_licitacoes: "/data/conlicitacao/licitacoes/"   # no daemon; fora dele, a pasta montada do acervo (scripts: PASTA_LICITACOES)
valor_minimo_disputa: 100000       # R$, sobre a parte que a empresa disputaria
regioes_atuacao: [DF, GO, MG, PA]  # fora delas: ponto de atenção; pode ser oportunidade
categorias: referencias/categorias.yaml   # foco | adjacente | fora vem da categoria; sem categoria = adjacente
portfolio_exclusivo: false         # fora do foco é avaliado se a margem for boa
habilitacao_elimina: false         # falta de habilitação não elimina; avalia obtenção rápida
referencias_compartilhadas:
  habilitacoes: referencias/habilitacoes-certificados/
  conlicitacao: referencias/conlicitacao/PERFIL.md   # companyId 30933, filter_id 44760; cl.py, só GET
crm_resumo:                        # resumo IA do ConLicitação, baixado uma vez pelo CRM
  arquivo: resumo_conlicitacao.json   # na pasta da licitação
  container: realmak-crm-postgres-1   # transitório, só fora do daemon (docker exec)
  precos: referencias/precos/EMPRESAS_PRECOS_FILTRADA.xlsx
cerebro:                           # ferramentas cerebro_* (MCP da Realmak, só leitura); empresas em contexto/empresas.json
  os: windows                      # sistema onde os analistas abrem os originais (parâmetro exigido pelas ferramentas cerebro_*)
  limite_trechos: 15
score:                             # regra na skill score; quem calcula é score.py
  pontos: {triagem: 30, lote: 30, margem: 40}   # podemos participar?, dá para executar?, dá lucro?
  faixas_nota: {baixa: 0, media: 30, oportunidade: 55, alta: 75}
janela_precos_anos: 2              # preços mais antigos não entram
cotacao:
  email_envio: conta conectada em Painel de controle → E-mail   # o Odoo envia e recebe
  sigilo_oportunidade: omitir      # o pedido não cita órgão nem licitação; muda só por DECISOES
  prazo_resposta_dias_uteis: 3     # nunca depois de prazo_limite_dias_antes_sessao
  prazo_limite_dias_antes_sessao: 2   # dias corridos antes da sessão (a confirmar)
  checagens:                       # a confirmar
    cobrar_apos_dias_uteis: 2      # checagem 1: cobra quem não respondeu
    final: prazo_limite            # quem não respondeu vira "sem resposta"
  regras_quantidade:               # orientação; falta de fornecedor não segura relatório nem vira pendência
    - se: marca_exclusiva_no_edital
      consultar: fabricante + até 2 canais autorizados
      respostas_minimas: 1
    - se: custo_relevante
      consultar: 3 (ao menos 1 fabricante, se houver)
      respostas_minimas: 2
    - se: mercadoria_comum
      consultar: 2 (revendedor aceito)
      respostas_minimas: 1
    - se: respostas_abaixo_do_minimo_na_checagem_1
      acao: ampliar com mais 2 fornecedores
precificacao:
  tributos_pct: 15                 # hipótese até confirmação da empresa (Luciene); % sobre a receita
  margem_minima_pct: 10            # hipótese até confirmação da empresa (Luciene); % sobre a receita
  cobertura_regua: 80              # preço online para os itens que somam esta % do valor; orientação
```

## 3. Comportamentos comuns

1. **Nunca descartar sozinho.** Classificar com a nota e explicar; o descarte é humano.
2. **Oportunidade financeira é regra máxima.** O que fizer sentido financeiramente, mesmo fora do foco, da região ou sem habilitação hoje, fica registrado com o porquê (ponto de atenção do edital ou resumo da precificação), nunca descartado em silêncio.
3. **Todo fato com fonte:** arquivo + página ou trecho literal. Fato separado de inferência. Conhecimento do agente é inferência: rotulado, nunca confirma atendimento nem vira custo.
4. **Ter documento ≠ estar válido.** Usar a data impressa; marcar o que precisa renovar ou reconsultar.
5. **Nada sai da empresa sem aprovação.** E-mails, esclarecimentos e impugnações: o agente redige, uma pessoa aprova e envia.
6. **Pendência nunca bloqueia.** Falta de cotação, resposta ou documento fica como lacuna no item ou lote afetado; o resto conclui.
7. **A pasta da licitação é só leitura**, exceto `agents/<nome_agente>/`.
8. **Datas absolutas** (AAAA-MM-DD); **valores em R$** com data-base e origem.
9. **Objetividade.** Frases curtas; só o trecho que sustenta a conclusão.
10. **O card é o relatório.** As skills gravam JSON no contrato do plano; nenhuma escreve HTML. Planilha exigida pelo órgão mantém o formato do órgão.
11. **IA externa é índice.** Resumos de terceiros não conhecem a estratégia da Realmak: conferir o fato na fonte e refazer o juízo. Rotular `Sugestão ConLicitação`.
12. **Pesquise antes de pedir.** Acervo, cérebro, ConLicitação e online vêm antes de qualquer pendência ou pergunta. Pendência é só o que a empresa precisa fazer, decidir ou aprovar. Falta de pesquisa do agente não vira tarefa da analista.
13. **Cada coisa num lugar.** Exigências, prazos e regras do edital em `edital.json`; quem atende à habilitação em `habilitacao.json`; execução, itens e preço online dos itens de fornecimento em `tecnica.json`; preço, cenários e preço online de peças de manutenção em `precificacao.json`. Os outros arquivos citam o lugar.
14. **Escreva só o que decide.** Sem descrever o que não se aplica, busca vazia sem efeito ou falha de ferramenta sem impacto. Cobertura incompleta: uma frase, com o efeito.
15. **Problemas sistêmicos na hora.** Qualquer etapa ou portão deve chamar `registrar_nota_urgente` assim que identificar um problema sistêmico do grupo (sem esperar a precificação), usando `chave` estável conforme `../contexto/prompt_sistema.md`.

## 4. Saídas e relatório

As quatro saídas da análise ficam em `agents/<nome_agente>/analise/`, no [contrato do card](referencias/card/CONTRATO.md); o card da licitação as mostra. Toda lista pode vir vazia; desconhecido é `null`, nunca 0. `fonte` é o rótulo curto (`Edital 8.3`, `TR 9.15`); no texto, o fato do edital fica separado da conclusão.

| Origem | Como citar no campo `fonte` ou no texto |
|---|---|
| Edital | documento + item ou página (`Edital 8.3`, `TR anexo I, item 2`) |
| Cérebro | empresa de origem (Realmak, A Força, Nortfort, Una ou Sublime) + título do documento + data do documento |
| Referências do agente | caminho do arquivo + id do registro |
| ConLicitação | rota + data da consulta |
| Online | URL da página individual + data da consulta |

O relatório é o da skill: `analise/analise-fornecimento.html` (fornecimento) ou o painel `analise/analise-manutencao.html` (manutenção, com o relatório de impressão `analise/analise-manutencao-relatorio.html`), listados em `arquivos` do JSON, com as planilhas `.xlsx` das skills. O daemon publica no card os `.html` e as `.xlsx` de `analise/`; o Odoo só deixa rodar o script do painel gerado pelo `painel.py` da skill. Não há relatório genérico.

## 5. Score

Score 0–100 e nota 1–5 vêm só do `score.py` ([skill score](skills/score/SKILL.md)). O score responde "vale analisar?": podemos participar, dá para executar e dá lucro. Não é exato nem probabilidade de vencer; falta de dado dá pontos parciais, nunca zera. Margem leva "hipótese: tributos <`precificacao.tributos_pct`>%, margem mínima <`precificacao.margem_minima_pct`>%" enquanto os dois forem hipótese.

## 6. Padrão das skills

Cada skill do agente fica em `skills/<nome>/` com `SKILL.md` ([modelo](templates/SKILL.md)) e `referencias/DECISOES.md`; as do plugin seguem o §7. A skill traz descrição operacional, entradas, passos e saídas, sem seções vazias. Regras decididas ficam em DECISOES; leia antes de mudá-las. As do fluxo e do gestor ficam em [DECISOES.md](DECISOES.md). Referências compartilhadas são citadas, não copiadas.

## 7. Skills do realmak-plugin

O daemon usa `skills/` para as sete skills locais (`coletar-edital`, `pasta-licitacao`, `guia-leitura-edital`, `analise-tecnica`, `conferir-habilitacao`, `cotacao-fornecedor`, `score`) e `../../plugins/realmak/skills/` para as compartilhadas. Faça mudanças nas skills compartilhadas na árvore do plugin. A conversa manual e o agente usam os mesmos arquivos.

| A skill pede | Aqui |
|---|---|
| Skill `licitacao`, MCP, anexos da conversa, portal | Pasta da licitação, com `manifesto.json`, documentos e textos em `extraidos/`. Use [pasta-licitacao](skills/pasta-licitacao/SKILL.md) e [guia-leitura-edital](skills/guia-leitura-edital/SKILL.md). Se faltar documento, consulte a página oficial em leitura. |
| Skill `cerebro` | O item `triagem-cerebro` (E1) segue o [contrato de triagem no Cérebro](referencias/cerebro.md), consultando apenas `realmak`, `nortfort`, `aforca` e `una` (nunca `sublime`). Cada item `pesquisa-habilitacao-<alias>` selecionado em G1 pesquisa a própria empresa e segue todas as pistas de `fontes/triagem_cerebro.json`. |
| Aquisição, controle e leitura da habilitação | Use a integração do daemon descrita abaixo. O manual usa os comandos portáteis da skill. |
| Base de custos | `fontes/base-custos.json`, entregue pelo daemon. Sem base, declare a hipótese do §2 e a limitação. |
| `compras-publicas`, `conlicitacao` | `buscar_web` e [referencias/conlicitacao/PERFIL.md](referencias/conlicitacao/PERFIL.md). |
| Pasta do processo e entrega na conversa | Grave na pasta da análise do agente. Perguntas viram `perguntas_tecnico` ou ressalvas. Só o gestor pergunta, no portão. |

Nos itens `pesquisa-habilitacao-<alias>` (T1), registre candidatos por exigência, incluindo as pistas dirigidas, no caminho definido no fluxo, conforme o [contrato de aquisição](referencias/habilitacao-aquisicao.md). O daemon arquiva todos os candidatos em área privada com `arquivar_para`, tenta novamente em falha transitória, verifica o SHA-256 e entrega o estado por candidato. Nos itens `habilitacao-<alias>` (T2), abra e confronte todos os originais baixados. Registre arquivo, página, seção ou aba, trecho literal e titular, vigência, escopo e quantitativo, conforme a exigência. Confronte OCR decisivo com a imagem. Falha final de download fica explícita com a causa. Uma cópia baixada que continue ilegível exige registro das tentativas de leitura. Grave apenas a prova necessária no JSON compartilhado.

- **Habilitação.** Siga o [contrato do card](referencias/card/CONTRATO.md) para os parciais, a cobertura e a consolidação. A consolidação preserva as provas das empresas aprofundadas, traz resumo curto da triagem para empresas puladas em G1 e sinaliza pesquisas falhas; não reabre a pesquisa nem elege "preferida" entre duas indeterminadas com base apenas em certidões secundárias. Certidões emitíveis na hora (CNPJ, RFB/PGFN, FGTS, CNDT, falência/concordata, cadastros simples) são checadas em 1 consulta SQL (`reg_certidao`).
- **Peças.** O item `pecas` parte do edital/TR e grava as ofertas e lacunas em `fontes/pecas.json`, no [contrato do card](referencias/card/CONTRATO.md#pesquisa-de-peças). A precificação usa a fonte já gravada; se faltar preço, sinaliza a lacuna e segue com premissa explícita.
- **Dimensionamento e custo.** A análise técnica (`tecnica`) depende de `habilitacao` e herda os atestados/CATs validados em `analise/habilitacao.json` para nunca contradizer a habilitação. Use a memória do órgão na base, com as fontes. Uma hipótese que muda a equipe ou a recomendação só entra como cenário alternativo. Em `tecnica.json` e `precificacao.json`, use `premissa_decisiva: true` se a base continuar condicionada pela falta de informação decisiva.
- **Precificação.** Use estritamente a `empresa_escolhida` de G2 (fallback: `habilitacao.json.mais_aderente`) e grave obrigatoriamente `empresa_precificada` (alias) em `analise/precificacao.json` — nunca precifique a Realmak silenciosamente quando G2 escolheu outra empresa. Bloqueie o uso de premissas/planilha de manutenção em licitações de obra ou reforma sem planilha orçamentária válida. Nunca reaplique encargos sobre custo-hora já carregado da `base-custos.json`. Com alíquota de tributos ausente (`una`) ou frágil (`n=1` em `nortfort`/`aforca`), deixe a margem definitiva em aberto ou simule faixa tributária explícita sinalizando confirmação contábil. Em manutenção, grave os dados e gere o Excel pelo script da skill. Em fornecimento, use as `cotacoes_online` de `tecnica.json` como custo de compra e confira frete, tributos e margem. Liste os arquivos abertos pelo card em `precificacao.json`.
- **Pedido de precificação do card.** Se o prompt do item `precificacao` trouxer "Pedido de precificação do usuário (JSON)" (ou existir `fontes/pedido_precificacao.json`; rodada parcial só de `precificacao` e `score`, pedida pelo analista em "Nova precificação"), a skill de precificação parte do `analise/precificacao.json` atual e aplica o pedido (preço, desconto, margem ou premissas) com `aplicar_pedido.py`, sem refazer as outras fases. O preço do pedido vira o preço-alvo e o anterior fica como cenário `Preço-alvo anterior`. Planilha, proposta de preços e cotações novas só se o pedido marcar `atualizar_planilha`, `gerar_proposta` ou `buscar_cotacoes`. Formato em [CONTRATO.md](referencias/card/CONTRATO.md#pedido-de-precificação).

Quando o executor disponibilizar `licitacao_buscar_fontes`, use o `lead_id` do card para localizar cláusulas por peça, item, página física ou texto. Cite o trecho e o link estável retornados; confira todas as ocorrências antes de atribuir a fonte.
