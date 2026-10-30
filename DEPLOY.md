# Como publicar no servidor

Este guia põe o mcp-realmak para rodar num servidor com Docker e Caddy. Nenhum nome de
servidor, domínio ou IP está neste repositório: use os seus onde aparecer `<...>`.

O serviço escuta só em `127.0.0.1:8095` do servidor. Quem recebe o tráfego da internet,
com HTTPS, é o Caddy, que repassa `/mcp` para o serviço.

## 1. Pré-requisitos

- Docker com o plugin `compose`.
- Um domínio apontando para o servidor, atendido pelo Caddy que já existe lá.
- A URL do gateway do Galeed (termina em `/v1`).
- Credenciais do ConLicitação: token da API, login e senha do site.
- O IP de saída do servidor cadastrado no ConLicitação para a API (a API só aceita IP cadastrado).

## 2. Subir o serviço

```bash
git clone <url-deste-repositorio> mcp-realmak
cd mcp-realmak
cp .env.example .env
chmod 600 .env
# edite o .env e preencha os valores (GALEED_API_URL, CONLICITACAO_*)
docker compose up -d --build
docker compose ps          # o serviço deve ficar "healthy"
curl -s http://127.0.0.1:8095/healthz
```

O `curl` deve responder `{"status":"ok"}`. Um `POST` em `/mcp` sem chave responde 401.

O cookie de sessão do ConLicitação fica no volume `conlicitacao-sessao`, no arquivo
`/data/conlicitacao-sessao.json` (modo 0600). Se trocar a senha do site, apague o arquivo:

```bash
docker compose exec mcp-realmak rm -f /data/conlicitacao-sessao.json
```

Ver logs (nunca trazem chave, cookie nem link assinado):

```bash
docker compose logs -f mcp-realmak
```

Atualizar: `git pull && docker compose up -d --build`.

## 3. Caddy

Dentro do bloco do site que já existe no Caddyfile, acrescente:

```caddy
handle /mcp* {
    reverse_proxy <destino>:8095 {
        flush_interval -1
    }
}
```

`flush_interval -1` desliga o buffer: o MCP por HTTP responde em fluxo (SSE) e o buffer
travaria as respostas. Depois recarregue: `caddy reload` (ou reinicie o contêiner do Caddy).

Com o login de pessoa ligado (seção 6), repasse também os metadados do OAuth, que ficam na raiz
do domínio. As outras rotas do login (`/mcp/oauth/...`) já passam pelo `handle /mcp*`:

```caddy
handle /.well-known/oauth-* {
    reverse_proxy <destino>:8095
}
```

Se o site já tiver outras regras dentro do bloco, mantenha o `handle /mcp*` junto delas.
Não use a mesma rota para outra coisa: o `/healthz` não precisa ser exposto fora do servidor.

### O que colocar em `<destino>`

O Caddy costuma rodar em contêiner. Dentro dele, `127.0.0.1` é o próprio contêiner do Caddy,
não o servidor. O destino precisa ser alcançável de dentro do contêiner do Caddy. Há duas formas.

**Opção A: mesma rede Docker (recomendada).** Se a borda for a do realmak-crm, ela já cria a rede `mcp-realmak` e o override `compose.vps.yaml` deste repositório entra nela: `docker compose -f compose.yaml -f compose.vps.yaml up -d --build --wait`. Para outro Caddy: Ligue o mcp-realmak à rede em que o Caddy está
e use o nome do serviço como destino.

1. Descubra a rede do Caddy: `docker inspect <contêiner-do-caddy> --format '{{json .NetworkSettings.Networks}}'`.
2. Crie um arquivo `compose.override.yaml` ao lado do `compose.yaml`:

   ```yaml
   services:
     mcp-realmak:
       networks:
         - default
         - caddy
   networks:
     caddy:
       external: true
       name: <nome-da-rede-do-caddy>
   ```

3. `docker compose up -d` e, no Caddyfile, `reverse_proxy mcp-realmak:8095`.

Com essa opção a porta publicada em `127.0.0.1:8095` continua útil só para o `curl` de teste.

**Opção B: pelo host.** Faça o contêiner do Caddy enxergar o host e use o endereço dele como
destino.

- No `compose` do Caddy, acrescente ao serviço do Caddy:
  `extra_hosts: ["host.docker.internal:host-gateway"]`, e use `reverse_proxy host.docker.internal:8095`.
- Nesse caso o serviço precisa estar publicado em uma interface que o contêiner alcance. A
  publicação padrão `127.0.0.1:8095` não é alcançável de dentro de outro contêiner; troque no
  `compose.override.yaml` por `ports: !override ["<ip-da-ponte-docker>:8095:8095"]` (o IP da
  ponte `docker0`, não o IP público) e confira que o firewall não expõe a porta para fora.

Prefira a opção A: não abre porta além do loopback.

## 4. Conferir de fora

```bash
curl -s https://<dominio>/mcp -X POST -o /dev/null -w '%{http_code}\n'      # 401 sem chave
curl -s https://<dominio>/mcp -X POST \
  -H 'Authorization: Bearer <chave gld_live_...>' \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | head -c 400
```

