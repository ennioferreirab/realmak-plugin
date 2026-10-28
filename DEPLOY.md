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

Se o site já tiver outras regras dentro do bloco, mantenha o `handle /mcp*` junto delas.
Não use a mesma rota para outra coisa: o `/healthz` não precisa ser exposto fora do servidor.

### O que colocar em `<destino>`

O Caddy costuma rodar em contêiner. Dentro dele, `127.0.0.1` é o próprio contêiner do Caddy,
não o servidor. O destino precisa ser alcançável de dentro do contêiner do Caddy. Há duas formas.

**Opção A: mesma rede Docker (recomendada).** Ligue o mcp-realmak à rede em que o Caddy está
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
| ConLicitação: "recusou o login" | login ou senha do site mudou; atualize o `.env`, apague o arquivo de sessão e reinicie |
