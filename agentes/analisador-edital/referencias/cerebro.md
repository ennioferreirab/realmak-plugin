# Triagem estruturada no Cérebro (fluxo de edital v6)

Use a skill [cerebro](../../../plugins/realmak/skills/cerebro/SKILL.md). Identifique a empresa de origem, cite a fonte e preserve sempre a diferença entre **prova própria**, **documento de terceiro** e **pista**. A saída `fontes/triagem_cerebro.json` serve de base ao portão G1 e ao aprofundamento dirigido em E2.

## Escopo de empresas (regra estrita)

Consulte **apenas as 4 empresas ativas**: `realmak`, `nortfort`, `aforca` e `una`. **Nunca consulte `sublime`.** Cruze os resultados com os perfis de `agentes/contexto/empresas.json`.

## Item `triagem-cerebro` (E1, após `edital`)

Leia `analise/edital.json`, o manifesto, o resumo disponível e o mapa de leitura. Execute consultas SQL estruturadas no Cérebro das 4 empresas ativas:

1. **Capacidade econômico-financeira (`reg_balanco`):** verifique CCL, PL e índices aplicáveis comparando com a **base financeira correta do edital** (valor global vs por item/lote).
2. **Qualificação técnica eliminatória (`vw_atestados_quantitativos` e tabelas de CAT/atestados):** para cada exigência eliminatória ou lote, localize a melhor prova e **distinga explicitamente titularidade própria vs documento de terceiro** (por exemplo, um acervo de terceiro como EBLOC 12.159 m² jamais conta como prova própria da empresa).
3. **Certidões e sanções (`reg_certidao`):** em 1 consulta SQL por empresa, verifique certidões recentes e eventual sanção ou impedimento vigente.
4. **Histórico no órgão e objeto semelhante:** registre contratos ou atas anteriores relevantes no mesmo órgão ou objeto.

## Saída (`fontes/triagem_cerebro.json`)

Grave `fontes/triagem_cerebro.json` com:
- `exigencias[]`: para cada exigência eliminatória/lote: `clausula`, `minimo_exigido`, `base_financeira` (`"global"` | `"por_item"` | `null`), `melhor_prova_propria` (`empresa`, `titularidade: "propria"|"terceiro"|"nenhuma"`, `quantidade`, `fonte`), `lacuna`.
- `empresas_alvo`: recomendação para o G1 com 1 empresa principal + no máximo 1 reserva (somente se prova ou custo puder inverter o resultado), com `motivo`.
- `sem_prova_propria`: sinalização booleana clara quando nenhuma das 4 empresas tem prova própria plausível para exigência eliminatória pesada, acompanhada de `pistas_diligencia[]` (melhores pistas concretas para diligência ou abertura dirigida).
- `pistas[]`: números de CAT, atestado ou contrato com `empresa` titular confirmada (preservando zeros iniciais e grafia da fonte) para guiar `pesquisa-habilitacao-<alias>` em E2.
- `perguntas`: objeto com as três chaves `orgao`, `objeto` e `sancoes`, cada valor como **uma única string não vazia** (nunca objeto aninhado `{...}` ou lista).

```json
{
  "consultado_em": "AAAA-MM-DD",
  "disponivel": true,
  "erro": null,
  "empresas_consultadas": ["realmak", "nortfort", "aforca", "una"],
  "perguntas": {
    "orgao": "Realmak: contrato 10/2024 de manutenção predial no órgão; nenhuma ocorrência em AForça/UNA/Nortfort.",
    "objeto": "Realmak: CAT TJMA 1.140 TR (própria); AForça: atestado VRF 150 TR (própria).",
    "sancoes": "Nenhuma sanção ou impedimento vigente localizado nas 4 empresas ativas."
  },
  "exigencias": [
    {
      "clausula": "TR 8.3 (p. 14)",
      "minimo_exigido": "Manutenção VRF >= 120 TR",
      "base_financeira": "global",
      "melhor_prova_propria": {
        "empresa": "realmak",
        "titularidade": "propria",
        "quantidade": "1.140 TR",
        "fonte": "Realmak · CAT TJMA 2024"
      },
      "lacuna": null
    }
  ],
  "empresas_alvo": [
    {"empresa": "realmak", "papel": "principal", "motivo": "Melhor prova própria técnica e PL compatível com base global."}
  ],
  "sem_prova_propria": false,
  "pistas_diligencia": [],
  "pistas": [
    {"empresa": "realmak", "tipo": "cat", "numero": "00123/2024", "referencia": "vw_atestados_quantitativos"}
  ],
  "achados": []
}
```

Se nada puder ser consultado após as tentativas aplicáveis, grave `disponivel: false`, `erro` com o impedimento e `exigencias: []`, `achados: []`. Nenhum desses estados prova ausência de documento.
