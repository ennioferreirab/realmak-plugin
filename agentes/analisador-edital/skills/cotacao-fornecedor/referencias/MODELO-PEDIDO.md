# Modelo de pedido de cotação

Preencher os campos entre `<>`. Remover blocos que não se aplicam. Texto curto e objetivo. Não citar órgão nem número da licitação. Não prometer compra.

O arquivo do pedido começa pelo frontmatter abaixo; o resto do arquivo é o corpo do e-mail, em texto simples (sem tabela nem negrito Markdown). O remetente é a conta conectada em Painel de controle → E-mail.

```
---
para: <e-mail comercial oficial do fornecedor>
assunto: "Pedido de cotação — <produto/serviço resumido> — <quantidade> <unidade>"
data_limite: <AAAA-MM-DD>
estado: rascunho
---

Prezados,

A <empresa que disputaria> (CNPJ <cnpj>) solicita o melhor preço para o volume abaixo:

- Item <n>: <especificação técnica exigida, sem cortar requisitos obrigatórios> — <qtd total estimada> <un>

<Se registro de preços:> As quantidades são estimadas para até <vigência> meses, sem garantia de compra mínima.
<Se o item permitir:> Informe também o preço unitário a partir de <25%>, <50%> e <100%> da quantidade.

Condições:
- Entrega em <cidade/UF>, frete incluso (CIF). Se não for possível, informe o frete à parte.
- Pagamento: informe o preço à vista e para pagamento em <prazo de pagamento do órgão> dias.
- Prazo de entrega desejado: até <N> dias após o pedido.
- Validade mínima da proposta: <N> dias.
- Informe preço unitário e total, impostos inclusos, NCM, origem, prazo de entrega e garantia.

<Somente se o edital exigir; manter o que couber:>
- Carta de solidariedade do fabricante em nome da <empresa>.
- Credenciamento da <empresa> para instalação ou assistência técnica da marca.
- Registro do produto em <órgão regulador>.

Precisamos da resposta até <data-limite>.

Atenciosamente,
<nome> — <cargo>
<empresa> · <telefone>
```
