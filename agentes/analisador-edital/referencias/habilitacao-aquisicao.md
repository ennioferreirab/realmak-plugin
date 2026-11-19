# Pesquisa e aquisição da habilitação

O fluxo v5 usa quatro pesquisas T1 e quatro cruzamentos T2, uma cadeia por empresa. As pesquisas aguardam o Cérebro histórico, inclusive se ele falhar, e aproveitam também as pistas disponíveis do G1. A aquisição de uma empresa ocorre no fechamento da sua pesquisa, antes de liberar o cruzamento. Os parciais em `analise/habilitacao/<alias>.json` e o consolidado mantêm o [contrato v1 do card](card/CONTRATO.md).

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

Cada candidato tem `id` de registro ou `sha256` do original, além de `titulo` e `motivo`. Informe ambos quando disponíveis. Preserve números de CATs, atestados e contratos como texto, com zeros à esquerda. A união de `pistas[]` e dos números nos achados de `fontes/cerebro_g1.json` e `fontes/cerebro.json` é a pauta de buscas dirigidas do alias. Uma mesma pista pode servir a várias cláusulas. Registre o resultado ou o motivo documentado de descarte. Sem pista fechada ou prova, preserve a lacuna.

## Aquisição pelo daemon e entrada do cruzamento

O daemon usa a empresa da etapa e a exigência para arquivar cada candidato, em área privada. Repete falhas transitórias e permite reaproveitar cópias verificadas da mesma empresa e licitação. Uma falha individual recebe causa após as tentativas, sem descartar os downloads bem-sucedidos.

`fontes/habilitacao/<alias>/downloads.json` contém o mesmo agrupamento. Cada candidato recebe `estado: "baixado"|"falha"`. Para `baixado`, informe `arquivo`, `sha256` e `url` permanente quando disponível. Para `falha`, informe `motivo_falha` e o número de `tentativas` de aquisição. Caminhos, hashes e endereços de prova vêm do daemon.

`habilitacao-<alias>` (T2) lê o arquivo desta rodada e abre todos os originais baixados. Registra para cada exigência título, localizador, trecho e confronto, inclusive quando o documento não atende. Se houver falha de aquisição, registra `download falhou: <causa>` em `pesquisa_incompleta` e a lacuna documental na linha do card. Quando houver cópia ilegível, registra o impedimento de leitura após tentar vias alternativas. O motivo de uma falha de sessão fica explícito; o cruzamento usa todos os downloads válidos que a rodada produziu.
