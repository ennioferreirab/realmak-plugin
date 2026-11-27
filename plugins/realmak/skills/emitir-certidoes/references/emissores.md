# Emissores de certidões — tabela testada e receitas

Resultados verificados diretamente a partir do contêiner `realmak-crm-agentes-1` (sem navegador, via Python `urllib`, sem contornar captcha ou login).

## Tabela de emissores testados

| Emissor | Certidão | Status sem navegador | Link oficial direto | Motivo / observação técnica |
|---|---|---|---|---|
| **TJDFT** | Falência / Concordata / Recuperação Judicial (`FALENCIA_CONCORDATA`, `CRIMINAL`, `CIVEL`, `ESPECIAL`) | **Funciona** | https://cnc.tjdft.jus.br/ | API REST pública (`cnc-api.tjdft.jus.br`), sem captcha. Reaproveita certidão vigente automaticamente. Atenção: usa o nome cadastrado na Receita (ex.: EIRELI mesmo quando contrato social já é LTDA); registrar em `observacao` sem bloquear. |
| **SEFAZ-GO** | Certidão de Débito Inscrito em Dívida Ativa (Fazenda Estadual GO) | **Funciona** | https://www.sefaz.go.gov.br/Certidao/Emissao/ | Formulário HTML `POST` em 2 passos (`certidao.asp`) sem captcha. Devolve `%PDF` direto com `Certidao.Render=pdf` e `Certidao.ConfirmaNomeContribuinte=Sim` (e também aceita `Render=xml` para leitura estruturada). |
| **RFB / PGFN** | CND Federal (Tributos Federais e Dívida Ativa da União) | **Exige captcha** | https://servicos.receitafederal.gov.br/servico/certidoes | Portal exige `hCaptcha` (`js.hcaptcha.com`). Abrir "a fazer" para pessoa emitir no link oficial. |
| **Caixa (FGTS)** | CRF — Certificado de Regularidade do FGTS | **Exige captcha / bloqueio WAF** | https://consulta-crf.caixa.gov.br/consultacrf/pages/consultaEmpregador.jsf | WAF Azion retorna `HTTP 403` para requisições automatizadas e o portal exige captcha. Abrir "a fazer" para pessoa. |
| **TST** | CNDT — Certidão Negativa de Débitos Trabalhistas | **Exige captcha / bloqueio anti-bot** | https://cndt-certidao.tst.jus.br/inicio.faces | `cndt-certidao.tst.jus.br` dá timeout do contêiner; `tst.jus.br/certidao1` retorna `HTTP 202` (desafio anti-bot) e a emissão exige captcha. Abrir "a fazer" para pessoa. |
| **GDF / SEFAZ-DF** | CND do Distrito Federal (Estadual + Municipal unificada no DF) | **Exige captcha** | https://ww1.receita.fazenda.df.gov.br/cidadao/certidoes/Certidao | SPA Angular chama `/api/emissao/certidaoCloudflare/debito` protegido por Cloudflare Turnstile / reCAPTCHA. Abrir "a fazer" para pessoa. |
| **SEFAZ-MA** | Certidão Negativa Estadual (Maranhão) | **Bloqueado / exige captcha** | https://sistemas1.sefaz.ma.gov.br/portalsefaz/jsp/pagina/pagina.jsf?codigo=1693 | Conexão encerrada pelo servidor (`Connection reset by peer`) a partir do contêiner e emissão web protegida por captcha. Abrir "a fazer" para pessoa. |
| **Prefeitura de Goiânia** | CND Municipal (Goiânia/GO) | **Exige captcha** | https://www.goiania.go.gov.br/sistemas/sccer/asp/sccer00201f0.asp | Formulário protegido por captcha + Cloudflare. Abrir "a fazer" para pessoa. |
| **Prefeitura de São Luís** | CND Municipal (São Luís/MA) | **Indisponível no contêiner** | https://stm.semfaz.saoluis.ma.gov.br/ | Timeout a partir do contêiner; emissão via portal web. Abrir "a fazer" para pessoa. |
| **TJGO** | Falência / Concordata / Recuperação Judicial (Goiás) | **Exige captcha** | https://projudi.tjgo.jus.br/CertidaoNegativaPositivaPublica?PaginaAtual=1 | Página exige `reCAPTCHA` + Cloudflare Turnstile. Abrir "a fazer" para pessoa. |
| **TJMA** | Falência / Concordata / Recuperação Judicial (Maranhão — JurisConsult) | **Exige captcha** | https://jurisconsult.tjma.jus.br/ | SPA Ionic exige Cloudflare Turnstile (`challenges.cloudflare.com/turnstile/v0/api.js`). Abrir "a fazer" para pessoa. |
| **CREA-DF / CREA-GO** | CRQ — Certidão de Registro e Quitação de Pessoa Jurídica | **Exige login** | https://www.creadf.org.br/ · https://www.creago.org.br/ | Emissão de CRQ de PJ requer acesso autenticado na área restrita da empresa no conselho (e `creadf.org.br` também falhou verificação de cadeia SSL no contêiner). Abrir "a fazer" para pessoa. |

