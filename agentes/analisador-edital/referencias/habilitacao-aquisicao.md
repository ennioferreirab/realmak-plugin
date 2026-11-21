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

O item `baixar` depende da pesquisa do mesmo alias. O daemon resolve a ref pelo registro da empresa, localiza o original na montagem somente leitura do E: e extrai texto sem OCR. Quando a extração produzir texto, grava `leitura.txt` na pasta `documentos_empresa/<empresa>/<sha>/`. O binário fica no acervo. Servidor de arquivos indisponível ou extração travada deixa a leitura pendente.

`fontes/habilitacao/<alias>/downloads.json` mantém o agrupamento e o estado `baixado` para originais localizados. Preserva `arquivo`, `sha256`, `origem_windows` e `url`. `caminho` aponta para o original disponível ao leitor, na montagem para documentos do acervo. `texto` é opcional e aponta para `leitura.txt`. Leia também `outras_copias[]`, quando houver. Saídas anteriores que só têm `caminho` podem ser lidas abrindo o original já indicado.

O T2 lê `texto` primeiro e consulta `caminho` quando faltar texto ou para confirmar trecho decisivo. Para PDF escaneado ou imagem, faça leitura visual das páginas relevantes. Registre localizador, trecho e confronto. Se houver impedimento, registre a causa e mantenha `verificar` sem prova suficiente. O endereço de prova é o `url` fornecido pelo daemon, no formato atual do card.
