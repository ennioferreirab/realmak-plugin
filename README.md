# realmak-plugin

Servidor MCP remoto (Streamable HTTP, caminho `/mcp`) que dá aos analistas de licitação da Realmak, dentro do Claude Desktop, três grupos de ferramentas, e um plugin do Claude com as skills que ensinam a usá-las. Todas as ferramentas são somente leitura.

Esta é uma versão de teste (MVP). Veja os [limites](#limites-do-mvp) no fim.

## Ferramentas

43 ferramentas, em três grupos.

| Grupo | Prefixo | Qtd. | Para quê |
| --- | --- | --- | --- |
| Compras públicas | `pncp_*` (14), `dadosabertos_*` (10), `contratosgovbr_*` (7) | 31 | PNCP, Compras.gov.br e Contratos.gov.br: licitações, atas, contratos, fornecedores, CATMAT/CATSER e preços praticados |
| ConLicitação | `conlicitacao_*` | 7 | Achar licitação no site (UASG, edital, processo, órgão, objeto, UF), detalhe com itens e impugnações, filtros, boletins, pregões monitorados e mensagens |
| Cérebro (Galeed) | `galeed_*` | 5 | `galeed_retrieve`, `galeed_facts` e, para chaves com acesso ao dataset de registros, `galeed_esquema`, `galeed_consulta`, `galeed_provas` |

As ferramentas de compras foram extraídas do projeto [mcp-brasil](https://github.com/Mcp-Brasil/mcp-brasil) (MIT). Veja [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

Resultados grandes são cortados em cerca de 100 mil caracteres, com um aviso para refinar o filtro ou paginar. O `conlicitacao_ler_boletim` já devolve só uma página resumida de cada vez.

### Ferramentas de registros do cérebro

`galeed_esquema`, `galeed_consulta` e `galeed_provas` só aparecem na lista para chaves que o gateway deixa usar: o servidor consulta `GET /consulta/esquema` com a chave de quem listou e mostra as três ferramentas apenas se a resposta for 200 (ou 503, módulo ligado mas dataset ainda indisponível). A resposta definitiva fica em cache por 5 minutos. Se um cliente guardar a lista de ferramentas, pode ser preciso reconectar para vê-las. Quando uma chave sem acesso chama uma delas mesmo assim, o servidor devolve a mensagem do gateway (403) de forma clara.

## Como funciona a autenticação

A chave de bot do Galeed (`gld_live_...`) é o token Bearer. Não existe outra senha.

1. O cliente envia `Authorization: Bearer <chave>` em cada requisição.
2. Na primeira vez que vê uma chave, o servidor chama `GET {GALEED_API_URL}/facts?limit=1` com ela. `200` vale; `401` e `403` não valem.
3. O resultado, válido ou inválido, fica em cache por 5 minutos, indexado pelo sha256 da chave. A chave nunca é gravada em disco nem em log.
4. Se o Galeed não responder, o servidor recusa o acesso com `503` e uma mensagem clara (falha fechada). Ele nunca libera sem conferir.
5. A mesma chave é repassada às ferramentas `galeed_*`. Cada chave está presa a um único cérebro, então cada analista vê só o que a própria chave enxerga.

Uma chave válida libera todas as ferramentas (compras, ConLicitação e cérebro). O login do site e o token da API do ConLicitação ficam só no servidor.

**Como pegar a chave.** No painel do Galeed do seu cérebro, em Acesso, crie um bot com acesso a todas as áreas, vá em Conectar, Chaves do cérebro, e clique em Gerar chave. A chave inteira aparece uma única vez; copie na hora. Quem administra o cérebro faz isso. Trate a chave como senha: não vai para chat, print nem Git.

**Sobre OAuth.** O servidor usa um verificador de token simples, sem configurar `base_url` nem provedor OAuth. Por isso o FastMCP não publica metadados OAuth (`/.well-known/oauth-protected-resource`), e o `401` volta com `WWW-Authenticate: Bearer`, sem `resource_metadata`. Os testes conferem isso. O cliente não tenta abrir fluxo OAuth e usa o cabeçalho estático. Se um dia o servidor passar a usar `RemoteAuthProvider` ou um provedor OAuth, o Claude pode tentar descobrir OAuth e ignorar o cabeçalho fixo: não faça isso sem rever a instalação.

## Instalar o plugin

O plugin `realmak` traz as skills (`cerebro`, `analisar-edital`, `conferir-habilitacao`, `conlicitacao`, `compras-publicas`) e declara o conector do servidor. Você precisa da sua chave do Galeed. O endereço do servidor já vem preenchido (`https://realmak.duckdns.org/mcp`).

### Claude Code

```bash
claude plugin marketplace add ennioferreirab/realmak-plugin
claude plugin install realmak@realmak
```

Na instalação o Claude Code pergunta a chave (e o endereço, já preenchido). A chave é guardada no cofre de credenciais do sistema, não em arquivo de configuração. Para testar sem instalar, use `claude --plugin-dir ./plugins/realmak`.

### Claude Desktop (chat)

1. Abra Customize, Plugins, Add, Add marketplace, e informe a URL do repositório no GitHub (`https://github.com/ennioferreirab/realmak-plugin`). Instale o plugin `realmak`. Isso traz as skills.
2. Adicione o conector à mão, porque o chat e o Cowork ignoram servidores de plugin que dependem de `user_config` (a URL e a chave vêm da configuração do plugin, que esses aplicativos não pedem): Customize, Connectors, `+`, Add custom connector. Preencha:
   - URL: `https://realmak.duckdns.org/mcp`;
   - Authentication: No sign-in;
   - Request headers: `Authorization: Bearer <sua chave gld_live_...>`.

   Fonte: [Getting started with custom connectors using remote MCP](https://support.claude.com/en/articles/11175166-getting-started-with-custom-connectors-using-remote-mcp).

As skills chamam as ferramentas pelo nome (`galeed_retrieve`, `conlicitacao_buscar_licitacao`...). O nome completo pode ter prefixo conforme o aplicativo.

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

Publicação no servidor, com Docker e Caddy: [DEPLOY.md](DEPLOY.md).

## Desenvolvimento

```bash
uv sync
uv run pytest                      # testes, com HTTP simulado
uv run python scripts/check_local.py   # sobe tudo em 127.0.0.1 com um Galeed falso
```

O `check_local.py` confere `/healthz`, o `401` sem chave, o `tools/list` pelo cliente MCP e o repasse da chave ao Galeed.

## Limites do MVP

- Só leitura. Não há ferramentas para monitorar ou desmonitorar pregões, nem para gravar no cérebro.
- Não baixa edital nem lê pastas do servidor de arquivos. Nas skills `analisar-edital` e `conferir-habilitacao`, o analista anexa os arquivos à conversa.
- A busca do ConLicitação no site só alcança licitações classificadas nas atividades contratadas pela Realmak.
- Uma única conta do ConLicitação (login e token) para todos os analistas. A chave do Galeed controla quem entra, não quem vê o quê no ConLicitação.
- O formato exato de alguns campos do site do ConLicitação (por exemplo `bidding_info`) não é documentado; o servidor repassa o que vem, sem links assinados, e ordena os avisos por data quando consegue.
- Estado em memória: o cache de chaves se perde ao reiniciar. O cookie de sessão do ConLicitação sobrevive no volume.
- Os dados de compras públicas vêm de APIs de terceiros. Confira na fonte oficial antes de usar em proposta ou recurso.

## Licença

MIT. As ferramentas de compras incorporam código do mcp-brasil, também MIT, com os avisos em [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
