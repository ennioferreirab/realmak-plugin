"""Contratos vigentes de um CNPJ, cruzando PNCP, ConLicitação e Compras.gov.br.

Por que existe: nenhuma API oficial filtra contratos só pelo fornecedor.
- PNCP (consulta/v1) não tem busca por fornecedor; a busca do portal
  (/api/search) tem e devolve só o que está publicado no PNCP (Lei 14.133).
- Compras.gov.br filtra por fornecedor (niFornecedor), mas só dentro de UM órgão
  (codigoOrgao obrigatório). Para cobrir os contratos federais antigos
  (SIASG) é preciso varrer os órgãos federais, em segundo plano.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import httpx

from mcp_realmak.compras._shared.cache import TTLCache
from mcp_realmak.compras._shared.formatting import parse_brl_number
from mcp_realmak.compras._shared.http_client import create_client, http_get
from mcp_realmak.compras.contratosgovbr.client import _parse_contrato
from mcp_realmak.compras.contratosgovbr.constants import CONTRATO_POR_UG_URL
from mcp_realmak.compras.contratosgovbr.schemas import ContratoResumo
from mcp_realmak.compras.dadosabertos import client as dados_abertos
from mcp_realmak.compras.dadosabertos.constants import CONTRATOS_FIM_VIGENCIA_URL
from mcp_realmak.compras.pncp import client as pncp

logger = logging.getLogger(__name__)

CONCORRENCIA = 3  # o Compras.gov.br aceita rajadas, mas sustenta só ~2 consultas/s (depois, 429)
# Quem tem mais chance de ter contrato vem primeiro; só muda o tempo até os primeiros achados.
_PRIORIDADE_TIPO = {
    "ADMINISTRACAO DIRETA": 0,
    "AUTARQUIA": 0,
    "FUNDACAO": 0,
    "EMPRESA PUBLICA COMERCIAL E FINANCEIRA": 1,
    "ECONOMIA MISTA": 1,
}
TENTATIVAS_POR_ORGAO = 8
VARREDURA_TTL_S = 6 * 3600.0
MAX_VARREDURAS = 32
JANELA_PASSADO_ANOS = 6  # contratos que o Compras.gov.br dá por encerrados mas podem ter aditivo
VERIFICACAO_ORCAMENTO_S = 40.0  # tempo máximo, por chamada, para checar aditivos no Contratos.gov.br
PNCP_PAGINAS_MAX = 10
PNCP_TAMANHO = 50


def apenas_digitos(valor: str) -> str:
    return "".join(ch for ch in valor if ch.isdigit())


def cnpj_valido(cnpj: str) -> bool:
    """Confere tamanho e dígitos verificadores."""
    if len(cnpj) != 14 or not cnpj.isdigit() or len(set(cnpj)) == 1:
        return False
    for tamanho in (12, 13):
        pesos = list(range(tamanho - 7, 1, -1)) + list(range(9, 1, -1))
        soma = sum(int(d) * p for d, p in zip(cnpj[:tamanho], pesos, strict=False))
        digito = 0 if soma % 11 < 2 else 11 - soma % 11
        if int(cnpj[tamanho]) != digito:
            return False
    return True


@dataclass
class ContratoVigente:
    fontes: set[str] = field(default_factory=set)
    orgao: str | None = None
    unidade: str | None = None
    numero: str | None = None
    objeto: str | None = None
    modalidade: str | None = None
    data_inicio: str | None = None
    data_fim: str | None = None
    valor_global: float | None = None
    valor_pncp: float | None = None
    controle_pncp: str | None = None
    link_pncp: str | None = None
    codigo_orgao: str | None = None
    codigo_ug: str | None = None
    # Checagem de aditivos no Contratos.gov.br: "prorrogado" (achado entre os ativos da UG) ou
    # "nao_listado". O segundo NÃO prova que encerrou: a lista da UG pode não trazer o contrato.
    verificado: str | None = None

    def vigente(self, hoje: date | None = None) -> bool:
        """Sem data de fim (PNCP já filtra vigentes) conta como vigente."""
        return not self.data_fim or self.data_fim >= (hoje or date.today()).isoformat()


@dataclass
class Varredura:
    """Estado da varredura de órgãos federais no Compras.gov.br para um CNPJ."""

    cnpj: str
    total: int = 0
    feitos: int = 0
    registros: list[dict[str, Any]] = field(default_factory=list)
    falhas: list[str] = field(default_factory=list)
    iniciada_em: float = field(default_factory=time.monotonic)
    concluida_em: float | None = None
    tarefa: asyncio.Task[None] | None = None

    @property
    def concluida(self) -> bool:
        return self.concluida_em is not None


@dataclass
class Resultado:
    cnpj: str
    razao_social: str | None
    habilitado: bool | None
    contratos: list[ContratoVigente]
    pncp_ok: bool
    pncp_erro: str | None
    varredura: Varredura
    escopo_restrito: bool
    conlicitacao_ok: bool = False
    conlicitacao_erro: str | None = None
    verificacao_pendente: int = 0


_VARREDURAS: dict[str, Varredura] = {}


class _Freio:
    """Pausa global quando o Compras.gov.br responde 429."""

    def __init__(self) -> None:
        self._ate = 0.0

    async def esperar(self) -> None:
        atraso = self._ate - time.monotonic()
        if atraso > 0:
            await asyncio.sleep(atraso)

    def frear(self, segundos: float) -> None:
        self._ate = max(self._ate, time.monotonic() + segundos)


async def _consultar_orgao(
    http: httpx.AsyncClient, freio: _Freio, codigo_orgao: str, cnpj: str, hoje: date
) -> list[dict[str, Any]]:
    """Contratos vigentes do CNPJ em um órgão. Levanta em falha definitiva."""
    params = {
        "codigoOrgao": codigo_orgao,
        "niFornecedor": cnpj,
        # Da janela no passado até o futuro: o Compras.gov.br não atualiza a vigência
        # de contratos antigos prorrogados por aditivo; eles voltam como "encerrados".
        "dataVigenciaFinalMin": date(hoje.year - JANELA_PASSADO_ANOS, hoje.month, min(hoje.day, 28)).isoformat(),
        "dataVigenciaFinalMax": hoje.replace(year=hoje.year + 15, day=min(hoje.day, 28)).isoformat(),
        "pagina": "1",
        "tamanhoPagina": "500",
    }
    ultimo: str = ""
    for tentativa in range(TENTATIVAS_POR_ORGAO):
        await freio.esperar()
        try:
            resp = await http.get(CONTRATOS_FIM_VIGENCIA_URL, params=params)
        except httpx.TransportError as exc:
            ultimo = type(exc).__name__
            await asyncio.sleep(min(1.0 * (tentativa + 1), 5.0))
            continue
        if resp.status_code == 200:
            dados = resp.json()
            itens = dados.get("resultado", []) if isinstance(dados, dict) else []
            return [i for i in itens if isinstance(i, dict) and not i.get("contratoExcluido")]
        if resp.status_code == 429:
            try:
                espera = float(resp.headers.get("retry-after", "1"))
            except ValueError:
                espera = 1.0
            freio.frear(espera + random.uniform(0.1, 0.6))
            ultimo = "429"
            continue
        if resp.status_code >= 500:
            ultimo = str(resp.status_code)
            await asyncio.sleep(min(1.0 * (tentativa + 1), 5.0))
            continue
        raise RuntimeError(f"HTTP {resp.status_code}")
    raise RuntimeError(f"sem resposta ({ultimo})")


async def _varrer(estado: Varredura, orgaos: list[tuple[str, str]]) -> None:
    hoje = date.today()
    freio = _Freio()

    async def passada(lote: list[tuple[str, str]], concorrencia: int) -> list[tuple[str, str]]:
        fila: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
        for item in lote:
            fila.put_nowait(item)
        falhou: list[tuple[str, str]] = []

        async def trabalhador(http: httpx.AsyncClient) -> None:
            while True:
                try:
                    codigo, nome = fila.get_nowait()
                except asyncio.QueueEmpty:
                    return
                try:
                    for reg in await _consultar_orgao(http, freio, codigo, estado.cnpj, hoje):
                        reg.setdefault("nomeOrgao", nome)
                        estado.registros.append(reg)
                    estado.feitos += 1
                except Exception as exc:
                    logger.warning("Órgão %s (%s) falhou: %s", codigo, nome, exc)
                    falhou.append((codigo, nome))

        async with create_client(timeout=30.0) as http:
            await asyncio.gather(*(trabalhador(http) for _ in range(concorrencia)))
        return falhou

    try:
        falhas = await passada(orgaos, CONCORRENCIA)
        if falhas:  # uma segunda chance, mais devagar, para os que estouraram o limite
            await asyncio.sleep(5)
            falhas = await passada(falhas, 2)
        estado.falhas = [f"{c} {n}" for c, n in falhas]
    finally:
        estado.concluida_em = time.monotonic()


async def _orgaos_federais(codigos: list[str] | None) -> list[tuple[str, str]]:
    todos = await dados_abertos.listar_orgaos()
    ordenados = sorted(
        (o for o in todos if o.esfera == "F" and o.codigo_orgao),
        key=lambda o: _PRIORIDADE_TIPO.get((o.tipo_administracao or "").upper(), 2),
    )
    federais = [(o.codigo_orgao or "", o.nome_orgao or "") for o in ordenados]
    if codigos:
        pedidos = set(codigos)
        achados = {c: n for c, n in federais if c in pedidos}
        return [(c, achados.get(c, c)) for c in codigos]
    return federais


def _varredura_de(cnpj: str, chave: str) -> Varredura | None:
    estado = _VARREDURAS.get(chave)
    if estado is None:
        return None
    if estado.concluida and time.monotonic() - (estado.concluida_em or 0) > VARREDURA_TTL_S:
        del _VARREDURAS[chave]
        return None
    return estado


async def _iniciar_varredura(cnpj: str, codigos: list[str] | None) -> Varredura:
    chave = f"{cnpj}:{','.join(sorted(codigos or []))}"
    estado = _varredura_de(cnpj, chave)
    if estado is not None:
        return estado
    orgaos = await _orgaos_federais(codigos)
    estado = Varredura(cnpj=cnpj, total=len(orgaos))
    if len(_VARREDURAS) >= MAX_VARREDURAS:
        mais_antiga = min(_VARREDURAS, key=lambda k: _VARREDURAS[k].iniciada_em)
        del _VARREDURAS[mais_antiga]
    _VARREDURAS[chave] = estado
    estado.tarefa = asyncio.create_task(_varrer(estado, orgaos))
    return estado


def _numero_do_titulo(titulo: str | None) -> str | None:
    """'Contrato nº 00116/2024' -> '00116/2024'."""
    if not titulo or "nº" not in titulo:
        return None
    return titulo.split("nº", 1)[1].strip() or None


async def _contratos_pncp(cnpj: str) -> list[ContratoVigente]:
    """Contratos vigentes do CNPJ na busca do portal do PNCP.

    A busca é textual (q=<cnpj>), então só vale o que traz o CNPJ como fornecedor.
    """
    achados: list[ContratoVigente] = []
    for pagina in range(1, PNCP_PAGINAS_MAX + 1):
        res = await pncp.pesquisar(
            cnpj, tipo="contrato", status="vigente", pagina=pagina, tamanho=PNCP_TAMANHO
        )
        for d in res.documentos:
            if apenas_digitos(d.fornecedor_ni or "") != cnpj:
                continue
            achados.append(
                ContratoVigente(
                    fontes={"PNCP"},
                    orgao=d.orgao_nome,
                    unidade=d.unidade_nome,
                    numero=_numero_do_titulo(d.titulo),
                    objeto=d.descricao or d.titulo,
                    modalidade=d.modalidade_nome,
                    data_inicio=(d.data_inicio or "")[:10] or None,
                    data_fim=(d.data_fim or "")[:10] or None,
                    valor_pncp=d.valor_global,
                    valor_global=d.valor_global,
                    controle_pncp=d.numero_controle_pncp,
                    link_pncp=d.link_pncp,
                )
            )
        if pagina * PNCP_TAMANHO >= res.total or not res.documentos:
            break
    return achados


def _contrato_compras(reg: dict[str, Any]) -> ContratoVigente:
    return ContratoVigente(
        fontes={"Compras.gov.br"},
        orgao=reg.get("nomeOrgao"),
        unidade=reg.get("nomeUnidadeGestora"),
        numero=reg.get("numeroContrato"),
        objeto=reg.get("objeto"),
        modalidade=reg.get("nomeModalidadeCompra"),
        data_inicio=(reg.get("dataVigenciaInicial") or "")[:10] or None,
        data_fim=(reg.get("dataVigenciaFinal") or "")[:10] or None,
        valor_global=reg.get("valorGlobal"),
        controle_pncp=reg.get("numeroControlePncpContrato"),
        codigo_orgao=str(reg["codigoOrgao"]) if reg.get("codigoOrgao") is not None else None,
        codigo_ug=str(reg["codigoUnidadeGestora"]) if reg.get("codigoUnidadeGestora") else None,
    )


def _numero_ano(c: ContratoVigente) -> tuple[int, str] | None:
    """('00116/2024') -> (116, '2024'); o ano cai para o início da vigência se faltar."""
    if not c.numero:
        return None
    bruto, _, sufixo = c.numero.partition("/")
    digitos = "".join(ch for ch in bruto if ch.isdigit())
    ano = sufixo.strip()[:4] or (c.data_inicio or "")[:4]
    return (int(digitos), ano) if digitos and ano else None


def _mesmo_contrato(a: ContratoVigente, b: ContratoVigente) -> bool:
    """Sem número de controle do PNCP: mesmo número e ano, e valor ou fim de vigência iguais."""
    chave = _numero_ano(a)
    if chave is None or chave != _numero_ano(b):
        return False
    valor_perto = (
        a.valor_global is not None
        and b.valor_global is not None
        and abs(a.valor_global - b.valor_global) <= 1.0
    )
    return valor_perto or bool(a.data_fim and a.data_fim == b.data_fim)


def _incorporar(base: list[ContratoVigente], novos: list[ContratoVigente]) -> None:
    por_controle = {c.controle_pncp: c for c in base if c.controle_pncp}
    for n in novos:
        existente = por_controle.get(n.controle_pncp) if n.controle_pncp else None
        if existente is None:
            existente = next((c for c in base if _mesmo_contrato(c, n)), None)
        if existente is None:
            base.append(n)
            if n.controle_pncp:
                por_controle[n.controle_pncp] = n
            continue
        existente.fontes |= n.fontes
        existente.link_pncp = existente.link_pncp or n.link_pncp
        existente.controle_pncp = existente.controle_pncp or n.controle_pncp
        if "PNCP" in n.fontes and n.valor_pncp is not None:
            existente.valor_pncp = n.valor_pncp
        # O Compras.gov.br é a fonte de valor e vigência; a mais completa preenche o que falta.
        existente.numero = existente.numero or n.numero
        existente.objeto = existente.objeto or n.objeto
        existente.orgao = existente.orgao or n.orgao
        existente.data_fim = existente.data_fim or n.data_fim
        existente.codigo_ug = existente.codigo_ug or n.codigo_ug
        if existente.valor_global is None:
            existente.valor_global = n.valor_global


def unir(
    compras: list[ContratoVigente],
    pncp_lista: list[ContratoVigente],
    conlicitacao: list[ContratoVigente] | None = None,
) -> list[ContratoVigente]:
    """Junta as fontes sem contar duas vezes o mesmo contrato.

    Chave: número de controle do PNCP, que Compras.gov.br e ConLicitação também trazem nos
    contratos publicados lá. Sem ele, vale número+ano com mesmo valor ou mesmo fim de vigência.
    """
    unidos = list(compras)
    _incorporar(unidos, pncp_lista)
    _incorporar(unidos, conlicitacao or [])
    return sorted(unidos, key=lambda c: (c.data_fim or "9999", c.orgao or ""))


def _contrato_conlicitacao(item: dict[str, Any]) -> ContratoVigente:
    return ContratoVigente(
        fontes={"ConLicitação"},
        orgao=item.get("orgao"),
        numero=_numero_conlicitacao(item),
        objeto=item.get("objeto"),
        data_inicio=item.get("vigencia_inicio"),
        data_fim=item.get("vigencia_fim"),
        valor_global=item.get("valor_contratado"),
        controle_pncp=item.get("contrato_pncp_id"),
        codigo_ug=str(item["uasg"]) if item.get("uasg") else None,
    )


def _numero_conlicitacao(item: dict[str, Any]) -> str | None:
    """'00037' vira '00037/2026' (ano da assinatura ou do início) para casar com as outras fontes."""
    numero = item.get("numero_contrato")
    if not numero:
        return None
    if "/" in str(numero):
        return str(numero)
    ano = (item.get("assinatura") or item.get("vigencia_inicio") or "")[:4]
    return f"{numero}/{ano}" if ano else str(numero)


async def _contratos_conlicitacao(cnpj: str) -> tuple[list[ContratoVigente], str | None]:
    """Tela Contratos do ConLicitação, com o login do servidor. Opcional: sem ele, segue sem."""
    try:
        from mcp_realmak.conlicitacao.format import resumir_contratos
        from mcp_realmak.conlicitacao.tools import get_site_client

        site = get_site_client()
        achados: list[ContratoVigente] = []
        for pagina in range(1, 6):
            dados = await site.buscar_contratos(cnpj=cnpj, pagina=pagina)
            itens = resumir_contratos(dados, cnpj)
            if not (dados.get("contratos") or []):
                break
            achados.extend(_contrato_conlicitacao(i) for i in itens)
            if len(dados.get("contratos") or []) < 20:
                break
        return achados, None
    except Exception as exc:
        logger.warning("ConLicitação indisponível para %s: %s", cnpj, type(exc).__name__)
        return [], f"{type(exc).__name__}: {exc}"[:200]


_UG_CACHE = TTLCache(ttl=VARREDURA_TTL_S, maxsize=256)
_SEM_CACHE = object()
_UG_EM_CURSO: dict[str, asyncio.Task[list[ContratoResumo]]] = {}


async def _ativos_da_ug(ug: str) -> list[ContratoResumo]:
    """Contratos ativos de uma UG no Contratos.gov.br, com a vigência já atualizada pelos aditivos."""
    guardado = _UG_CACHE.get(ug, _SEM_CACHE)
    if guardado is not _SEM_CACHE:
        return guardado

    async def buscar() -> list[ContratoResumo]:
        try:
            dados = await http_get(f"{CONTRATO_POR_UG_URL}/{ug}", timeout=90.0, max_retries=2)
        finally:
            _UG_EM_CURSO.pop(ug, None)
        lista = [_parse_contrato(i) for i in dados] if isinstance(dados, list) else []
        _UG_CACHE.set(ug, lista)
        return lista

    tarefa = _UG_EM_CURSO.get(ug)
    if tarefa is None:
        tarefa = _UG_EM_CURSO[ug] = asyncio.ensure_future(buscar())
    return await asyncio.shield(tarefa)


async def verificar_prorrogacoes(
    cnpj: str, contratos: list[ContratoVigente], *, orcamento_s: float = VERIFICACAO_ORCAMENTO_S
) -> int:
    """Confere no Contratos.gov.br os contratos que o Compras.gov.br dá por encerrados.

    O Compras.gov.br guarda a vigência original. A lista de ativos de cada UG do Contratos.gov.br
    traz a vigência com os aditivos: se o contrato está lá, foi prorrogado. Se não está, nada se
    conclui (a UG de origem pode ser outra), e ele continua na lista para confirmar.
    Devolve quantos ficaram sem checar (UG demorou além do orçamento; a próxima chamada usa o cache).
    """
    candidatos = [
        c for c in contratos if not c.vigente() and c.verificado is None and c.codigo_ug
    ]
    if not candidatos:
        return 0
    limite = asyncio.Semaphore(2)

    async def uma(ug: str) -> list[ContratoResumo]:
        async with limite:
            return await _ativos_da_ug(ug)

    tarefas = {ug: asyncio.ensure_future(uma(ug)) for ug in {c.codigo_ug for c in candidatos if c.codigo_ug}}
    await asyncio.wait(tarefas.values(), timeout=orcamento_s)
    hoje = date.today().isoformat()
    pendentes = 0
    for c in candidatos:
        tarefa = tarefas[c.codigo_ug or ""]
        if not tarefa.done() or tarefa.cancelled() or tarefa.exception() is not None:
            pendentes += 1
            continue
        chave = _numero_ano(c)
        achado = next(
            (
                a
                for a in tarefa.result()
                if apenas_digitos(a.fornecedor_cnpj_cpf or "") == cnpj
                and chave == _numero_ano(ContratoVigente(numero=a.numero, data_inicio=a.vigencia_inicio))
            ),
            None,
        )
        if achado and (achado.vigencia_fim or "")[:10] >= hoje:
            c.data_fim = (achado.vigencia_fim or "")[:10]
            valor = parse_brl_number(achado.valor_global)
            c.valor_global = valor if valor else c.valor_global
            c.fontes.add("Contratos.gov.br")
            c.verificado = "prorrogado"
        else:
            c.verificado = "nao_listado"
    return pendentes


async def _fornecedor(cnpj: str) -> tuple[str | None, bool | None]:
    try:
        res = await dados_abertos.consultar_fornecedor(cnpj=cnpj)
    except Exception as exc:
        logger.warning("Cadastro do fornecedor %s indisponível: %s", cnpj, exc)
        return None, None
    if not res.fornecedores:
        return None, None
    f = res.fornecedores[0]
    return f.nome_razao_social, f.habilitado_licitar


async def contratos_vigentes(
    cnpj: str, *, aguardar_s: float = 45.0, codigos_orgao: list[str] | None = None
) -> Resultado:
    """PNCP + varredura do Compras.gov.br. Espera a varredura até `aguardar_s`."""
    inicio = time.monotonic()
    # O cadastro vem antes da varredura: depois dela, a mesma API estaria em 429.
    razao, habilitado = await _fornecedor(cnpj)
    estado = await _iniciar_varredura(cnpj, codigos_orgao)  # segue em segundo plano
    (pncp_lista, pncp_erro), (conlic_lista, conlic_erro) = await asyncio.gather(
        _pncp_seguro(cnpj), _contratos_conlicitacao(cnpj)
    )
    restante = aguardar_s - (time.monotonic() - inicio)
    if estado.tarefa is not None and not estado.concluida and restante > 0:
        await asyncio.wait({estado.tarefa}, timeout=restante)
    compras = [_contrato_compras(r) for r in list(estado.registros)]
    unidos = unir(compras, pncp_lista, conlic_lista)
    pendentes = await verificar_prorrogacoes(cnpj, unidos)
    unidos.sort(key=lambda c: (c.data_fim or "9999", c.orgao or ""))
    return Resultado(
        cnpj=cnpj,
        razao_social=razao,
        habilitado=habilitado,
        contratos=unidos,
        verificacao_pendente=pendentes,
        pncp_ok=pncp_erro is None,
        pncp_erro=pncp_erro,
        varredura=estado,
        escopo_restrito=bool(codigos_orgao),
        conlicitacao_ok=conlic_erro is None,
        conlicitacao_erro=conlic_erro,
    )


async def _pncp_seguro(cnpj: str) -> tuple[list[ContratoVigente], str | None]:
    try:
        return await _contratos_pncp(cnpj), None
    except Exception as exc:
        logger.warning("PNCP indisponível para %s: %s", cnpj, exc)
        return [], f"{type(exc).__name__}: {exc}"[:200]