---

## Receitas prontas (atalhos do script `emitir_certidao.py`)

### 1. TJDFT (`--emissor tjdft`)

- **Certidões suportadas:** `FALENCIA_CONCORDATA` (padrão), `CRIMINAL`, `CIVEL`, `ESPECIAL`.
- **Passo 1 — Consultar pessoa na Receita via API do TJDFT:**
  - `GET https://cnc-api.tjdft.jus.br/api/ext/pessoas/{cnpj_14_digitos}?nome={parte_do_nome}`
  - Headers obrigatórios: `Origin: https://cnc.tjdft.jus.br` e `Referer: https://cnc.tjdft.jus.br/`.
  - Retorna `{"nome_receita": "...", "tipo_pessoa": "JURIDICA", ...}`.
- **Passo 2 — Solicitar ou reaproveitar certidão:**
  - `POST https://cnc-api.tjdft.jus.br/api/ext/solicitacoes`
  - JSON: `{"nome": "<nome_receita>", "cpf_cnpj": "<cnpj_14_digitos>", "nome_mae": null, "nome_pai": null, "tipo_certidao": "FALENCIA_CONCORDATA"}`.
  - Se já existir certidão válida, devolve `certidao_existente: true` com `certidao.url_certidao` (link S3 assinado válido por ~15 min), `data_emissao` e `data_validade`.
  - Para forçar nova emissão (somente quando a vigente vencer antes da sessão): `?certidao_a_recriar=<id>`.
- **Passo 3 — Baixar PDF:** `GET url_certidao`.
- **Observação:** o TJDFT usa o `nome_receita`; divergência de sufixo societário (`EIRELI` vs. `LTDA`) com o mesmo CNPJ é normal e deve ir apenas em `observacao`, sem bloquear.

### 2. SEFAZ-GO (`--emissor sefaz-go`)

- **Certidão suportada:** `01` (Dívida Ativa — Certidão Negativa/Positiva de Débitos Inscritos em Dívida Ativa Estadual de Goiás).
- **Endpoint:** `POST https://www.sefaz.go.gov.br/Certidao/Emissao/certidao.asp`
- **Headers:** `Referer: https://www.sefaz.go.gov.br/Certidao/Emissao/`, `Content-Type: application/x-www-form-urlencoded`.
- **Campos do formulário (`application/x-www-form-urlencoded`):**
  - `Certidao.Tipo=01`
  - `Certidao.TipoDocumento=2` (CNPJ)
  - `Certidao.NumeroDocumento=<cnpj_14_digitos>`
  - `Certidao.NumeroDocumentoCNPJ=<cnpj_formatado>`
  - `Certidao.Espolio=N`
  - `Certidao.Render=pdf` (ou `xml` para metadados estruturados)
  - `Certidao.ValidarEmissao_Emitir=0`
  - `Certidao.ConfirmaNomeContribuinte=Sim`
- **Resposta:** `application/pdf` (`%PDF-1.3`) direto, sem captcha nem login. Quando o contribuinte não possui débito inscrito, emite Certidão Negativa com validade (em geral 60 dias).

---

## Protocolo para cadastrar novos emissores

Ao encontrar um edital que exija certidão de uma UF/município/conselho ainda ausente da tabela acima:

1. Localize o link oficial de emissão de certidões do órgão.
2. Inspecione o HTML e os scripts JS (se SPA) em Python no contêiner.
3. Se houver `recaptcha`, `hcaptcha`, `turnstile`, `captcha`, desafio WAF ou `login`/`gov.br`: **pare**, adicione uma linha na tabela acima com o status real e o link oficial, e devolva pendência para pessoa.
4. Se houver endpoint/formulário público sem captcha/login: valide o download do PDF, confira CNPJ/resultado/validade, acrescente a receita nesta página e (quando recorrente) adicione suporte em `scripts/emitir_certidao.py`.
