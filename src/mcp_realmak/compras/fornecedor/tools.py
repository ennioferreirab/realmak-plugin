"""Ferramenta de contratos vigentes por CNPJ (PNCP + Compras.gov.br)."""

from __future__ import annotations

import time
from datetime import date

from fastmcp import Context

from mcp_realmak.compras._shared.formatting import format_brl, markdown_table

from . import client


def _dias(data_fim: str | None) -> str:
    try:
        return str((date.fromisoformat(data_fim or "") - date.today()).days)
    except ValueError:
        return "?"


def _celula(texto: str | None, limite: int = 90) -> str:
    limpo = " ".join((texto or "").split()).replace("|", "/")
    return limpo if len(limpo) <= limite else limpo[: limite - 1] + "…"


def _orgao_unidade(c: client.ContratoVigente) -> str:
    orgao, unidade = c.orgao or "", c.unidade or ""
    return f"{orgao} · {unidade}" if unidade and unidade.lower() != orgao.lower() else orgao


def _eta(v: client.Varredura) -> str:
    decorrido = time.monotonic() - v.iniciada_em
    if v.feitos < 20 or decorrido < 10:
        return ""
    restantes = (v.total - v.feitos) / (v.feitos / decorrido)
    return f" Faltam cerca de {max(1, round(restantes / 60))} min."


def formatar(res: client.Resultado) -> str:
    v = res.varredura
    nome = res.razao_social or "razão social não encontrada no Compras.gov.br"
    linhas = [f"## Contratos vigentes: {nome} ({res.cnpj})", ""]
    if res.habilitado is not None:
        linhas.append(f"Habilitado a licitar no Compras.gov.br: {'sim' if res.habilitado else 'não'}.")
        linhas.append("")

    vigentes = [c for c in res.contratos if c.vigente()]
    a_verificar = [c for c in res.contratos if not c.vigente()]
    prorrogados = [c for c in vigentes if c.verificado == "prorrogado"]

    def tabela(lista: list[client.ContratoVigente]) -> str:
        return markdown_table(
            ["Órgão", "Nº", "Objeto", "Vence em", "Dias", "Valor global", "Fonte"],
            [
                [
                    _celula(_orgao_unidade(c), 55),
                    c.numero or "—",
                    _celula(c.objeto),
                    c.data_fim or "—",
                    _dias(c.data_fim),
                    format_brl(c.valor_global) if c.valor_global else "—",
                    " + ".join(sorted(c.fontes)),
                ]
                for c in lista
            ],
        )

    if vigentes:
        total = sum(c.valor_global or 0 for c in vigentes)
        linhas.append(
            f"**{len(vigentes)} contratos vigentes** · valor global somado "
            f"{format_brl(total)} (sem contar duas vezes o mesmo contrato)."
        )
        linhas.append("")
        linhas.append(tabela(vigentes))
        if prorrogados:
            linhas.append("")
            linhas.append(
                f"{len(prorrogados)} destes constavam como encerrados no Compras.gov.br e foram "
                "confirmados como prorrogados por aditivo no Contratos.gov.br (vigência e valor de lá): "
                + "; ".join(f"{_celula(c.orgao, 30)} {c.numero or ''}" for c in prorrogados)
                + "."
            )
        divergentes = [
            c
            for c in vigentes
            if c.valor_pncp and c.valor_global and abs(c.valor_pncp - c.valor_global) > 0.01
        ]
        if divergentes:
            linhas.append("")
            linhas.append(
                "Valor diferente entre as fontes (a tabela usa o do Compras.gov.br; "
                "o do PNCP costuma não refletir aditivos): "
                + "; ".join(
                    f"{_celula(c.orgao, 30)} {c.numero or ''} PNCP {format_brl(c.valor_pncp or 0)}"
                    for c in divergentes
                )
                + "."
            )
        com_link = [c for c in vigentes if c.link_pncp]
        if com_link:
            linhas.append("")
            linhas.append("Links no PNCP:")
            linhas.extend(
                f"- {_celula(c.orgao, 40)} {c.numero or ''}: {c.link_pncp}" for c in com_link
            )
    else:
        linhas.append("Nenhum contrato vigente encontrado nas fontes consultadas.")

    if a_verificar:
        linhas += [
            "",
            f"### Confirmar prorrogação ({len(a_verificar)})",
            "O Compras.gov.br dá estes contratos por encerrados (fim nos últimos "
            f"{client.JANELA_PASSADO_ANOS} anos) e a checagem de aditivos no Contratos.gov.br não "
            "os confirmou (não constam entre os ativos da UG, ou a consulta demorou). Muitos já "
            "acabaram, mas alguns podem estar prorrogados: confirme no histórico do contrato "
            "(`contratosgovbr_consultar_historico_contrato`), no cérebro da Realmak ou no termo aditivo. "
            "Não entram na contagem nem na soma acima. Chame de novo para completar a checagem.",
            "",
            tabela(a_verificar),
        ]

    linhas += ["", "### Cobertura"]
    if res.pncp_ok:
        linhas.append("- PNCP (Lei 14.133, qualquer esfera): consultado.")
    else:
        linhas.append(f"- PNCP: **falhou** ({res.pncp_erro}). Tente de novo; a lista pode estar incompleta.")
    if res.conlicitacao_ok:
        linhas.append("- ConLicitação (tela Contratos): consultado.")
    else:
        linhas.append(
            f"- ConLicitação: indisponível ({res.conlicitacao_erro}). A lista segue sem essa fonte."
        )
    escopo = "órgãos indicados" if res.escopo_restrito else "órgãos federais"
    if v.concluida:
        linhas.append(
            f"- Compras.gov.br (SIASG, federal): {v.feitos} de {v.total} {escopo} consultados."
        )
        if v.falhas:
            linhas.append(
                f"  **Sem resposta ({len(v.falhas)}):** {', '.join(v.falhas[:10])}"
                + (" …" if len(v.falhas) > 10 else "")
                + ". Chame de novo mais tarde para repetir."
            )
    else:
        pct = round(100 * v.feitos / v.total) if v.total else 0
        linhas.append(
            f"- Compras.gov.br: **varredura em andamento**, {v.feitos} de {v.total} {escopo} "
            f"({pct}%).{_eta(v)} O resultado acima é parcial. Chame a ferramenta de novo com o mesmo CNPJ "
            "para atualizar; a varredura continua em segundo plano."
        )
    if not res.escopo_restrito:
        linhas.append(
            "- Fora do alcance: contratos de órgãos estaduais e municipais anteriores à Lei 14.133 "
            "e contratos ainda não publicados."
        )
    linhas.append(
        "- Datas incluem os aditivos de prazo que a fonte já registrou; confira o termo aditivo "
        "dos contratos que vencem em breve."
    )
    return "\n".join(linhas)


