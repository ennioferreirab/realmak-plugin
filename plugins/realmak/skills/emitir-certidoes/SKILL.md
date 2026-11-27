---
name: emitir-certidoes
description: Emite ou reaproveita certidões públicas sem navegador (via Python/HTTP no contêiner), confere CNPJ, nome, resultado e validade no PDF, grava em DOCUMENTOS PARA DISPUTA e registra como recorrente. Para emissores ainda não mapeados, orienta a descoberta de APIs públicas sem contornar captcha ou login; quando houver captcha ou login, abre pendência com link direto e instrução.
---

# Emitir certidões sem navegador

Objetivo: emitir automaticamente (ou reaproveitar vigente) toda certidão exigida pelo edital que esteja ausente, vencida ou vencendo antes da data da sessão pública, usando apenas chamadas HTTP em Python no contêiner (`urllib`) — **sem navegador** e **sem nunca contornar captcha ou login**.

## 1. Determinar o emissor (genérico por empresa e edital)

Nunca assuma um único tribunal ou fazenda. Determine o emissor combinando **a exigência do edital** com **a sede/domicílio da empresa disputante** obtida via `dados_empresa(empresa)` (nunca use CNPJ fixo nem dados de outra empresa):

- **Falência, concordata e recuperação judicial:** Tribunal de Justiça (TJ) da UF/comarca da sede da empresa (ex.: TJDFT para empresas sediadas no DF, TJGO para GO, TJMA para MA).
- **Fazenda Estadual:** SEFAZ da UF da sede da empresa (e da UF do órgão licitante, se o edital exigir expressamente).
- **Fazenda Municipal:** Secretaria de Fazenda do município da sede (no Distrito Federal, a CND do GDF é unificada estadual + municipal).
- **Fazenda Federal / Dívida Ativa da União:** RFB/PGFN.
- **FGTS (CRF):** Caixa Econômica Federal.
- **Débitos Trabalhistas (CNDT):** TST.
- **Conselhos profissionais (CRQ PJ):** CREA, CFT, CAU ou conselho da UF correspondente.

## 2. Consultar receitas prontas ou descobrir caminho automático

Consulte primeiro [references/emissores.md](references/emissores.md):

1. **Emissor com receita `funciona`:** execute o script diretamente (no contêiner do daemon, use `python3` direto):

```bash
python3 /plugin-realmak/skills/emitir-certidoes/scripts/emitir_certidao.py \
  --emissor <codigo> \
  --cnpj <cnpj_da_empresa> \
  --nome "<razao_social_ou_trecho>" \
  --saida "/tmp/certidoes/<nome_arquivo>.pdf"
```

   - No TJDFT, o script **reaproveita certidão vigente por padrão** (`certidao_existente: true`), sem forçar nova emissão. Só passe `--recriar` se a certidão existente vencer antes da sessão pública.
2. **Emissor marcado como `exige captcha` ou `exige login`:** **não tente contornar**. Retorne imediatamente a pendência com o link oficial direto e a instrução objetiva para uma pessoa emitir e subir na pasta da disputa.
3. **Emissor ainda não listado em `references/emissores.md` (descoberta genérica):**
   - Baixe a página oficial de emissão de certidões do órgão via Python (`urllib`) ou `abrir_pagina`.
   - **Verificação obrigatória de bloqueio:** se a página ou seus scripts tiverem `recaptcha`, `hcaptcha`, `turnstile`, `captcha`, desafio anti-bot/WAF ou exigirem `login`/`gov.br`/certificado digital, **pare imediatamente** e registre a pendência para pessoa com o link direto.
   - Se for SPA (Angular, React, Vue, Ionic) sem captcha/login, inspecione os bundles JS para identificar a API pública (`/api/...`), headers exigidos (`Origin`, `Referer`) e campos do pedido.
   - Se for formulário HTML tradicional sem captcha/login, inspecione `<form>` e os `<input>`/`<select>` (incluindo eventual etapa de confirmação de nome).
   - Teste com `GET`/`POST` em Python no contêiner, baixe o PDF e confira o conteúdo.
   - Quando funcionar, **registre a nova receita** em [references/emissores.md](references/emissores.md) (emissor, URLs, cabeçalhos, campos, regra de validade e observações) para que as próximas execuções usem o atalho direto.

## 3. Conferir o PDF antes de publicar

O script faz a conferência automática do PDF (e deve ser validada na resposta):

- **Arquivo válido:** cabeçalho `%PDF` e texto legível.
- **CNPJ:** dígitos do CNPJ no texto do PDF conferem com a empresa disputante.
- **Nome / razão social:** se o órgão retornar razão social da Receita com sufixo antigo (ex.: `EIRELI` no TJDFT enquanto o contrato social já diz `LTDA`, com o **mesmo CNPJ**), **não bloqueie** — registre em `observacao`.
- **Resultado:** deve ser `NADA CONSTA`, `NEGATIVA` ou `POSITIVA COM EFEITOS DE NEGATIVA`. Se constar `POSITIVA` (sem efeito de negativa), marque `situacao: "pendente"` e detalhe o motivo.
- **Validade:** confira `validade` em `AAAA-MM-DD` frente à data da sessão pública.

## 4. Publicar no card e registrar como recorrente

Quando a certidão estiver válida e conferida:

1. Grave em **DOCUMENTOS PARA DISPUTA** com `disputa_adicionar(nome, arquivo, exigencia, substituir?, empresa?, bloqueia?, momento?, risco_inabilitacao?, motivo_bloqueio?)`, vinculando ao **rótulo exato** da exigência em `habilitacao.json`. Nunca sobrescreva arquivo de `origem: "pessoa"`.
2. Registre no Cérebro da empresa com `registrar_recorrente(empresa, tipo, arquivo, nome, validade)` (com `validade` em `AAAA-MM-DD`).
3. Remova cópias temporárias fora de **DOCUMENTOS PARA DISPUTA** (use `/tmp/certidoes/...` como pasta de saída para não poluir `"Entregas da IA"`).

## 5. Saída estruturada (inclusive para subagentes T2)

Ao executar como subagente T2 (um por certidão emitível em paralelo), devolva sempre um JSON com o contrato:

```json
{
  "certidao": "falencia",
  "situacao": "ok",
  "validade": "2026-12-24",
  "arquivo": "H-11 - Certidão de falência.pdf",
  "observacao": "Reaproveitada certidão vigente do TJDFT; razão social consta como EIRELI na Receita (mesmo CNPJ da LTDA)."
}
```

Em caso de falha, captcha ou login, devolva `situacao: "pendente"`, `arquivo: null`, `validade: null` e `observacao` contendo o **link oficial direto** e a **instrução curta** para o gestor abrir o "a fazer" para uma pessoa.
