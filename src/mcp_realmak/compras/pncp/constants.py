"""Constants for the PNCP (Portal Nacional de Contratações Públicas) feature.

API docs: https://pncp.gov.br/api/consulta/swagger-ui/index.html
OpenAPI spec: https://pncp.gov.br/api/consulta/v3/api-docs
"""

# API base URL
PNCP_API_BASE = "https://pncp.gov.br/api/consulta/v1"

# Endpoints (verified against OpenAPI spec)
CONTRATACOES_URL = f"{PNCP_API_BASE}/contratacoes/publicacao"
CONTRATACOES_PROPOSTA_URL = f"{PNCP_API_BASE}/contratacoes/proposta"
CONTRATACOES_ATUALIZACAO_URL = f"{PNCP_API_BASE}/contratacoes/atualizacao"
CONTRATOS_URL = f"{PNCP_API_BASE}/contratos"
CONTRATOS_ATUALIZACAO_URL = f"{PNCP_API_BASE}/contratos/atualizacao"
ATAS_URL = f"{PNCP_API_BASE}/atas"
ATAS_ATUALIZACAO_URL = f"{PNCP_API_BASE}/atas/atualizacao"
FORNECEDORES_URL = f"{PNCP_API_BASE}/fornecedores"
ORGAOS_URL = "https://pncp.gov.br/api/pncp/v1/orgaos"
CONTRATACAO_DETALHE_URL = f"{PNCP_API_BASE}/orgaos"
PCA_URL = f"{PNCP_API_BASE}/pca"
INSTRUMENTOS_COBRANCA_URL = f"{PNCP_API_BASE}/instrumentoscobranca/inclusao"

# Busca do portal (texto livre). Não tem OpenAPI: os parâmetros vêm do código
# do portal pncp.gov.br/app (buildCurrentQueryParams) e de testes ao vivo.
SEARCH_URL = "https://pncp.gov.br/api/search/"
PORTAL_URL = "https://pncp.gov.br/app"
MAX_PAGE_SIZE_SEARCH = 50
SEARCH_MAX_RETRIES = 8

# Status aceitos pela busca, por tipo de documento. Valor fora da lista é
# ignorado em silêncio pela API (volta tudo), por isso validamos antes.
SEARCH_STATUS: dict[str, dict[str, str]] = {
    "edital": {
        "recebendo_proposta": "A receber/recebendo propostas",
        "propostas_encerradas": "Em julgamento/propostas encerradas",
        "todos": "Todos",
    },
    "ata": {"vigente": "Vigentes", "nao_vigente": "Não vigentes", "todos": "Todos"},
    "contrato": {"vigente": "Vigentes", "nao_vigente": "Não vigentes", "todos": "Todos"},
}
SEARCH_STATUS_PADRAO: dict[str, str] = {
    "edital": "recebendo_proposta",
    "ata": "vigente",
    "contrato": "vigente",
}

# Arquivos vêm com o host interno da API (a porta muda a cada resposta, ex.:
# :41377, :41217); este é o caminho público equivalente, que baixa o arquivo.
ARQUIVO_URL_INTERNA_RE = r"^https://pncp\.gov\.br:\d+/pncp-api/v1"
ARQUIVO_URL_PUBLICA = "https://pncp.gov.br/api/pncp/v1"

# Paginação
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE_CONTRATACOES = 50  # max for /contratacoes/publicacao
MAX_PAGE_SIZE_CONTRATOS = 500  # max for /contratos and /atas

# Limite de período (dias)
MAX_DATE_RANGE_DAYS = 365

# Modalidades de contratação — códigos reais da API PNCP
# Fonte: https://pncp.gov.br/api/consulta/v1/modalidades
MODALIDADES: dict[int, str] = {
    1: "Leilão - Eletrônico",
    2: "Diálogo Competitivo",
    3: "Concurso",
    4: "Concorrência - Eletrônica",
    5: "Concorrência - Presencial",
    6: "Pregão - Eletrônico",
    7: "Pregão - Presencial",
    8: "Dispensa",
    9: "Inexigibilidade",
    10: "Manifestação de Interesse",
    11: "Pré-qualificação",
    12: "Credenciamento",
    13: "Leilão - Presencial",
    14: "Inaplicabilidade da Licitação",
    15: "Chamada Pública",
    16: "Concorrência - Eletrônica Internacional",
    17: "Concorrência - Presencial Internacional",
    18: "Pregão - Eletrônico Internacional",
    19: "Pregão - Presencial Internacional",
}

# Esferas (orgaoEntidade.esferaId)
ESFERAS: dict[str, str] = {
    "F": "Federal",
    "E": "Estadual",
    "M": "Municipal",
    "D": "Distrital",
    "N": "Não se aplica",
}

# Modos de disputa
MODOS_DISPUTA: dict[int, str] = {
    1: "Aberto",
    2: "Fechado",
    3: "Aberto-Fechado",
    4: "Dispensa Com Disputa",
    5: "Não se aplica",
}
