# Modelo de contraproposta

Usar só nos casos do passo 7.4 da skill. Preencher os campos entre `<>`. Texto curto. Nada sai sem aprovação; a contraproposta não herda a aprovação do pedido.

Não citar: órgão, licitação, nome ou preço de outro fornecedor, orçamento total, alvo, margem ou preço de venda da empresa.

`data_limite`: posterior à preparação e dentro da janela operacional antes da sessão (`cotacao.prazo_limite_dias_antes_sessao`). Não herde prazo vencido do pedido. Sem janela útil: mantenha o rascunho interno e registre a limitação na s5, sem prometer aprovação.

```
---
para: <mesmo e-mail do pedido>
assunto: "Re: Pedido de cotação — <produto> — <quantidade> <unidade>"
data_limite: <AAAA-MM-DD>
estado: aguardando_aprovacao
contraproposta_de: <id do pedido>
---

Prezados,

Obrigado pela proposta de <data da resposta> para <produto>, <quantidade> <unidade>.

<Com preço pedido:> Para seguir com este volume, precisamos de preço unitário de até R$ <preço pedido>, nas mesmas condições (<frete>, <pagamento>). É possível?
<Sem preço pedido:> Para este volume, qual o melhor preço unitário que podem oferecer?

<Se o fornecedor deu faixa de volume:> Informe também o preço para <quantidade estimada>, sem compromisso de compra mínima.

Precisamos da resposta até <data-limite>.

Atenciosamente,
<nome> — <cargo>
<empresa> · <telefone>
```
