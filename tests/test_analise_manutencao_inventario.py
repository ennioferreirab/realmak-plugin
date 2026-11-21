"""Regressões do gerador e do encaminhamento da pesquisa técnica."""

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

SKILLS = Path(__file__).resolve().parents[1] / "plugins/realmak/skills"
MANUTENCAO = SKILLS / "analisar-edital-manutencao"


def gerar(dados, tmp_path):
    entrada = tmp_path / "dados.json"
    entrada.write_text(json.dumps(dados), encoding="utf-8")
    resultado = subprocess.run(
        [sys.executable, str(MANUTENCAO / "scripts/gerar_analise.py"), str(entrada), str(tmp_path)],
        capture_output=True, text=True,
    )
    assert resultado.returncode == 0, resultado.stderr
    return tuple(
        (tmp_path / arquivo).read_text(encoding="utf-8")
        for arquivo in ("analise-manutencao.html", "analise-manutencao-relatorio.html", "analise-manutencao.md")
    )


@pytest.fixture
def exemplo():
    return json.loads((MANUTENCAO / "assets/exemplo-dados.json").read_text(encoding="utf-8"))


def dados_outro_objeto():
    # Mantém apenas a estrutura comum. O exemplo legado traz conteúdo textual do seu objeto.
    dados = {
        key: [] for key in (
            "condicoes", "dados_servico", "documentos", "escopo", "pecas",
            "pontos", "prazos", "premissas", "proximos_passos", "requisitos", "riscos", "decisoes",
            "leitura_rapida",
        )
    }
    dados.update({
        "capa": {"titulo": "Análise", "linha2": "Caso fictício", "linha3": ""},
        "conclusao": "Atende com condições",
        "justificativa": "Revisar inventário",
        "escopo_na": "",
        "conclusao_equipe": ["", "", ""],
        "base_carga": {},
        "equipe": [["Técnico", 1, 100, 10]],
        "testes": {"ciclo": ["Ciclo", 1, 2, ""], "sla": ["SLA", "", "", "Atende", ""]},
    })
    return dados


@pytest.mark.parametrize("com_inventario", [True, False])
def test_objeto_sem_potencia_eletrica_nao_herda_categorias(tmp_path, com_inventario):
    dados = dados_outro_objeto()
    if com_inventario:
        dados["inventario"] = [
            {"categoria": "Instrumentos óticos", "linhas": [[2, "Lupa", "5×", "Sala A", "TR item 1"]]},
            {"categoria": "Vazios", "linhas": []},
        ]
    painel, relatorio, markdown = gerar(dados, tmp_path)
    grupos = json.loads(re.search(r"const DADOS=(.*?);\n", painel).group(1))["inventarios"]
    assert [g["titulo"] for g in grupos] == (["Instrumentos óticos"] if com_inventario else [])
    for saida in (painel, relatorio, markdown):
        assert not re.search(r"nobreak|gerador|\bkVA\b|Vazios", saida, re.I)
        assert ("Instrumentos óticos" in saida) == com_inventario
        if com_inventario:
            assert "5×" in saida and "TR item 1" in saida


def test_inventario_legado_preserva_unidade_e_limite_documentado(exemplo, tmp_path):
    painel, relatorio, markdown = gerar(exemplo, tmp_path)
    for saida in (painel, relatorio, markdown):
        assert "Nobreaks" in saida and "Grupos geradores" in saida
        assert "Potência (kVA)" in saida
        assert f"{exemplo['limites']['nobreak']} kVA" in saida


def test_um_grupo_legado_sem_limite_nao_inventa_outro_grupo(tmp_path):
    dados = dados_outro_objeto()
    dados["geradores"] = [[1, 200, "Fabricante hipotético", "Sala A", "Faixa A"]]
    painel, relatorio, markdown = gerar(dados, tmp_path)
    for saida in (painel, relatorio, markdown):
        assert "Grupos geradores" in saida and "Potência (kVA)" in saida
        assert "Nobreaks" not in saida and "kVA ou mais" not in saida


def test_fluxo_textual_exige_descoberta_por_emissor_e_prova():
    cerebro = (SKILLS / "cerebro/SKILL.md").read_text(encoding="utf-8")
    habilidade = (SKILLS / "analisar-habilitacao/SKILL.md").read_text(encoding="utf-8")
    for requisito in (
        "classes de emissores", "ambientes de operação", "atestados.emissor_id", "entidades.entidade_id",
        "nome, sigla e variantes", "beneficiária em uma junção separada", "Uma consulta ampla é triagem",
        "IDs reais do atestado", "cerebro_provas", "minuta", "falha for recuperável", "extração pendente",
    ):
        assert requisito in cerebro
    assert "pesquisa de atestados por emissor e ambiente da skill `cerebro`" in habilidade


