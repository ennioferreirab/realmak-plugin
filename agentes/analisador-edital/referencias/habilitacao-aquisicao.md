# Pesquisa e aquisição da habilitação

O fluxo v5 usa quatro pesquisas T1 e quatro cruzamentos T2, uma cadeia por empresa. As pesquisas aguardam o Cérebro histórico, inclusive se ele falhar, e aproveitam também as pistas disponíveis do G1. Cada pesquisa libera seu item `baixar-habilitacao-<alias>` (T0), que libera o cruzamento após gravar os downloads. Os parciais em `analise/habilitacao/<alias>.json` e o consolidado mantêm o [contrato v1 do card](card/CONTRATO.md).

## Pesquisa T1

`pesquisa-habilitacao-<alias>` grava `fontes/habilitacao/<alias>/candidatos.json` na pasta do agente, com as exigências da análise do edital e as tentativas por cláusula. Use somente identificadores retornados pelo Cérebro da empresa indicada. Envie todos os candidatos materiais, inclusive quando a pertinência depender de abrir a cópia. Uma pista sem identificador recuperável permanece nas tentativas.

Exemplo fictício:

```json
{
  "versao": 1,
  "empresa": "realmak",
  "exigencias": [
    {
      "exigencia": "Atestado de manutenção com quantitativo mínimo",
      "fonte": "TR 8.1",
      "candidatos": [
        {"id": "at_exemplo", "titulo": "CAT 00123/2026", "motivo": "Serviço equivalente com quantitativo a conferir."}
      ],
      "tentativas": [
        {"via": "cerebro_buscar", "consulta": "00123/2026", "resultado": "Candidato para TR 8.1."}
      ]
    }
  ]
}
```

Cada candidato tem `id` aceito por `cerebro_provas` na empresa do item, além de `titulo` e `motivo`. Inclua `sha256` quando disponível, para conferência do download. Candidato recebido sem ID falha com motivo “candidato sem id do cérebro”. Preserve números de CATs, atestados e contratos como texto, com zeros à esquerda. A união de `pistas[]` e dos números nos achados de `fontes/cerebro_g1.json` e `fontes/cerebro.json` é a pauta de buscas dirigidas do alias. Uma mesma pista pode servir a várias cláusulas. Registre o resultado ou o motivo documentado de descarte. Sem pista fechada ou prova, preserve a lacuna.

## Aquisição pelo daemon e entrada do cruzamento

O item `baixar` tem `empresa`, `entrada` com a lista, `saida` com os downloads e depende da pesquisa do mesmo alias. O daemon chama `cerebro_provas` por ID e arquiva em área privada, vinculando a exigência. Em falhas passageiras, repete com esperas de 3, 10 e 30 segundos. Uma falha individual recebe causa após as tentativas e o item conclui com os resultados disponíveis. Entrada ausente ou ilegível faz falhar o item.

`fontes/habilitacao/<alias>/downloads.json` contém o mesmo agrupamento. Cada candidato recebe `estado: "baixado"|"falha"`. Para `baixado`, informe `arquivo`, `sha256`, `caminho` absoluto para o leitor e `url` permanente da cópia. Para `falha`, informe `motivo_falha` e o número de `tentativas` de aquisição. Caminhos, hashes e endereços de prova vêm do daemon.

`habilitacao-<alias>` (T2) lê o arquivo desta rodada e abre todos os originais baixados. Registra para cada exigência título, localizador, trecho e confronto, inclusive quando o documento não atende. Se houver falha de aquisição, registra `download falhou: <causa>` em `pesquisa_incompleta` e a lacuna documental na linha do card. Quando houver cópia ilegível, registra o impedimento de leitura após tentar vias alternativas. O motivo de uma falha de sessão fica explícito; o cruzamento usa todos os downloads válidos que a rodada produziu.
