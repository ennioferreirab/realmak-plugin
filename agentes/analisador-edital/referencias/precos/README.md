# Base de preços

Fonte: `realmak-brain/docs/sintese-temporaria/EMPRESAS_PRECOS_FILTRADA.xlsx` (disputas anteriores da Realmak e concorrentes).

No `agente-precificacao` isto era um link para essa planilha. Dentro do container do daemon o link não resolve, então a
planilha **não** foi copiada para o CRM. Pendente: montar o arquivo só leitura no serviço `agentes` (`compose.yaml`) em
`referencias/precos/EMPRESAS_PRECOS_FILTRADA.xlsx`. Até lá, a precificação e a análise de fornecimento usam compras públicas, online e o cérebro.
