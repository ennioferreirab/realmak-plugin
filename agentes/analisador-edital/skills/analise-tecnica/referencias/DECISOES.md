# Decisões — analise-tecnica

Registro das regras decididas com o usuário. A mais recente vale; decisões substituídas ficam marcadas, não apagadas. O motivo cita a fonte (plano, mensagem, caso real); sem registro, "Motivo não registrado".

| # | Data | Decisão | Motivo | Decidido por | Situação |
|---|---|---|---|---|---|
| 1 | 2026-11-16 | Um único item `tecnica` com esta skill de roteamento, que lê `tipo_objeto` e segue `analisar-edital-manutencao` ou `analisar-edital-fornecimento`. Substitui a adequação técnica (seção 4). | O `se` do `fluxo.json` só condiciona por decisão de portão (`services/agentes/src/analise/fluxo.ts`), não por campo de arquivo; dois itens condicionais exigiriam mudar o daemon. Pedido de Ennio, skills do realmak-plugin#16. | Desenvolvedor | vigente |
| 2 | 2026-11-28 | A conclusão técnica não cita a rodada, a herança da habilitação nem `empresa_avaliada`; ressalva em uma frase curta do que importa para executar. | A seção Habilitação já mostra quais empresas foram analisadas; bastidor da rodada confunde o analista. |

## Perguntas em aberto

- [ ] Se o daemon ganhar condição por campo de saída, trocar este roteador por dois itens condicionais.