Sem chave a resposta é 401. Com chave válida vem a lista de ferramentas. Se o Galeed estiver
fora do ar, o servidor responde 503 (ele nunca libera sem conferir a chave).

## 5. Problemas comuns

| Sintoma | Causa provável |
| --- | --- |
| 502 no Caddy | destino não alcançável de dentro do contêiner do Caddy (veja a seção 3) |
| Respostas travadas ou cortadas | falta `flush_interval -1` |
| 401 com chave certa | chave de outro cérebro, revogada, ou `GALEED_API_URL` sem `/v1` |
| 503 ao conectar | o servidor não alcançou o Galeed (rede, URL, gateway fora do ar) |
| ConLicitação: "recusou o token (401)" | IP de saída do servidor não cadastrado, ou token trocado |
| Connect: "Sem acesso ao cérebro" | o e-mail não é um principal humano ativo com grant no Galeed, ou há dois com o mesmo e-mail |
| Connect: "chave de serviço recusada" | `GALEED_SERVICE_KEY` revogada, ou o agente fora de `GALEED_ACT_AS_PRINCIPALS` no Galeed |
| Connect abre e volta com erro de redirect | o aplicativo usa um redirect fora da lista; acrescente o host em `MCP_REALMAK_OAUTH_REDIRECT_HOSTS` |
| Connect: "não tem acesso ao cérebro nem às licitações" | o e-mail não tem grant no Galeed nem usuário interno no Odoo com as licitações liberadas |
| `licitacao_*` dizem "o Odoo recusou o servidor MCP (401)" | segredo diferente: o volume `mcp-realmak-odoo` não está montado aqui, ou o `ODOO_MCP_SECRET` sobrou no `.env` |
| ConLicitação: "recusou o login" | login ou senha do site mudou; atualize o `.env`, apague o arquivo de sessão e reinicie |

## 6. Login de pessoa (botão Connect)

Opcional. Sem isto, só a chave de bot funciona (Claude Code, pi agent, scripts).

1. **No Galeed**, crie um agente para o servidor (painel, Acesso), gere uma chave `gld_live_` para ele e
   acrescente `<brain>:<id do agente>` a `GALEED_ACT_AS_PRINCIPALS` no `.env` do Galeed. Reinicie o
   gateway. Essa chave só age em nome de pessoas que tenham acesso concedido no mesmo cérebro, e só leitura.
2. **No `.env` daqui:** `MCP_REALMAK_PUBLIC_URL=https://<dominio>`, `MCP_REALMAK_OAUTH_SECRET` (gere com
   `openssl rand -hex 32`) e `GALEED_SERVICE_KEY` com a chave do passo 1.
3. **Formas de login.** Configure as que quiser; a página mostra só as configuradas.
   - **Google Workspace:** no Google Cloud Console, crie um cliente OAuth do tipo "Aplicativo da Web",
     tela de consentimento interna, com o URI de redirecionamento `https://<dominio>/mcp/oauth/login/google/callback`.
     Preencha `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` e `GOOGLE_WORKSPACE_DOMAIN`.
   - **Conta do Galeed:** `GALEED_LOGIN_URL` com a raiz do painel do Galeed (onde responde `/auth/login`),
     alcançável a partir deste servidor. O Galeed limita 10 tentativas por minuto por IP, e aqui todas
     saem do mesmo IP.
   - **Código por e-mail:** `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` e `SMTP_FROM`. No
     Workspace, `smtp.gmail.com` com uma senha de app, ou o relay SMTP do Workspace.
4. Acrescente os metadados do OAuth no Caddy (seção 3) e reinicie o serviço.
5. Confira: `curl -s https://<dominio>/.well-known/oauth-authorization-server` devolve o JSON com
   `authorization_endpoint`. No Claude Desktop, Customize, Connectors, clique em Connect no conector da
   Realmak e faça o login.

## 7. Licitações do Odoo (`licitacao_*`)

Opcional. Exige o login de pessoa (seção 6) e o realmak-crm com o módulo `realmak_mcp` no mesmo servidor.

1. **No realmak-crm**, o deploy instala o `realmak_mcp`. Na primeira chamada, o Odoo cria o segredo em
   `/run/realmak-mcp/secret`, no volume Docker `mcp-realmak-odoo`, e entra na rede `mcp-realmak`.
2. **Aqui**, o `compose.vps.yaml` monta esse volume só para leitura e define `ODOO_MCP_URL=http://web:8069`
   e `ODOO_MCP_SECRET_FILE=/run/realmak-mcp/secret`. Atualize com:

   ```bash
   git pull && docker compose -f compose.yaml -f compose.vps.yaml up -d --build --wait
   ```

   Suba o realmak-crm antes: o volume externo precisa existir.
3. As rotas `/realmak_mcp/` do Odoo não saem para a internet: o nginx do CRM responde 404 para elas. Só
   este serviço as alcança, pela rede interna.
4. Confira: depois do Connect, uma pessoa com as licitações liberadas no Odoo vê as `licitacao_*`. Se não
   vir, `docker compose logs mcp-realmak` mostra "Odoo indisponível" (rede ou volume) ou nada (a pessoa
   não tem o grupo de vendedor no Odoo).
