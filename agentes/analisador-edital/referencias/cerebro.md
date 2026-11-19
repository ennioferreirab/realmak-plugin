# Consulta histórica no fluxo de edital

Use a skill [cerebro](../../../plugins/realmak/skills/cerebro/SKILL.md). Identifique a empresa de origem, cite o documento e preserve a diferença entre prova lida e pista. As saídas servem de subsídio ao gestor e à análise. Cada item de habilitação consulta a sua empresa e investiga as pistas pelo identificador.

## Consulta curta antes do G1

Leia o manifesto, o resumo disponível e o mapa de leitura. Busque três pontos que podem mudar a decisão: histórico no órgão, objeto semelhante com os quantitativos exigidos, e sanção ou pendência que alcance o certame. Grave `fontes/cerebro_g1.json` com `perguntas` contendo `orgao`, `objeto` e `sancoes`. Cada resposta indica a empresa ou a cobertura e a lacuna. Conserve no texto dos achados os números de CATs, atestados e contratos, com a empresa e a exigência provável.

## Consulta histórica depois do G1

Aprofunde preços, compras, BDI, atas e recursos. Diferencie compra efetiva, preço proposto e estimativa. Inclua as pistas do G1 em `fontes/cerebro.json` com a origem e o grau de confiança. A pesquisa documental por exigência cabe aos itens de habilitação.

## Saídas

```json
{
  "consultado_em": "AAAA-MM-DD",
  "disponivel": true,
  "erro": null,
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
