# Consulta histórica no fluxo de edital

Use a skill [cerebro](../../../plugins/realmak/skills/cerebro/SKILL.md). Identifique a empresa de origem, cite o documento e preserve a diferença entre prova lida e pista. As saídas servem de subsídio ao gestor e à análise. Cada item de habilitação consulta a sua empresa e investiga as pistas pelo identificador.

## Consulta curta antes do G1

Leia o manifesto, o resumo disponível e o mapa de leitura. Busque três pontos que podem mudar a decisão: histórico no órgão, objeto semelhante com os quantitativos exigidos, e sanção ou pendência que alcance o certame. Grave `fontes/cerebro_g1.json` com `perguntas` contendo `orgao`, `objeto` e `sancoes`. Cada resposta indica a empresa ou a cobertura e a lacuna. Antes de gravar, revise também as respostas das ferramentas. Registre em `pistas` cada número de CAT, atestado ou contrato encontrado e a empresa titular confirmada, mesmo quando o número não couber no resumo dos achados. Preserve zeros iniciais e a grafia da fonte.

## Consulta histórica depois do G1

Aprofunde preços, compras, BDI, atas e recursos. Diferencie compra efetiva, preço proposto e estimativa. Inclua as pistas do G1 em `fontes/cerebro.json` e acrescente todas as novas pistas numeradas encontradas, com a origem. A pesquisa de cada empresa lê a união das duas saídas e faz uma consulta dirigida por identificador. A pesquisa documental por exigência cabe aos itens de habilitação.

## Saídas

```json
{
  "consultado_em": "AAAA-MM-DD",
  "disponivel": true,
  "erro": null,
  "pistas": [{"empresa": "realmak", "tipo": "cat|atestado|contrato", "numero": "00123/2026", "referencia": "<fonte da pista>"}],
  "achados": [{
    "tema": "orgao|habilitacao|preco|concorrencia|bdi",
    "achado": "[Empresa] …",
    "data_documento": "AAAA-MM-DD",
    "file_path": null,
    "confianca": "alta|media|pista",
    "escopo": "item-21|lote-2|global",
    "valor_unit": null,
    "origem": "compra_interna|proposta|null"
  }]
}
```

Se nada puder ser consultado após as novas tentativas, grave `disponivel: false`, `erro` com o impedimento e `achados: []`. Resultado parcial conserva os achados e descreve o que ficou sem pesquisa. Nenhum desses estados prova ausência de documento.
