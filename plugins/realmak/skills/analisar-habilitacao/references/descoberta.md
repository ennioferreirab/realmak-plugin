# Descoberta de atestados por empresa

1. Leia a cláusula e o TR. Monte um JSON por empresa com `empresa` (alias) e `termos`. Use em `composto` expressões do edital que descrevem o ambiente. Em `amplo`, decomponha essas expressões em núcleos pesquisáveis de atividade, processo, material tratado ou classe de emissor. Inclua sinônimos, siglas e variantes pertinentes com e sem acento quando usadas no acervo. Não repita apenas a expressão composta. Em `equipamento`, liste famílias, sinônimos e modelos. Em `servico`, liste tipos de serviço e variantes independentes. Use termos literais. Exemplo fictício:

   ```json
   {
     "empresa": "empresa-exemplo",
     "termos": {
       "composto": ["central de tratamento de efluentes"],
       "amplo": ["efluente", "águas residuais", "aguas residuais"],
       "equipamento": ["bomba dosadora", "dosador de reagente"],
       "servico": ["calibração", "calibracao", "aferição"]
     }
   }
   ```

2. Confira o esquema e o acesso com a skill `cerebro`. Para cada recorte, gere o SQL com `python scripts/descobrir_atestados.py consulta --recorte <recorte> < plano.json`. Use o SQL em `cerebro_consulta` para a empresa do plano, com `limite=50`. As duas buscas de ambiente varrem objeto, área e dados do emissor, inclusive variantes de nome. Equipamento e serviço buscam no objeto, área e trechos dos serviços, sem filtro por emissor ou ambiente. Se o esquema não oferecer uma coluna ou tabela, adapte a consulta aos campos disponíveis e registre a diferença. Se não houver acesso estruturado, faça passadas textuais separadas e mantenha a cobertura estruturada pendente, com o motivo.
3. Preserve SQL, termos, empresa, limite e respostas em trilha. Acrescente ao plano uma lista `paginas`, com `empresa`, `recorte`, `apos` (nulo na primeira página), `linhas` e `truncado` de cada resposta bem-sucedida. Em página cheia ou truncada, gere a próxima com `--apos <último-atestado_id>`. Mesmo uma página cheia sem marca de truncamento pede continuação. Se faltar cursor utilizável, refaça com página menor ou recorte mais específico. Ao usar outro limite, use o mesmo valor em todas as páginas do plano, no MCP e em `unir`. Registre falhas e retome pelo último cursor confirmado. Uma falha de consulta não equivale a página vazia.
4. Rode `python scripts/descobrir_atestados.py unir < plano.json`. A saída conserva a união por ID e os recortes que encontraram cada candidato. Código 1 indica recortes pendentes, com seus cursores. Código 2 indica entrada inválida. Some à união os IDs das buscas complementares por identidade do emissor, contrato, beneficiária, família do TR e texto, registrando também a origem. Preserve IDs diferentes de minuta e atestado emitido. Continue a busca estruturada por emissor e contrato ao encontrar uma minuta.
5. Para cada ID da união, registre a cláusula, o destino e o fundamento factual. Reduza o ruído por triagem individual de titular, objeto e serviço. Se houver sobreposição potencialmente material, abra o original antes de descartar por equivalência incerta. Encaminhe à fila os candidatos que exigem prova. Informe cobertura pendente quando um recorte ficar incompleto ou uma rota não puder ser executada. Só então aplique a reconciliação por ID da referência do dossiê.
