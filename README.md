# realmak-plugin

Servidor MCP remoto (Streamable HTTP, caminho `/mcp`) que dá aos analistas de licitação da Realmak, dentro do Claude Desktop, quatro grupos de ferramentas, e um plugin do Claude com as skills que ensinam a usá-las. Só as ferramentas `licitacao_*` escrevem, e só na licitação do Odoo, como a pessoa que entrou.

Esta é uma versão de teste (MVP). Veja os [limites](#limites-do-mvp) no fim.

## Ferramentas

50 ferramentas, em quatro grupos.

| Grupo | Prefixo | Qtd. | Para quê |
| --- | --- | --- | --- |
| Compras públicas | `pncp_*` (19), `dadosabertos_*` (10), `contratosgovbr_*` (7) | 36 | PNCP, Compras.gov.br e Contratos.gov.br: busca por texto no PNCP, licitações, itens, vencedores, documentos e histórico de editais, atas, contratos, fornecedores, CATMAT/CATSER e preços praticados |
| ConLicitação | `conlicitacao_*` | 7 | Achar licitação no site (UASG, edital, processo, órgão, objeto, UF), detalhe com itens e impugnações, filtros, boletins, pregões monitorados e mensagens |
| Cérebro | `cerebro_*` | 5 | `cerebro_buscar`, `cerebro_fatos` e, para chaves com acesso ao dataset de registros, `cerebro_esquema`, `cerebro_consulta`, `cerebro_provas` |
| Licitações da plataforma | `licitacao_*` | 7 | Buscar e abrir a pasta da licitação no Odoo (JSON), ler o texto dos documentos, link de download, registrar nota, anexar arquivo na Saída IA (pasta "Agentes MCP") e deixar o status no card. Só no login de pessoa |

As ferramentas de compras foram extraídas do projeto [mcp-brasil](https://github.com/Mcp-Brasil/mcp-brasil) (MIT). Veja [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

### Ferramentas de licitação (Odoo)

As `licitacao_*` só aparecem para quem entrou pelo login de pessoa e tem as licitações liberadas no Odoo (grupo de vendedor). A chave de bot não carrega e-mail e não as vê.

1. O servidor chama as rotas internas do módulo `realmak_mcp` do realmak-crm (`{ODOO_MCP_URL}/realmak_mcp/v1/...`) com o segredo compartilhado e `X-Realmak-Act-As: <e-mail>`. O Odoo roda a chamada como essa pessoa: valem as regras de acesso dela.
2. O segredo é criado pelo Odoo no volume `mcp-realmak-odoo` e lido a cada chamada (`ODOO_MCP_SECRET_FILE`). Nunca aparece em erro nem em log.
3. Arquivos não passam pela conversa: `licitacao_link_arquivo` e `licitacao_enviar_arquivo` devolvem links `/mcp/arquivos/...` assinados, presos à pessoa e à licitação, válidos por 15 minutos (o de envio, uma vez). O servidor repassa ao Odoo, que confere a permissão de novo. Envio até 50 MB.
4. Toda escrita fica no card: nota interna no histórico, arquivo na Saída IA e a faixa "Claude de <pessoa> · <status>".

Uma pessoa só com o Odoo (sem o cérebro) também entra pelo login; ela vê as `licitacao_*` e não vê as `cerebro_*`.

Resultados grandes são cortados em cerca de 100 mil caracteres, com um aviso para refinar o filtro ou paginar. O `conlicitacao_ler_boletim` já devolve só uma página resumida de cada vez.

### Ferramentas de registros do cérebro

`cerebro_esquema`, `cerebro_consulta` e `cerebro_provas` só aparecem na lista para chaves que o gateway deixa usar: o servidor consulta `GET /consulta/esquema` com a chave de quem listou e mostra as três ferramentas apenas se a resposta for 200 (ou 503, módulo ligado mas dataset ainda indisponível). A resposta definitiva fica em cache por 5 minutos. Se um cliente guardar a lista de ferramentas, pode ser preciso reconectar para vê-las. Quando uma chave sem acesso chama uma delas mesmo assim, o servidor devolve a mensagem do gateway (403) de forma clara.

## Como funciona a autenticação

Há duas portas de entrada:

- **Pessoas (plugin no Claude Desktop, Cowork e Claude Code):** login OAuth na página do próprio servidor, com Google Workspace, conta do Galeed ou código por e-mail. Veja "Login de pessoa" abaixo.
- **Bots e scripts:** a chave de bot do Galeed (`gld_live_...`) vai como token Bearer.

### Chave de bot

1. O cliente envia `Authorization: Bearer <chave>` em cada requisição.
2. Na primeira vez que vê uma chave, o servidor chama `GET {GALEED_API_URL}/facts?limit=1` com ela. `200` vale; `401` e `403` não valem.
3. O resultado, válido ou inválido, fica em cache por 5 minutos, indexado pelo sha256 da chave. A chave nunca é gravada em disco nem em log.
4. Se o Galeed não responder, o servidor recusa o acesso com `503` e uma mensagem clara (falha fechada). Ele nunca libera sem conferir.
5. A mesma chave é repassada às ferramentas `cerebro_*`. Cada chave está presa a um único cérebro, então cada analista vê só o que a própria chave enxerga.

Uma chave válida libera todas as ferramentas (compras, ConLicitação e cérebro). O login do site e o token da API do ConLicitação ficam só no servidor.

**Como pegar a chave.** No painel do Galeed do seu cérebro, em Acesso, crie um bot com acesso a todas as áreas, vá em Conectar, Chaves do cérebro, e clique em Gerar chave. A chave inteira aparece uma única vez; copie na hora. Quem administra o cérebro faz isso. Trate a chave como senha: não vai para chat, print nem Git.

### Login de pessoa (OAuth)

Fica desligado até o `.env` ter `MCP_REALMAK_PUBLIC_URL`, `MCP_REALMAK_OAUTH_SECRET`, `GALEED_SERVICE_KEY` e ao menos uma forma de login. Desligado, o servidor não publica metadados OAuth e o `401` volta sem `resource_metadata`, como antes.

1. O aplicativo descobre o OAuth pelo `401` (`/.well-known/oauth-protected-resource/mcp`), se registra em `/mcp/oauth/register` (só redirects para `claude.ai`, `claude.com` e `localhost`, mais os de `MCP_REALMAK_OAUTH_REDIRECT_HOSTS`) e abre `/mcp/oauth/authorize` com PKCE S256. Todas as rotas do login ficam sob `/mcp/oauth/`; só os metadados `/.well-known/oauth-*` ficam na raiz.
2. A página mostra as formas de login configuradas: Google Workspace (restrito a `GOOGLE_WORKSPACE_DOMAIN`), conta do Galeed (o servidor confere a senha no `/auth/login` do Galeed e encerra a sessão) ou código de 6 dígitos por e-mail (10 minutos, 5 tentativas; a página não revela se o e-mail tem acesso).
3. Com o e-mail provado, o servidor pergunta ao Galeed se ele tem acesso (`GET /v1/facts` com a chave de serviço e `X-Galeed-Act-As: <email>`) e, se não tiver, pergunta ao Odoo se ele tem as licitações liberadas. Sem nenhum dos dois, a página diz isso e não emite nada.
4. O aplicativo recebe um access token `rmk_...` (1 hora) e um refresh token `rmkr_...` (30 dias). O refresh confere o acesso de novo.
5. Cada ferramenta `cerebro_*` chama o Galeed com a chave de serviço e o e-mail da pessoa. Vale o grant dela no Galeed: tirar o acesso no painel corta em até 5 minutos (cache), e o refresh seguinte falha.

Nada fica em banco: códigos, tokens e cadastros de cliente vão cifrados com `MCP_REALMAK_OAUTH_SECRET`. Trocar o segredo desconecta todo mundo. No Claude Code, quando o header `Authorization` está configurado, o cliente não tenta OAuth, então a chave de bot continua valendo como antes.

Uma pessoa com acesso de leitura só a algumas áreas recebe 403 em `cerebro_esquema`, `cerebro_consulta` e `cerebro_provas`: o Galeed exige escopo total no dataset de registros.

## Instalar o plugin

O plugin `realmak` traz as skills (`cerebro`, `licitacao`, `analisar-edital`, `conferir-habilitacao`, `conlicitacao`, `compras-publicas`) e declara o conector do servidor (`https://realmak.duckdns.org/mcp`). O plugin não pede chave: cada pessoa entra pelo login, e precisa ter acesso concedido no Galeed ou no Odoo.

### Claude Code

```bash
claude plugin marketplace add ennioferreirab/realmak-plugin
claude plugin install realmak@realmak
```

Depois, dentro do `claude`, rode `/mcp`, escolha o servidor `realmak` e autentique pelo navegador. Para testar sem instalar, use `claude --plugin-dir ./plugins/realmak`.

### Claude Desktop (chat)

1. Abra Customize, Plugins, Add, Add marketplace, e informe a URL do repositório no GitHub (`https://github.com/ennioferreirab/realmak-plugin`). Instale o plugin `realmak`. Isso traz as skills.
2. Na página do plugin, clique em Vincular (Connect) e entre com Google, conta do Galeed ou código por e-mail. Se preferir, o conector também pode ser adicionado à mão: Customize, Connectors, `+`, Add custom connector, com a URL `https://realmak.duckdns.org/mcp`.

   Não coloque `headers` com `${user_config...}` no `.mcp.json` do plugin: o Desktop não resolve esse valor e o botão Vincular fica travado.

   Para usar uma chave de bot num cliente, o conector manual leva Authentication: No sign-in e o header `Authorization: Bearer <chave gld_live_...>`.

   Fonte: [Getting started with custom connectors using remote MCP](https://support.claude.com/en/articles/11175166-getting-started-with-custom-connectors-using-remote-mcp).

As skills chamam as ferramentas pelo nome (`cerebro_buscar`, `conlicitacao_buscar_licitacao`...). O nome completo pode ter prefixo conforme o aplicativo.

## Configuração do servidor

Só variáveis de ambiente. Veja [.env.example](.env.example). Nada de segredo vai para o repositório.

| Variável | Para quê |
| --- | --- |
| `GALEED_API_URL` | Obrigatória. Raiz do gateway, terminando em `/v1`. Sem valor padrão |
| `GALEED_TIMEOUT_MS` | Tempo máximo por chamada ao Galeed (padrão 30000) |
| `CONLICITACAO_URL` | Padrão `https://consultaonline.conlicitacao.com.br` |
| `CONLICITACAO_TOKEN` | Token da API (cabeçalho `x-auth-token`) |
| `CONLICITACAO_LOGIN`, `CONLICITACAO_SITE_PASSWORD` | Login do site do ConLicitação |
| `CONLICITACAO_SESSION_FILE` | Onde guardar o cookie de sessão (num volume, modo 0600) |
| `MCP_REALMAK_TOKEN_CACHE_SECONDS` | Cache da validação de chave (padrão 300) |
| `MCP_REALMAK_MAX_RESULT_CHARS` | Teto por resultado (padrão 100000) |
| `MCP_REALMAK_HOST`, `MCP_REALMAK_PORT` | Endereço de escuta (padrão `127.0.0.1:8095`) |
| `ODOO_MCP_URL` | Endereço interno do Odoo (na VPS, `http://web:8069`). Sem ele, as `licitacao_*` ficam escondidas |
| `ODOO_MCP_SECRET_FILE` | Arquivo do segredo criado pelo Odoo (na VPS, `/run/realmak-mcp/secret`). `ODOO_MCP_SECRET` aceita o valor direto, para teste |
| `ODOO_MCP_TIMEOUT_MS` | Tempo máximo por chamada ao Odoo (padrão 60000) |
| `MCP_REALMAK_ARQUIVO_MAX_MB` | Teto do envio por link (padrão 50) |

Publicação no servidor, com Docker e Caddy: [DEPLOY.md](DEPLOY.md).

## Desenvolvimento

```bash
uv sync
uv run pytest                      # testes, com HTTP simulado
uv run python scripts/check_local.py   # sobe tudo em 127.0.0.1 com um Galeed falso
```

O `check_local.py` confere `/healthz`, o `401` sem chave, o `tools/list` pelo cliente MCP e o repasse da chave ao Galeed.

## Limites do MVP

- Fora das `licitacao_*`, só leitura. Não há ferramentas para monitorar ou desmonitorar pregões, nem para gravar no cérebro.
- As `licitacao_*` exigem o login de pessoa. No Claude Code com a chave de bot no header, elas não aparecem.
- Não lê pastas do servidor de arquivos. Sem as `licitacao_*`, nas skills `analisar-edital` e `conferir-habilitacao` o analista anexa os arquivos à conversa.
- A busca do ConLicitação no site só alcança licitações classificadas nas atividades contratadas pela Realmak.
- Uma única conta do ConLicitação (login e token) para todos os analistas. A chave do Galeed controla quem entra, não quem vê o quê no ConLicitação.
- O formato exato de alguns campos do site do ConLicitação (por exemplo `bidding_info`) não é documentado; o servidor repassa o que vem, sem links assinados, e ordena os avisos por data quando consegue.
- Estado em memória: o cache de chaves se perde ao reiniciar. O cookie de sessão do ConLicitação sobrevive no volume.
- Os dados de compras públicas vêm de APIs de terceiros. Confira na fonte oficial antes de usar em proposta ou recurso.

## Licença

MIT. As ferramentas de compras incorporam código do mcp-brasil, também MIT, com os avisos em [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
