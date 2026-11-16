# Base de custos do grupo: esquema

`base-custos.json` é gerado por `scripts/ingerir_custos.py` a partir da planilha de pessoal do grupo (formato "TODOS_FUNCIONARIOS"). Não edite à mão: corrija a planilha de origem e rode a ingestão de novo.

## Planilha de origem

| Aba | O que a ingestão lê |
| --- | --- |
| Uma aba por pessoa (composição de custo) | Empresa, função, setor, salário, adicionais, VR, VT, encargos por grupo, custo mensal (linha "VII. Preço homem/mês") e horas/mês |
| Abas "A Pagar …" | Composições montadas para proposta; viram `modelos_proposta` |
| Faturamento | Alíquota de imposto e retenção de cada nota, por empresa |
| Abas de segmento (começam com "CEM POR CENTO") | Lucro, impostos e adicionais usados no preço; despesas mensais fixas da empresa; preço do litro da rota |

Abas sem empresa, sem função ou sem custo ficam fora e aparecem em `alertas`.

## Campos

| Campo | Conteúdo |
| --- | --- |
| `versao`, `competencia`, `gerado_em` | Versão do esquema, mês da folha (AAAA-MM) e data da ingestão |
| `fonte` | Nome do arquivo de origem e quantas abas foram lidas |
| `parametros` | Horas/mês, dias úteis, km por litro, dias de rota e preço do litro |
| `empresas.<slug>.tributos` | `aliquota` (sobre o faturamento), `aliquotas_vistas`, `retencao_tipica`, `notas`; `pendente` quando a planilha não tem a alíquota |
| `empresas.<slug>.encargos_sociais` | `total` e `grupos` (A a E) sobre a remuneração; `origem` diz se veio da empresa ou do padrão do grupo |
| `empresas.<slug>.beneficios` | `vr_dia` e `vt_dia` |
| `empresas.<slug>.administracao_central` | Pessoas e custo mensal do pessoal administrativo, sócios e apoio |
| `cargos_por_empresa[]` | `cargo`, `empresa`, `vinculo` (`clt` ou `prestador`), `n`, faixas de `salario_base`, `custo_mensal` e `custo_hora` (`min`, `med`, `media`, `max`), `periculosidade`, `horas_mes` |
| `cargos_grupo[]` | As mesmas faixas juntando as empresas (`empresa` = `grupo`) |
| `modelos_proposta[]` | Cargo, empresa, salário, periculosidade, encargos, custo mensal e custo-hora das abas "A Pagar" |
| `markup_referencia[]` | `segmento`, `aplica_a` (serviço ou peças), `lucro`, `impostos`, `adicionais` |
| `despesas_mensais_empresa[]` | `segmento`, `item`, `valor_mensal`, `tipo` (`despesa` ou `tributo pago`) |
| `alertas[]` | O que falta ou precisa de confirmação |

Slugs de empresa: `realmak`, `aforca`, `nortfort`, `una` e `alfa`. Prestadores sem empresa do grupo entram em `_prestadores_e_sem_empresa`.

## Cargos padrão

A função escrita na planilha vira um cargo padrão para que as faixas juntem a mesma função escrita de jeitos diferentes:

| Função na planilha | Cargo |
| --- | --- |
| Técnico, Tec. de Manutenção | Técnico de manutenção |
| Aux Técnico, Aux Téc, Auxiliar Técnico | Auxiliar técnico |
| Eletrotécnico | Eletrotécnico |
| Ajudante Geral | Ajudante geral |
| Meio Oficial, Oficial | Meio oficial, Oficial |
| Eng Mecânico, Eng Elétrico, Eng Civil | Engenheiro mecânico, eletricista, civil |
| Vidraceiro | Vidraceiro |

Função de execução fora dessa lista aparece em `alertas`. Para incluir uma nova, acrescente o padrão em `CARGOS` no script.

## Custo mensal

É o custo cheio da composição de cada pessoa, como a planilha calcula: salário, adicionais, encargos dos grupos A a E, VR, VT e diferenças, sem lucro e sem tributo. Por isso a faixa de um cargo pode ser bem maior que salário mais encargos legais quando há hora extra ou gratificação. `consultar_base.py` separa essa parte em `E_detalhe.outros_itens_folha`.
