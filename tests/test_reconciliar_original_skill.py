import hashlib
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins/realmak/skills/analisar-habilitacao/scripts"
HASH = hashlib.sha256(b"via ficticia confirmada").hexdigest()


def chamar(script, *args, dados=None):
    return subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, args)],
                          input=json.dumps(dados), text=True, capture_output=True)


def base(linhas=None):
    return {"empresa": "empresa-a", "id": "cert_teste", "provas": [],
            "paginas": [{"empresa": "empresa-a", "id": "cert_teste",
                         "linhas": [{"sha": HASH, "caminho": "pasta/certidao.pdf"}] if linhas is None else linhas}],
            "busca": [{"empresa": "empresa-a", "sha256": HASH, "tem_link_baixar": True}]}


def resolver(dados):
    r = chamar("reconciliar_original.py", "resolver", dados=dados)
    return r.returncode, json.loads(r.stdout)


def test_provas_vazias_preservam_link_da_busca_e_conferem_bytes(tmp_path):
    codigo, decisao = resolver(base())
    assert codigo == 0 and decisao == {"estado": "selecionado", "origem": "busca", "indice": 0, "sha256": HASH}
    copia = tmp_path / "recebido.pdf"
    copia.write_bytes(b"resposta indevida")
    assert chamar("reconciliar_original.py", "conferir", copia, HASH).returncode == 2
    copia.write_bytes(b"via ficticia confirmada")
    assert chamar("reconciliar_original.py", "conferir", copia, HASH).returncode == 0
    pasta = tmp_path / "licitacao"
    pasta.mkdir()
    salvo = json.loads(chamar("guardar_original.py", pasta, "empresa-a", copia).stdout)
    fila = pasta / "fila.sqlite"
    entrada = [{"empresa": "empresa-a", "clausula": "Regra 2", "id": "cert_teste", "tipo": "original"}]
    assert chamar("fila_documental.py", fila, "adicionar", dados=entrada).returncode == 0
    resultado = {"estado": "salvo", "detalhe": "Cópia arquivada", "arquivo": str(Path(salvo["arquivo"]).relative_to(pasta)),
                 "sha256": salvo["sha256"], "sha256_origem": "0"*64,
                 "tentativas": [{"via": "download", "estado": "ok", "resultado": "HTTP 200"}]}
    assert chamar("fila_documental.py", fila, "registrar", "--numero", 1, dados=resultado).returncode == 2
    resultado["sha256_origem"] = HASH
    assert chamar("fila_documental.py", fila, "registrar", "--numero", 1, dados=resultado).returncode == 0


def test_busca_por_nome_so_resolve_com_hash_e_empresa_corretos():
    dados = base()
    dados["busca"] = [{"empresa": "empresa-b", "sha256": HASH, "tem_link_baixar": True},
                     {"empresa": "empresa-a", "sha256": "0"*64, "tem_link_baixar": True}]
    codigo, decisao = resolver(dados)
    assert codigo == 2 and decisao["nome"] == "certidao.pdf"
    dados["busca"].append({"empresa": "empresa-a", "sha256": HASH, "tem_link_baixar": True})
    assert resolver(dados)[1]["indice"] == 2


def test_pagina_versoes_e_preserva_ambiguidade():
    linhas = [{"sha": f"{n:064x}"} for n in range(50)]
    dados = base(linhas)
    codigo, decisao = resolver(dados)
    assert codigo == 2 and linhas[-1]["sha"] in decisao["proxima_sql"]
    assert "rd.registro_id = 'cert_teste'" in decisao["proxima_sql"]
    dados["paginas"].append({"empresa": "empresa-a", "id": "cert_teste", "apos": linhas[-1]["sha"],
                            "linhas": [{"sha": HASH}]})
    assert len(resolver(dados)[1]["hashes"]) == 51
    dados["sha256_esperado"] = HASH
    assert resolver(dados)[0] == 0
    dados["paginas"][1]["empresa"] = "empresa-b"
    invalido = chamar("reconciliar_original.py", "resolver", dados=dados)
    assert invalido.returncode == 2 and "fora da empresa" in invalido.stderr
