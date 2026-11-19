# Decisões — score

Registro das regras decididas com o usuário. A mais recente vale; decisões substituídas ficam marcadas, não apagadas.

| # | Data | Decisão | Motivo | Decidido por | Situação |
|---|---|---|---|---|---|
| 1 | 2026-10-15 | Criar um **score geral** calculado numa skill própria (`score`), que é a única fonte da regra. Cada seção pontuável tem o seu score. | Comparar licitações com a mesma régua e responder se a concorrência entra na nota. | Ennio | cálculo substituído por #10 (script) |
| 2 | 2026-10-15 | No relatório, sem explicação em texto: o cálculo aparece só no **tooltip** do número (ao passar o mouse), direto ao ponto. | Relatório objetivo. | Ennio | vigente |
| 3 | 2026-10-15 | Concorrência entra no score geral como seção pontuável (peso 20), pela margem no preço provável do vencedor. | Responde a pergunta 6 da skill concorrencia. | Claude (proposta, a validar) | substituída por #12 |
| 4 | 2026-10-15 | Pesos, faixas de margem, faixas da nota, confiança mínima e travas conforme o SKILL.md (valores iniciais em `score` no AGENTS.md). | Ponto de partida; calibrar com licitações reais. | Claude (proposta, a validar) | substituída por #10 |
| 5 | 2026-10-15 | **3 — Inconclusivo** passa a ser decidido pela **confiança** (dados insuficientes), não por uma faixa do score. | A escala da nota mistura qualidade (1, 2, 4, 5) e falta de dado (3). | Claude (proposta, a validar) | substituída por #10 |
| 6 | 2026-10-15 | Habilitação ❌ **com caminho alternativo pendente** (ex.: esclarecimento ao órgão) vale 5 na triagem, sem trava. | Lacuna achada no cálculo da 19482164. | Claude (calibração, a validar) | substituída por #10 |
| 7 | 2026-10-15 | Seção ⏳ com score calculável entra com o score atual e metade do peso na confiança. | Quase toda seção fica ⏳ por dias (fornecedor, órgão); sem isso nenhuma licitação teria score. | Claude (calibração, a validar) | substituída por #10 |
| 8 | 2026-10-15 | Trava prevalece sobre a confiança: com trava, nota 1. | Na 19478221, a confiança baixa daria "Inconclusivo" apesar de barreira sem caminho. | Claude (calibração, a validar) | mantida em #12 |
| 9 | 2026-10-15 | Exigência ❌ com caminho alternativo pendente **limita o score da triagem a 50** (além dos 5 pontos da #6). | Na 19482164, o atestado ❌ só tirava 15 pontos e a tendência ficava em 77 (faixa Alta), otimista para uma barreira que depende do órgão. | Ennio | substituída por #10 |
| 10 | 2026-10-19 | Score calculado pelo script `score.py` (T0) a partir do bloco `dados`; nenhuma skill grava `score`. Score = 0,25 A + 0,20 T + 0,20 C + 0,35 M, em intervalo quando falta dado, sem redistribuir pesos; habilitação sai da aderência. Confiança = 100 × P × (0,80 + 0,15 K + 0,05 H), pela evidência de custo ponderada por valor (`pesos_fonte`); homologado é mercado, peso 0 no custo. Item `trivial` fora de T; sem exigência decisiva, H = 1. Nota 3 quando cobertura < `cobertura_minima` (50) ou largura > `largura_maxima` (30), com "a definir" no número; senão, ponto médio. Tributos 15% e margem mínima 10% como hipótese. | Os dois casos do piloto saíam com o mesmo 50 e confiança 22,5–25% sem evidência de preço. Fonte: plano `docs/superpowers/plans/2026-10-19-aprimorar-skills-precificacao.md`, consenso R2 e escolha "Hipótese provisória" de Ennio. | Ennio (plano e hipótese); consenso R2 | substituída por #12 |
| 11 | 2026-10-19 | R3b: cobertura econômica, ponderada por `cobre` como no `score.py` (B7). Custo completo = Σ componentes da s7; `s3.custos_extras` não somam de novo (B9). `decisiva` vale para toda incomum que muda a decisão, qualquer situação (B11). "A definir" só por largura; cobertura baixa dá nota 3 sem esconder o score (B24). Confiança por escopo em `topo.json.confianca.escopos` (B4). | Revisão adversarial R3b. | Main (Contract R3b) | substituída por #12 |
| 12 | 2026-10-20 | Score simples, de recomendação de análise: triagem 30 + lote interessante 30 + margem 40. Falta de dado dá pontos parciais, nunca zera; sem intervalos. Confiança, cobertura, largura e scores por seção saem do relatório. Nota: trava → 1; lote para disputar ou validar sem margem calculada → 3; senão, faixas da nota. `topo.score` é número. | Ennio: "essa conta maluca do score de confiança não faz sentido… tem margem, tem lote interessante, tem triagem razoável, isso já vale o score quase máximo. Esse score tem mais relação com recomendação de análise." | Ennio | vigente |
| 13 | 2026-11-16 | O score passa a ler só as saídas novas da análise: habilitação (Podemos participar?), conclusão técnica (Dá para executar?) e margem da precificação (Dá lucro?), com os mesmos pontos (30/30/40) e faixas. Travas: sessão perto demais, nenhuma empresa habilitável, técnica "não atende", preço inexequível. Substitui as regras por seção (s2, s4, s6, s7). | Pedido de Ennio, skills do realmak-plugin#16; orientação de 16/11/2026 (manter o score só se ler pouco dos JSON novos: lê quatro campos). Mantém o Score IA do card. | Ennio (orientação); desenvolvedor (conta) | vigente |

## Calibração 2026-10-15

| Licitação | Nota anterior (manual) | Score | Confiança | Nota pelo score | Observação |
|---|---|---|---|---|---|
| 19478221 SENAPPEN raio X | 1 Baixa | 20 (triagem 60, travada) | 25% | 1 Baixa | Bate. |
| 19482164 MPM CSNET | 3 Inconclusivo | 58 (tendência; era 77 antes da #9) | 22,5% | 3 Inconclusivo | Bate na nota; com o limite da #9, a tendência fica em Oportunidade. |

## Perguntas em aberto

- [x] Pesos iniciais e faixas de margem: substituídos pelos pontos da #12.
- [x] Confiança mínima de 60% para sair do "Inconclusivo": substituída por `cobertura_minima` e `largura_maxima` (#10).
- [ ] Confirmar com a empresa (Luciene) `tributos_pct` 15% e `margem_minima_pct` 10%.
- [x] Calibrar nas licitações 19478221 e 19482164 (tabela acima).
- [x] Limitar a triagem a 50 com ❌ de caminho pendente: aprovado (decisão #9), depois substituído por #10.
