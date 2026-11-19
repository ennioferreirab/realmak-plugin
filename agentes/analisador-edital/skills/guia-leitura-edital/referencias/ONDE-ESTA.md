# Onde está cada informação

Gerado de [catalogo.json](catalogo.json) (fonte única) e da medição de 2026-10-15 em 40 licitações do CRM. **Ordem** = onde procurar primeiro. **Medição** = em quantas licitações com aquele tipo de documento o termo aparece (presença) e quanto das ocorrências cai em cada tipo (participação). Regerar: `python3 scripts/localizar.py --guia`.

| Informação | Seções | Ordem de leitura | Medição (presença / participação) | Atenção |
|---|---|---|---|---|
| Data e hora da sessão | s1, s2 | Edital → Outros | Edital 89% / 97% · TR 22% / 1% | Edital pode dizer só "conforme PNCP": aí vale o manifesto do CRM ou o PNCP. |
| Valor estimado / teto | s1, s2, s3 | Edital → TR → ETP → Planilha | Edital 95% / 70% · TR 78% / 18% | Pode ser sigiloso (art. 24): procurar "sigiloso". |
| Critério de julgamento e adjudicação | s1, s7 | Edital → TR | Edital 97% / 77% · TR 74% / 19% |  |
| Modo de disputa e intervalo mínimo | s6, s7 | Edital | Edital 54% / 96% · ETP 10% / 4% |  |
| ME/EPP: exclusividade, cota, empate | s6 | Edital → TR | Edital 76% / 86% · TR 70% / 12% | TR às vezes recomenda dispensar o benefício e o edital aplica: vale o edital. |
| Margem de preferência | s6 | Edital | — |  |
| Esclarecimento e impugnação (prazo e canal) | s2, s4 | Edital | Edital 62% / 98% · TR 13% / 2% |  |
| Habilitação técnica (atestados, CAT, registro) | s2, s4 | TR → Edital → ETP | Edital 68% / 56% · TR 83% / 34% | Na Lei 14.133 os requisitos técnicos costumam estar no TR; o edital remete a ele. Ler os dois. |
| Habilitação econômica (índices, PL, capital) | s2 | Edital → TR | Edital 38% / 57% · TR 48% / 39% |  |
| Regularidade fiscal e trabalhista | s2 | Edital → TR | Edital 89% / 62% · TR 78% / 35% |  |
| Especificação técnica do objeto | s3, s4, s5 | TR → Outros → ETP → Edital | TR 70% / 63% · Edital 84% / 28% | Caderno de especificações e anexos técnicos costumam ser classificados como TR ou Outros. |
| Marca, modelo, catálogo, ficha técnica | s4, s5 | TR → Edital | TR 61% / 68% · Edital 51% / 30% |  |
| Itens e quantitativos | s3, s5, s7 | Planilha → TR → Edital → ETP | Edital 86% / 55% · TR 87% / 19% | Na planilha (xlsx) o texto vem sem cabeçalho de coluna: conferir no original. |
| Prazo de entrega ou execução | s2, s5 | TR → Edital → Minuta | Edital 62% / 70% · TR 57% / 20% |  |
| Local de entrega ou execução | s2, s5 | TR → Edital → Minuta | Edital 62% / 56% · TR 70% / 36% |  |
| Visita técnica / vistoria | s3, s4 | Edital → TR | Edital 51% / 59% · TR 57% / 31% |  |
| Amostra / prova de conceito | s2, s4 | Edital → TR | Edital 68% / 80% · TR 43% / 17% |  |
| Garantia contratual (% e momento) | s2, s7 | Minuta → Edital → TR | Edital 51% / 51% · TR 52% / 33% |  |
| Garantia do produto ou serviço | s4, s7 | TR → Edital | TR 91% / 52% · Edital 27% / 42% |  |
| Condições e prazo de pagamento | s2, s7 | TR → Edital → Minuta | Edital 54% / 54% · TR 87% / 39% |  |
| Penalidades e multas | s2, s7 | Minuta → Edital → TR | Edital 97% / 63% · TR 91% / 28% |  |
| Reajuste e repactuação | s7 | Minuta → TR → Edital | Edital 65% / 48% · TR 74% / 32% |  |
| Subcontratação | s2, s5 | TR → Edital → Minuta | Edital 78% / 43% · TR 96% / 39% |  |
| Consórcio | s2 | Edital → TR | TR 48% / 47% · Edital 86% / 46% |  |
| Equipe, responsável técnico, NR | s2, s4 | TR → Edital | Edital 70% / 56% · TR 74% / 29% |  |
| Obrigações da contratada | s4, s7 | TR → Edital → Minuta | Edital 43% / 61% · TR 43% / 31% |  |
| Vigência do contrato | s2, s7 | Minuta → TR → Edital | Edital 84% / 58% · TR 91% / 30% |  |
| Níveis de serviço (SLA, IMR) | s3, s7 | Outros → TR | — | Costuma vir em anexo próprio, classificado como Outros. |
| BDI, encargos e composição de custos | s3, s7 | Planilha → Edital → TR | Edital 62% / 45% · Planilha 67% / 26% |  |
| Preço unitário de referência | s3, s7 | Planilha → Edital → TR → Outros | Edital 95% / 70% · TR 57% / 17% |  |
| Inexequibilidade | s3, s7 | Edital | Edital 95% / 92% · TR 22% / 3% |  |
| Pesquisa de preços (origem do teto) | s3, s6 | ETP → Outros → Edital | Edital 38% / 57% · ETP 70% / 22% | Mapa de preços costuma vir como anexo Outros; o ETP diz quantas fontes e quais. |
| Modelo de proposta e planilha exigida | s7 | Edital → Outros → Planilha | — | Define a saída adaptada da precificação. |

Tipos: **Edital** = Edital · **TR** = Termo de referência · **ETP** = Estudo técnico preliminar · **Minuta** = Minuta de contrato · **Planilha** = Planilha de preços · **Outros** = Outros.
