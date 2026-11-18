import json
import subprocess
import sys
from pathlib import Path

import pytest

duckdb = pytest.importorskip("duckdb")
SCRIPT = (Path(__file__).resolve().parents[1] / "plugins/realmak/skills/analisar-habilitacao"
          / "scripts/descobrir_atestados.py")


def cli(plano, *args):
    return subprocess.run([sys.executable, str(SCRIPT), *args, "--limite", "2"],
                          input=json.dumps(plano), text=True, capture_output=True, check=False)


def test_descoberta_antes_da_reconciliacao():
    plano = {
        "empresa": "empresa-exemplo",
        "termos": {
            "composto": ["central de tratamento de efluentes"],
            "amplo": ["efluente", "águas residuais", "aguas residuais"],
            "equipamento": ["bomba dosadora"],
            "servico": ["calibração"],
        },
        "paginas": [],
    }
    db = duckdb.connect()
    db.execute("""
        CREATE TABLE atestados(atestado_id VARCHAR, emissor_id VARCHAR, beneficiario_id VARCHAR,
            contrato_numero VARCHAR, objeto VARCHAR, area VARCHAR, situacao_documento VARCHAR);
        CREATE TABLE entidades(entidade_id VARCHAR, nome VARCHAR, ramo VARCHAR, superior_nome VARCHAR,
            nomes VARCHAR[]);
        CREATE TABLE atestado_servicos(atestado_id VARCHAR, descricao VARCHAR, trecho VARCHAR);
        INSERT INTO entidades VALUES ('org_x', 'Consórcio Norte', NULL, NULL, ['Núcleo de águas residuais']);
        INSERT INTO atestados VALUES
            ('at_a', NULL, 'emp', '1', 'central de tratamento de efluentes', NULL, 'assinado'),
            ('at_b', NULL, 'outra', '2', 'fornecimento de água para diluir efluente', NULL, 'assinado'),
            ('at_c', NULL, 'emp', '3', 'operação do sistema de recirculação de ÁGUAS RESIDUAIS', NULL, 'assinado'),
            ('at_d', NULL, 'emp', '4', 'instrumentação agrícola', NULL, 'assinado'),
            ('at_e', NULL, 'emp', '5', 'oficina móvel', NULL, 'assinado'),
            ('at_f', 'org_x', 'emp', '6', 'operação de unidade móvel', NULL, 'assinado');
        INSERT INTO atestado_servicos VALUES
            ('at_d', 'instalação de bomba dosadora', 'bomba dosadora'),
            ('at_d', 'bomba dosadora auxiliar', NULL),
            ('at_e', 'instrumentação', 'calibração anual');
    """)
    for recorte in plano["termos"]:
        apos = None
        while True:
            args = ["consulta", "--recorte", recorte]
            if apos:
                args.extend(["--apos", apos])
            consulta = cli(plano, *args)
            assert consulta.returncode == 0, consulta.stderr
            linhas = [{"atestado_id": row[0]} for row in db.execute(consulta.stdout).fetchall()]
            plano["paginas"].append({"recorte": recorte, "empresa": plano["empresa"], "apos": apos,
                                      "truncado": False, "linhas": linhas})
            if len(linhas) < 2:
                break
            apos = linhas[-1]["atestado_id"]

    resultado = cli(plano, "unir")
    assert resultado.returncode == 0, resultado.stderr
    assert json.loads(resultado.stdout)["candidatos"] == {
        "at_a": ["amplo", "composto"], "at_b": ["amplo"], "at_c": ["amplo"],
        "at_d": ["equipamento"], "at_e": ["servico"], "at_f": ["amplo"],
    }
    # Página cheia, mesmo sem truncamento, não encerra o recorte.
    plano["paginas"].pop(3)
    resultado = cli(plano, "unir")
    assert resultado.returncode == 1
    assert json.loads(resultado.stdout)["pendentes"] == {"amplo": "at_f"}
    plano["paginas"][0]["empresa"] = "outra"
    assert cli(plano, "unir").returncode == 2