@pytest.mark.parametrize(("campo", "valor", "erro"), [
    ("leitura_rapida", [["só um"]], "leitura_rapida[0]: esperado 2 campos"),
    ("conclusao_equipe", ["só um", "dois"], "conclusao_equipe: esperado 3 campos"),
    ("condicoes", [["a", "b", "c"]], "condicoes[0]: esperado 2 campos"),
    ("testes", {"ciclo": ["sem capacidade"], "sla": []}, "testes.ciclo: esperado ao menos 3 campos"),
    ("inventario", [{"categoria": "Instrumentos", "linhas": [[1, "um"]]}],
     "inventario[0].linhas[0]: esperado 5 campos"),
])
def test_rejeita_cardinalidade_invalidada_sem_escrever(tmp_path, campo, valor, erro):
    dados = dados_outro_objeto()
    dados[campo] = valor
    entrada = tmp_path / "dados.json"
    entrada.write_text(json.dumps(dados), encoding="utf-8")
    destino = tmp_path / "saidas"
    resultado = subprocess.run(
        [sys.executable, str(MANUTENCAO / "scripts/gerar_analise.py"), str(entrada), str(destino)],
        capture_output=True, text=True,
    )
    assert resultado.returncode == 2
    assert erro in resultado.stderr
    assert not destino.exists()


def test_relatorio_mantem_titulo_e_total_junto_as_linhas(exemplo, tmp_path):
    _, relatorio, _ = gerar(exemplo, tmp_path)
    blocos = re.findall(r'<tbody class="linhas-juntas">(.*?)</tbody>', relatorio, re.S)
    assert any('class="grupo"' in bloco and bloco.count("<tr") > 1 for bloco in blocos)
    assert any('class="total"' in bloco and bloco.count("<tr") > 1 for bloco in blocos)
    assert not re.search(r'<tbody[^>]*><tr class="total">', relatorio)


def test_cobertura_independente_e_destinacao_da_prova():
    cerebro = (SKILLS / "cerebro/SKILL.md").read_text(encoding="utf-8")
    assert "sem exigir correspondência de emissor" in cerebro
    assert "Dê uma destinação a cada linha candidata pelo ID real" in cerebro

    candidatos = [
        {"id": "ficticio-1", "familia": "microscopia", "emissor": "editora"},
        {"id": "ficticio-2", "familia": "pesagem", "emissor": "instituto"},
    ]
    por_familia = [c["id"] for c in candidatos if c["familia"] == "microscopia"]
    assert por_familia == ["ficticio-1"]


def test_prova_fiscal_mais_recente_precisa_ser_aplicavel():
    cerebro = (SKILLS / "cerebro/SKILL.md").read_text(encoding="utf-8")
    for regra in ("CNPJ participante", "emissão mais recente", "distribuidor competente",
                  "vigência na sessão", "confirmação ao vivo no SICAF"):
        assert regra in cerebro
    certidoes = [
        ("2026-04-01", "distribuidor A", "2026-06-01"),
        ("2026-05-01", "distribuidor B", "2026-08-01"),
        ("2026-03-01", "distribuidor A", "2026-05-01"),
    ]
    sessao = "2026-05-15"
    aplicaveis = [c for c in certidoes if c[1] == "distribuidor A" and c[0] <= sessao <= c[2]]
    assert max(aplicaveis) == certidoes[0]


def test_equivalencia_material_e_atestado_emitido_antes_do_marco():
    habilidade = (SKILLS / "analisar-habilitacao/SKILL.md").read_text(encoding="utf-8")
    assert "Equivalência técnica material ainda não resolvida fica **Técnico decide**" in habilidade
    assert "antes do marco exigido e o contrato já encerrou" in habilidade
    assert "avaliar solicitar nova via" in habilidade or "avalie solicitar nova via" in habilidade


def test_conclusao_longa_vira_rotulo_e_cabecalho_aguenta_texto_longo(exemplo, tmp_path):
    # Card 6613 (21/11/2026): o modelo pôs a conclusão inteira no selo e o cabeçalho do painel colapsou.
    longa = "Viável com ressalvas. A execução cabe no campus único com cerca de 12 técnicos, " * 6
    exemplo["conclusao"] = longa
    exemplo["pilulas"] = ["PE 108/2026 · UESC", "SEI 073.5748.2024.0033819-56", "R$ 1.047.149,16 / 12 meses"]
    painel, relatorio, md = gerar(exemplo, tmp_path)
    dados = json.loads(re.search(r"const DADOS=(.*?);\n", painel, re.S).group(1))
    assert dados["D"]["conclusao"] == "Atende com condições"
    assert dados["D"]["justificativa"].startswith(longa.strip())
    assert ".topo{flex-wrap:nowrap}" not in painel
    assert ".pilulas{flex:1 1 100%" in painel and "text-overflow:ellipsis" in painel and "max-height:45vh" in painel
    assert "Atende com condições" in relatorio
