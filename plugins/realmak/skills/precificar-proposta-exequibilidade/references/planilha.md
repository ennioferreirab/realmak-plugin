# Dados da planilha de manutenção

Grave um JSON UTF-8. Campos desconhecidos são recusados. Use `null` para entrada sem dado e registre a causa em `fontes` ou na síntese. Valores monetários são números em reais. Percentuais são frações, por exemplo `0.15` para 15%.

Exemplo fictício, parcial:

```json
{
  "premissas": {
    "edital": "PE 10/2026",
    "objeto": "Manutenção de equipamentos",
    "vigencia_meses": 12,
    "teto_mensal": 8000,
    "preco_mensal": {"valor": 7200, "fonte": "Cenário-base, pendente de aprovação"},
    "tributos": {"valor": 0.15, "fonte": "Base de custos, competência do exemplo"},
    "dias_uteis": 21,
    "horas_jornada": 8,
    "fator_produtivo": 0.75,
    "data_proposta": "2026-10-15"
  },
  "proposta": {"pecas": "Kit preventivo incluído. Corretivas conforme o TR."},
  "equipamentos": [["Item 1", "Bomba", 10, 90, 45, "Minutos", "Alta"]],
  "mao_de_obra": [["Técnico", 0.5, 4500, 0.65, 650, "Rateado conforme equipe dimensionada"]],
  "operacao": {"deslocamentos": {"mensal": 500, "fonte": "Premissa: 4 visitas"}},
  "pecas": [["Kit preventivo", 4, 120, "Incluído", 1, "7 dias"]],
  "obrigacoes": [["SLA", "Visita programada", "90 dias", "OS", "Mão de obra", "TR 3.2", "Médio"]],
  "fontes": [["TR.pdf", "Inventário", "p. 3", "Equipamentos", null, null]],
  "pendencias": [[1, "Confirmar cotação", "Analista", null, "Preço das peças", null]]
}
```

## Campos permitidos

- `premissas`: `edital`, `contratante`, `objeto`, `uasg_orgao`, `processo`, `local`, `data_proposta` (AAAA-MM-DD), `validade_dias`, `vigencia_meses`, `teto_mensal`, `preco_mensal`, `verba_pecas_sob_demanda`, `tributos`, `administracao`, `contingencia`, `margem_minima`, `dias_uteis`, `horas_jornada`, `fator_produtivo`, `reserva_horas`, `glosa_maxima`, `capital_giro_meses`, `primeiro_ciclo_dias`, `limite_desconto`, `proponente`, `cnpj`, `contato`, `representante_legal`, `responsavel_tecnico`. Um valor pode vir com sua fonte, como no exemplo.
- `proposta`: `preco`, `pecas`, `atendimento`, `mobilizacao`, `reajuste`, `observacoes`.
- `operacao`: cada grupo aceita `mensal` e `fonte`. Grupos: `pecas`, `cmms`, `deslocamentos`, `ferramentas`, `ensaios`, `epis`, `garantias`, `treinamentos`, `residuos`, `subcontratacao`, `comunicacao`, `mobilizacao`, `capital_giro`, `outro`. Quando há peças detalhadas, a planilha calcula a reserva e a inclui uma vez no custo.
- `equipamentos` (até 101): item, família, quantidade, periodicidade em dias, tempo por evento, `Minutos` ou `Horas`, criticidade.
- `mao_de_obra` (até 10): função, FTE, salário ou honorário, fração de encargos, benefícios, observação.
- `pecas` (até 50): descrição, quantidade anual, custo unitário, tratamento, estoque mínimo, prazo de reposição.
- `obrigacoes` (até 30): tema, obrigação, prazo/meta, evidência, custo previsto, referência, risco.
- `fontes` (até 20): arquivo ou URL, conteúdo usado, página/aba/item, aplicação, data-base, observação.
- `pendencias` (até 2): número, ação, responsável, prazo, impacto, evidência. Inclua itens adicionais na síntese.

Os limites vêm das áreas do modelo que alimentam as fórmulas. Se exceder, agrupe linhas só quando a equivalência preservar os totais e mantenha a lista detalhada na memória de cálculo. O script recusa excedentes para evitar corte silencioso. Abra a saída em um aplicativo que recalcule fórmulas para verificar a aba Checks.
