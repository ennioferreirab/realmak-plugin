# Consulta histórica no fluxo de edital

Use a skill [cerebro](../../../plugins/realmak/skills/cerebro/SKILL.md). Identifique a empresa de origem, cite o documento e preserve a diferença entre prova lida e pista. As saídas servem de subsídio ao gestor e à análise. Cada item de habilitação consulta a sua empresa e investiga as pistas pelo identificador.

## Consulta curta antes do G1

Leia o manifesto, o resumo disponível e o mapa de leitura. Esta etapa é uma **triagem rápida** (meta: **~12 a 15 buscas** focadas apenas nos 3 pontos que podem mudar a decisão do G1; pesquisa documental exaustiva e busca de preços/BDI ficam para o item `cerebro` em E2 e para a habilitação):

1. Histórico no órgão (`orgao`);
2. Objeto semelhante com os quantitativos relevantes (`objeto`);
3. Sanção, penalidade ou impedimento que alcance o certame (`sancoes`).

Grave `fontes/cerebro_g1.json` com o bloco `perguntas` contendo exatamente as três chaves `orgao`, `objeto` e `sancoes`. **Cada valor de `perguntas` deve ser uma única string (texto simples, nunca objeto `{...}` ou lista)** informando o que foi encontrado com a empresa de origem ou onde buscou sem achar. Antes de gravar, revise também as respostas das ferramentas. Registre em `pistas` cada número de CAT, atestado ou contrato encontrado e a empresa titular confirmada, mesmo quando o número não couber no resumo dos achados. Preserve zeros iniciais e a grafia da fonte.

## Consulta histórica depois do G1

Aprofunde preços, compras, BDI, atas e recursos. Diferencie compra efetiva, preço proposto e estimativa. Inclua as pistas do G1 em `fontes/cerebro.json` e acrescente todas as novas pistas numeradas encontradas, com a origem. A pesquisa de cada empresa lê a união das duas saídas e faz uma consulta dirigida por identificador. A pesquisa documental por exigência cabe aos itens de habilitação.

## Saídas

Exemplo de `fontes/cerebro_g1.json` (no `fontes/cerebro.json`, após o G1, o campo `perguntas` é opcional):

```json
{
  "consultado_em": "AAAA-MM-DD",
  "disponivel": true,
  "erro": null,
  "perguntas": {
    "orgao": "Realmak: contrato 10/2024 de manutenção predial no órgão; nenhuma ocorrência em AForça/UNA/Nortfort.",
    "objeto": "AForça: atestado de manutenção de VRF 150 TR (2024); sem cobertura confirmada para chiller.",
    "sancoes": "Nenhuma sanção ou impedimento vigente localizado nas buscas em Realmak, AForça, Nortfort e UNA."
  },
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

Em `perguntas`, preencha `orgao`, `objeto` e `sancoes` sempre como **string única não vazia** (nunca objeto aninhado como `{"alvo": ..., "cobertura": ..., "lacuna": ...}`).

Se nada puder ser consultado após as novas tentativas, grave `disponivel: false`, `erro` com o impedimento e `achados: []`. Resultado parcial conserva os achados e descreve o que ficou sem pesquisa. Nenhum desses estados prova ausência de documento.
