# Avisos de terceiros

## mcp-brasil (licença MIT)

O módulo `src/mcp_realmak/compras/` (ferramentas `pncp_*`, `dadosabertos_*` e
`contratosgovbr_*`), os módulos auxiliares em `src/mcp_realmak/compras/_shared/`
e os testes em `tests/compras/` foram extraídos do projeto **mcp-brasil**
(https://github.com/Mcp-Brasil/mcp-brasil), a partir de um fork mantido pelo
autor deste repositório.

- Commit de origem: `84980e5` ("feat(compras): accept free text in the Pesquisa de Preço tools"),
  ramo `feat/compras-pesquisa-preco` do fork. Esse ramo inclui as ferramentas de
  Pesquisa de Preço, que ainda não estão no projeto original.
- Alterações: caminhos de importação (`mcp_brasil` para `mcp_realmak`), configuração
  do cliente HTTP reduzida a variáveis `MCP_REALMAK_*` (sem carga de `.env`) e remoção
  do registro de "features" do mcp-brasil. O comportamento das ferramentas é o mesmo.

Texto da licença do mcp-brasil, conforme o arquivo LICENSE do projeto de origem:

```
MIT License

Copyright (c) 2025-2026 MCP Brasil

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### Avisos que o mcp-brasil exige que acompanhem a redistribuição

O arquivo NOTICE do mcp-brasil pede que se mantenha o NOTICE, o LICENSE e a referência ao
SOURCES.md. Cópias fiéis estão em `third_party/mcp-brasil/` (LICENSE, NOTICE, SOURCES.md e
ACCEPTABLE_USE.md). Em resumo:

1. **A licença MIT cobre só o código.** Os dados devolvidos pelas APIs públicas (PNCP,
   Compras.gov.br, Contratos.gov.br) têm termos próprios. Para compras públicas, o SOURCES.md
   registra: publicidade obrigatória pela Lei 14.133/2021; CNPJ de fornecedores é dado
   público; CPF de pessoa física exige cuidado.
2. **Marcas e nomes de órgãos públicos** são citados só como referência. Este projeto é
   independente e não é serviço oficial de nenhum órgão.
3. **Uso aceitável:** respeite o ACCEPTABLE_USE.md (LGPD, vedação de perseguição de pessoas,
   de apresentar saída de IA como dado oficial sem conferir na fonte, e de sugerir oficialidade).
4. **Aviso aos usuários finais:** os dados podem conter erros, estar desatualizados ou ser
   mal interpretados por modelos de IA. Confira na fonte oficial antes de usar em decisão.
