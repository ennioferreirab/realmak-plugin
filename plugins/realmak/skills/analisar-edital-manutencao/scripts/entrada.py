"""Valida a estrutura dos dados antes de calcular ou escrever as saídas."""

import re


def _lista(valor, caminho):
    if not isinstance(valor, list):
        raise ValueError(f"{caminho}: esperado uma lista.")


def _tamanho(valor, caminho, tamanho, *, minimo=False):
    _lista(valor, caminho)
    if (minimo and len(valor) < tamanho) or (not minimo and len(valor) != tamanho):
        esperado = f"ao menos {tamanho}" if minimo else f"{tamanho}"
        raise ValueError(f"{caminho}: esperado {esperado} campos; recebeu {len(valor)}.")


def validar(dados):
    if not isinstance(dados, dict):
        raise ValueError("dados: esperado um objeto JSON.")
    for campo in ("capa", "base_carga", "testes"):
        if not isinstance(dados.get(campo), dict):
            raise ValueError(f"{campo}: esperado um objeto.")
    for campo in ("titulo", "linha2", "linha3"):
        if not isinstance(dados["capa"].get(campo), str):
            raise ValueError(f"capa.{campo}: esperado texto.")
    for campo in ("conclusao", "escopo_na"):
        if not isinstance(dados.get(campo), str):
            raise ValueError(f"{campo}: esperado texto.")

    _tamanho(dados.get("conclusao_equipe"), "conclusao_equipe", 3)
    for i, valor in enumerate(dados["conclusao_equipe"]):
        if not isinstance(valor, str):
            raise ValueError(f"conclusao_equipe[{i}]: esperado texto.")
    _tamanho(dados["testes"].get("ciclo"), "testes.ciclo", 3, minimo=True)
    _tamanho(dados["testes"].get("sla"), "testes.sla", 5, minimo=True)
    for campo, tamanho in {
        "leitura_rapida": 2, "condicoes": 2, "riscos": 4, "decisoes": 2, "prazos": 3,
        "requisitos": 10, "escopo": 8, "pecas": 9, "premissas": 4, "equipe": 4,
        "pontos": 7, "documentos": 5, "nobreaks": 5, "geradores": 5, "kpis_extras": 2,
    }.items():
        linhas = dados.get(campo, []) if campo in ("nobreaks", "geradores", "kpis_extras") else dados.get(campo)
        _lista(linhas, campo)
        for i, linha in enumerate(linhas):
            _tamanho(linha, f"{campo}[{i}]", tamanho, minimo=campo not in ("leitura_rapida", "condicoes"))

    servico = dados.get("dados_servico")
    _lista(servico, "dados_servico")
    for i, linha in enumerate(servico):
        if not isinstance(linha, str):
            _tamanho(linha, f"dados_servico[{i}]", 3)

    inventario = dados.get("inventario", [])
    _lista(inventario, "inventario")
    for i, grupo in enumerate(inventario):
        caminho = f"inventario[{i}]"
        if not isinstance(grupo, dict) or not isinstance(grupo.get("categoria"), str):
            raise ValueError(f"{caminho}.categoria: esperado texto em um objeto de inventário.")
        linhas = grupo.get("linhas")
        _lista(linhas, f"{caminho}.linhas")
        for j, linha in enumerate(linhas):
            _tamanho(linha, f"{caminho}.linhas[{j}]", 5)


# Selo da conclusão (decisão de Ennio, 21/11/2026: a tela monta, o modelo só escreve dados). O selo e a cor só aceitam
# três rótulos; um texto longo no lugar (card 6613: "Viável com ressalvas. A execução cabe...") quebrava o cabeçalho do
# painel. O rótulo sai do texto e o texto inteiro vai para a justificativa, sem perder nada.
CONCLUSOES = ("Atende", "Atende com condições", "Não atende")


def _sem_acento(texto):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)).lower()


def rotulo_conclusao(texto):
    bruto = (texto or "").strip()
    for rotulo in CONCLUSOES:
        if bruto.lower() == rotulo.lower():
            return rotulo
    t = _sem_acento(bruto)
    if re.search(r"\bnao atende\b|\binviavel\b|\binexequivel\b|\bnao_atende\b|\bnao viavel\b", t):
        return "Não atende"
    if re.search(r"ressalva|condic|com_ressalvas|parcial", t):
        return "Atende com condições"
    if re.match(r"(viavel|atende|exequivel|sim)\b", t):
        return "Atende"
    return "Atende com condições"


def normalizar(dados):
    """Deixa `conclusao` num dos três rótulos; o texto original, se for mais que o rótulo, abre a justificativa."""
    original = (dados.get("conclusao") or "").strip()
    rotulo = rotulo_conclusao(original)
    dados["conclusao"] = rotulo
    if original and original != rotulo:
        justificativa = (dados.get("justificativa") or "").strip()
        if original not in justificativa:
            dados["justificativa"] = original + ("\n\n" + justificativa if justificativa else "")
    return dados