async def contratos_vigentes_por_cnpj(
    cnpj: str,
    ctx: Context,
    aguardar_segundos: int = 45,
    codigos_orgao: str | None = None,
) -> str:
    """Lista os contratos vigentes de um fornecedor a partir do CNPJ.

    Use quando a pergunta é "quais contratos esta empresa tem ativos?" e você só
    tem o CNPJ. Nenhuma API oficial filtra contrato só por fornecedor, então a
    ferramenta cruza três fontes e junta o resultado sem repetir contratos:
    1. PNCP: busca do portal por contratos vigentes do CNPJ (Lei 14.133, todas as esferas).
    2. ConLicitação: tela Contratos do site, com o login do servidor (rápida, com a vigência
       original do contrato).
    3. Compras.gov.br: varre os órgãos federais atrás de contratos do CNPJ (inclui os do
       SIASG que não estão no PNCP). A varredura leva cerca de 10 minutos (o Compras.gov.br
       limita a ~2 consultas por segundo) e roda em
       segundo plano.

    Contratos antigos prorrogados por aditivo aparecem no Compras.gov.br com a vigência original
    (já vencida). Eles vêm numa lista à parte, "Confirmar prorrogação", e não entram na contagem
    de vigentes: confirme no histórico do contrato ou no cérebro antes de afirmar que vigoram.

    Se a varredura não terminar em `aguardar_segundos`, devolve o resultado parcial com
    o andamento. Chame de novo com o mesmo CNPJ para ver o resto; o progresso é guardado.
    O mesmo CNPJ fica em cache por 6 horas.

    Para conferir um contrato em detalhe (aditivos, empenhos, faturas), use
    `contratosgovbr_*` ou abra o link do PNCP.

    Args:
        cnpj: CNPJ do fornecedor, com ou sem pontuação.
        aguardar_segundos: Quanto esperar pela varredura antes de devolver o parcial (0 a 110).
        codigos_orgao: Opcional, separados por vírgula (ex.: "52111,26203"): consulta só esses
            órgãos no Compras.gov.br, em poucos segundos. Ache os códigos com `dadosabertos_buscar_orgao`.

    Returns:
        Tabela dos contratos vigentes (órgão, número, objeto, vencimento, valor, fonte) e a
        cobertura da consulta.
    """
    numero = client.apenas_digitos(cnpj)
    if not client.cnpj_valido(numero):
        return (
            f"CNPJ inválido: '{cnpj}'. Informe os 14 dígitos (com ou sem pontuação) "
            "com os dígitos verificadores corretos."
        )
    codigos = [c.strip() for c in (codigos_orgao or "").split(",") if c.strip()] or None
    espera = max(0, min(int(aguardar_segundos), 110))
    await ctx.info(f"Consultando contratos vigentes do CNPJ {numero}...")
    resultado = await client.contratos_vigentes(numero, aguardar_s=float(espera), codigos_orgao=codigos)
    await ctx.info(f"{len(resultado.contratos)} contratos encontrados até agora")
    return formatar(resultado)
