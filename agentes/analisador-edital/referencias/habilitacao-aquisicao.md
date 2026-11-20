# Pesquisa e aquisição da habilitação

O fluxo v5 usa quatro pesquisas T1 e quatro cruzamentos T2, uma cadeia por empresa. As pesquisas aguardam o Cérebro histórico, inclusive se ele falhar, e aproveitam também as pistas disponíveis do G1. Cada pesquisa libera seu item `baixar-habilitacao-<alias>` (T0), que libera o cruzamento após gravar os downloads. Os parciais em `analise/habilitacao/<alias>.json` e o consolidado mantêm o [contrato v1 do card](card/CONTRATO.md).

## Pesquisa T1

`pesquisa-habilitacao-<alias>` grava `fontes/habilitacao/<alias>/candidatos.json` na pasta do agente, com a pauta de `analise/edital.json` (`habilitacao[]`) e as tentativas por documento. Preserve a ordem e a fonte do edital e desdobre linhas agrupadas em uma entrada por documento. A pauta é comum às quatro empresas. Consulte o Cérebro por exigência e a pasta local. Grave o envelope válido com a pauta antes da primeira busca. Após cada busca, acrescente candidatos e tentativas sem perder o que já foi gravado. Todo achado plausível com ref entra em candidatos, inclusive cópias distintas ou com conflito. Registre a dúvida no motivo. O cruzamento abre os originais e decide titularidade, quantitativo e conflitos.

Na raiz, `empresa` contém o alias literal do item, igual ao segmento `<alias>` do caminho de saída (`aforca`, `realmak`, `una` ou `nortfort`). Registre o CNPJ em `cnpj_referencia` como texto, quando conhecido, e preserve seus zeros iniciais.

Exemplo fictício:

```json
{
  "versao": 1,
  "empresa": "realmak",
  "cnpj_referencia": "00123456000100",
  "exigencias": [
    {
      "exigencia": "Atestado de manutenção com quantitativo mínimo",
      "fonte": "TR 8.1",
      "candidatos": [
        {"ref": "d3", "motivo": "Serviço equivalente com quantitativo a conferir."},
        {"sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef", "titulo": "Atestado na pasta da licitação", "motivo": "Cópia autorizada para conferência."}
      ],
      "tentativas": [
        {"via": "cerebro_buscar", "consulta": "00123/2026", "resultado": "Candidato para TR 8.1."}
      ]
    }
  ]
}
```

Para candidato do Cérebro, use só `ref` e `motivo`, seguindo `como_citar`. Cite a ref devolvida na pesquisa da empresa. O daemon registra os documentos em `fontes/habilitacao/<alias>/documentos.json` e valida as referências no fim da pesquisa. Hit sem ref fica como pista nas tentativas para nova busca dirigida. Para cópia autorizada da pasta da licitação sem ref, preencha `sha256` calculado dos bytes, `titulo` e `motivo`.

A união de `pistas[]` e dos números nos achados de `fontes/cerebro_g1.json` e `fontes/cerebro.json` é a pauta de buscas dirigidas do alias. Preserve os números como texto, inclusive os zeros iniciais. Para cada lista vazia, as tentativas distinguem busca sem achados, exclusão fundamentada e pesquisa incompleta (por exemplo, ferramenta ausente). Em pesquisa incompleta, informe a causa e preserve as pistas. O T2 reflete a lacuna na saída do card.


## Aquisição pelo daemon e entrada do cruzamento

O item `baixar` tem `empresa`, `entrada` com a lista, `saida` com os downloads e depende da pesquisa do mesmo alias. O daemon resolve a ref pelo registro da empresa e obtém os identificadores do original antes de tentar a aquisição. Procura a cópia local autorizada. Se a consulta de provas pelo ID não devolver original, tenta resolver pelos demais dados disponíveis: hash, caminho e título. Arquiva a cópia identificada na empresa do item e vincula a exigência. Em falhas passageiras, repete com esperas de 3, 10 e 30 segundos. Uma falha individual recebe causa após as tentativas e o item conclui com os resultados disponíveis. Entrada ausente ou ilegível faz falhar o item.

`fontes/habilitacao/<alias>/downloads.json` contém o mesmo agrupamento. Cada candidato recebe `estado: "baixado"|"falha"`. Para `baixado`, informe `arquivo`, `sha256`, `caminho` absoluto para o leitor e `url` permanente da cópia. Para `falha`, informe `motivo_falha` e o número de `tentativas` de aquisição. Se o ID devolver mais cópias verificadas, o daemon também lista `outras_copias[]`, cada qual com `arquivo`, `sha256`, `caminho` e `url`. Quando a pesquisa indicar o hash, use as cópias desse conteúdo. Caminhos, hashes e endereços de prova vêm do daemon.

`habilitacao-<alias>` (T2) lê o arquivo desta rodada e abre todos os originais baixados. Registra para cada exigência título, localizador, trecho e confronto, inclusive quando o documento não atende. Se houver falha de aquisição, registra `download falhou: <causa>` em `pesquisa_incompleta` e a lacuna documental na linha do card. Quando houver cópia ilegível, registra o impedimento de leitura após tentar vias alternativas. O motivo de uma falha de sessão fica explícito; o cruzamento usa todos os downloads válidos que a rodada produziu.
