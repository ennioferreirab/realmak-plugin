# Decisões — guia-leitura-edital

Registro das regras decididas com o usuário. A mais recente vale; decisões substituídas ficam marcadas, não apagadas.

| # | Data | Decisão | Motivo | Decidido por | Situação |
|---|---|---|---|---|---|
| 1 | 2026-10-15 | Criar o guia de leitura do edital usando a classificação de documentos do CRM, para cada skill ir direto ao documento e à página certos. | Leitura mais assertiva e barata; subagentes leem só o necessário. | Ennio | vigente |
| 2 | 2026-10-15 | `catalogo.json` é a fonte única (informação → ordem de leitura → termos → seções). `ONDE-ESTA.md` é gerado dele. | Evitar duas versões do guia. | Claude | vigente |
| 3 | 2026-10-15 | Ordem inicial baseada na medição em 40 licitações (presença e participação por tipo) e na Lei 14.133. Termos contratuais (multa, reajuste, vigência, garantia contratual) começam pela minuta quando ela existe. | Dados reais do CRM. | Claude (a validar) | a validar |
| 4 | 2026-10-15 | Tipo do documento: manifesto → banco do CRM (transitório) → nome do arquivo. Proposto ao CRM gravar o tipo no manifesto. | Mesmo princípio do resumo IA: o que o CRM já calculou fica na pasta. | Claude (a validar) | a validar |
| 5 | 2026-10-15 | Divergência entre documentos: citar os dois, marcar ⚠️; precedência pelo que o edital disser, senão edital sobre anexos, e a divergência vira ponto de esclarecimento. | Evitar escolher o valor errado em silêncio. | Claude (a validar) | a validar |
| 6 | 2026-10-19 | Na seção 1, aviso de tipo vindo só do nome do arquivo apenas quando a leitura não confirmou o documento; TR embutido continua avisado. | Aviso técnico sem efeito na decisão nos dois casos do piloto. Fonte: plano `docs/superpowers/plans/2026-10-19-aprimorar-skills-precificacao.md` e auditoria R1. | Claude (a confirmar), pelo plano de Ennio | vigente |
| 7 | 2026-10-19 | R3b: skill cortada; números de medição e arquitetura transitória do CRM saem. Regras de leitura, páginas não extraídas e conflito de documentos mantidos. | Revisão adversarial R3b, §2.5. | Main (Contract R3b) | vigente |

## Perguntas em aberto

- [ ] A ordem de leitura do catálogo bate com a experiência da Luciene? Ajustar onde ela sabe que a informação costuma estar.
- [ ] CRM: gravar `tipo_documento` e `tipo_confianca` em `manifesto.anexos[].extraidos[]` (proposta §3.8).
- [ ] Reclassificar PDFs que juntam vários documentos (hoje um tipo só pelo início): o mapa já marca TR embutido no edital; vale classificar por trecho no CRM?
