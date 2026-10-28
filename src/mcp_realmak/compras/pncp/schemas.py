"""Pydantic schemas for the Compras feature."""

from __future__ import annotations

from pydantic import BaseModel


class Contratacao(BaseModel):
    """Contratação pública retornada pelo PNCP."""

    orgao_cnpj: str | None = None
    orgao_nome: str | None = None
    ano: int | None = None
    numero_sequencial: int | None = None
    numero_controle_pncp: str | None = None
    objeto: str | None = None
    modalidade_id: int | None = None
    modalidade_nome: str | None = None
    situacao_id: int | None = None
    situacao_nome: str | None = None
    valor_estimado: float | None = None
    valor_homologado: float | None = None
    data_publicacao: str | None = None
    data_abertura: str | None = None
    data_encerramento: str | None = None
    uf: str | None = None
    municipio: str | None = None
    unidade_nome: str | None = None
    esfera: str | None = None
    srp: bool | None = None
    link_pncp: str | None = None
    link_origem: str | None = None


class ContratacaoResultado(BaseModel):
    """Resultado paginado de busca de contratações.

    Com filtro de texto local, `total` conta só os itens que passaram no filtro
    e `total_api` guarda o total da consulta, para a paginação continuar.
    """

    total: int = 0
    total_api: int | None = None
    contratacoes: list[Contratacao] = []


class DocumentoPesquisa(BaseModel):
    """Edital, ata ou contrato vindo da busca textual do portal PNCP."""

    tipo: str | None = None
    titulo: str | None = None
    descricao: str | None = None
    numero_controle_pncp: str | None = None
    orgao_cnpj: str | None = None
    orgao_nome: str | None = None
    unidade_nome: str | None = None
    ano: int | None = None
    numero_sequencial: int | None = None
    municipio: str | None = None
    uf: str | None = None
    modalidade_nome: str | None = None
    situacao_nome: str | None = None
    data_publicacao: str | None = None
    data_inicio: str | None = None
    data_fim: str | None = None
    valor_global: float | None = None
    fornecedor_nome: str | None = None
    fornecedor_ni: str | None = None
    tem_resultado: bool | None = None
    link_pncp: str | None = None


class PesquisaResultado(BaseModel):
    """Resultado paginado da busca textual."""

    total: int = 0
    documentos: list[DocumentoPesquisa] = []


class ItemContratacao(BaseModel):
    """Item de uma contratação (edital)."""

    numero_item: int | None = None
    descricao: str | None = None
    material_ou_servico: str | None = None
    quantidade: float | None = None
    unidade_medida: str | None = None
    valor_unitario_estimado: float | None = None
    valor_total: float | None = None
    situacao: str | None = None
    criterio_julgamento: str | None = None
    beneficio: str | None = None
    tem_resultado: bool | None = None


class ResultadoItem(BaseModel):
    """Resultado (fornecedor homologado) de um item de contratação."""

    fornecedor_ni: str | None = None
    fornecedor_nome: str | None = None
    porte: str | None = None
    quantidade_homologada: float | None = None
    valor_unitario_homologado: float | None = None
    valor_total_homologado: float | None = None
    situacao: str | None = None
    data_resultado: str | None = None


class ArquivoContratacao(BaseModel):
    """Documento publicado em uma contratação (edital, TR, anexos)."""

    sequencial: int | None = None
    tipo: str | None = None
    titulo: str | None = None
    data_publicacao: str | None = None
    url: str | None = None


class EventoHistorico(BaseModel):
    """Evento do histórico de uma contratação (inclusão, retificação, exclusão)."""

    data: str | None = None
    tipo: str | None = None
    categoria: str | None = None
    documento: str | None = None
    item_numero: int | None = None
    justificativa: str | None = None
    usuario: str | None = None


class Contrato(BaseModel):
    """Contrato público."""

    orgao_cnpj: str | None = None
    orgao_nome: str | None = None
    numero_contrato: str | None = None
    objeto: str | None = None
    fornecedor_cnpj: str | None = None
    fornecedor_nome: str | None = None
    valor_inicial: float | None = None
    valor_final: float | None = None
    vigencia_inicio: str | None = None
    vigencia_fim: str | None = None
    data_publicacao: str | None = None
    situacao: str | None = None


class ContratoResultado(BaseModel):
    """Resultado paginado de busca de contratos."""

    total: int = 0
    contratos: list[Contrato] = []


class AtaRegistroPreco(BaseModel):
    """Ata de registro de preço."""

    orgao_cnpj: str | None = None
    orgao_nome: str | None = None
    numero_ata: str | None = None
    objeto: str | None = None
    fornecedor_cnpj: str | None = None
    fornecedor_nome: str | None = None
    valor_total: float | None = None
    vigencia_inicio: str | None = None
    vigencia_fim: str | None = None
    situacao: str | None = None


class AtaResultado(BaseModel):
    """Resultado paginado de busca de atas."""

    total: int = 0
    atas: list[AtaRegistroPreco] = []


class Fornecedor(BaseModel):
    """Fornecedor de contratações públicas."""

    cnpj: str | None = None
    razao_social: str | None = None
    nome_fantasia: str | None = None
    municipio: str | None = None
    uf: str | None = None
    porte: str | None = None
    data_abertura: str | None = None


class FornecedorResultado(BaseModel):
    """Resultado paginado de busca de fornecedores."""

    total: int = 0
    fornecedores: list[Fornecedor] = []


class OrgaoContratante(BaseModel):
    """Órgão contratante no PNCP."""

    cnpj: str | None = None
    razao_social: str | None = None
    esfera: str | None = None
    poder: str | None = None
    uf: str | None = None
    municipio: str | None = None


class OrgaoResultado(BaseModel):
    """Resultado paginado de busca de órgãos."""

    total: int = 0
    orgaos: list[OrgaoContratante] = []


class ItemPca(BaseModel):
    """Item do Plano de Contratações Anual."""

    numero_item: int | None = None
    descricao: str | None = None
    quantidade_estimada: float | None = None
    valor_unitario: float | None = None
    valor_total: float | None = None
    unidade_fornecimento: str | None = None
    categoria: str | None = None
    data_desejada: str | None = None


class Pca(BaseModel):
    """Plano de Contratações Anual."""

    orgao_cnpj: str | None = None
    orgao_nome: str | None = None
    ano: int | None = None
    unidade_nome: str | None = None
    id_pca: str | None = None
    data_publicacao: str | None = None
    itens: list[ItemPca] = []


class PcaResultado(BaseModel):
    """Resultado paginado de busca de PCAs."""

    total: int = 0
    pcas: list[Pca] = []


class InstrumentoCobranca(BaseModel):
    """Instrumento de cobrança (nota fiscal) vinculado a contrato."""

    cnpj_orgao: str | None = None
    ano_contrato: int | None = None
    numero_instrumento: str | None = None
    tipo_nome: str | None = None
    data_emissao: str | None = None
    objeto_contrato: str | None = None
    fornecedor_nome: str | None = None
    fornecedor_cnpj: str | None = None
    valor_nf: str | None = None
    chave_nfe: str | None = None


class InstrumentoCobrancaResultado(BaseModel):
    """Resultado paginado de busca de instrumentos de cobrança."""

    total: int = 0
    instrumentos: list[InstrumentoCobranca] = []
