import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "plugins/realmak/skills/analisar-habilitacao/scripts"
CHAVE = {"empresa": "exemplo", "clausula": "Lote A / regra 2", "id": "at_0001", "tipo": "original"}


def chamar(db, acao, dados=None, numero=None):
    args = [sys.executable, str(SCRIPTS / "fila_documental.py"), str(db), acao]
    if numero is not None:
        args += ["--numero", str(numero)]
    return subprocess.run(args, input=json.dumps(dados), text=True, capture_output=True)



def guardar(tmp_path, nome, conteudo):
    temporario = tmp_path / nome
    temporario.write_bytes(conteudo)
    dados = json.loads(subprocess.check_output(
        [sys.executable, str(SCRIPTS / "guardar_original.py"), str(tmp_path), "exemplo", str(temporario)],
        text=True,
    ))
    dados["arquivo"] = Path(dados["arquivo"]).relative_to(tmp_path).as_posix()
    return dados


def test_retomada_depois_de_503_enfileira_a_via_emitida(tmp_path):
    db = tmp_path / "fila.sqlite"
    assert chamar(db, "adicionar", [CHAVE, CHAVE]).returncode == 0
    original = json.loads(chamar(db, "proximo").stdout)
    rota = {"via": "baixar_original", "estado": "ok", "resultado": "Cópia conferida; contém minuta"}
    resultado = {"estado": "salvo", "detalhe": "Minuta preservada", "tentativas": [rota],
                 "minuta": {"emissor_id": "ent-teste", "contrato_numero": "Contrato n. 0009/2027"}}
    resultado.update(guardar(tmp_path, "minuta.txt", b"Minuta ficticia"))
    assert chamar(db, "registrar", resultado, original["numero"]).returncode == 0

    def servico_simulado(sql, disponivel):
        assert "a.emissor_id = 'ent-teste'" in sql and "0*9" in sql and "2027" in sql
        if not disponivel:
            return {"estado": "transitorio", "detalhe": "HTTP 503 no serviço de consulta"}
        return {"estado": "reconciliado", "detalhe": "Minuta e versão assinada separadas",
                "linhas": [{"atestado_id": "at_0001", "situacao_documento": "minuta"},
                           {"atestado_id": "at_0002", "situacao_documento": "assinado"}],
                "truncado": False}

    versoes = json.loads(chamar(db, "proximo").stdout)
    assert chamar(db, "registrar", servico_simulado(versoes["sql"], False), versoes["numero"]).returncode == 0
    assert chamar(db, "fechar").returncode == 2
    retomado = json.loads(chamar(db, "proximo").stdout)
    assert retomado["numero"] == versoes["numero"]
    assert chamar(db, "registrar", servico_simulado(retomado["sql"], True), retomado["numero"]).returncode == 0

    assinado = json.loads(chamar(db, "proximo").stdout)
    assert (assinado["ident"], assinado["clausula"]) == ("at_0002", CHAVE["clausula"])
    assert chamar(db, "fechar").returncode == 2
    resultado = {"estado": "salvo", "detalhe": "Via emitida aberta", "tentativas": [rota]}
    resultado.update(guardar(tmp_path, "emitido.txt", b"Atestado emitido ficticio"))
    assert chamar(db, "registrar", resultado, assinado["numero"]).returncode == 0
    fechado = chamar(db, "fechar")
    assert fechado.returncode == 0
    assert len(json.loads(fechado.stdout)["itens"]) == 3


def test_fechamento_recusa_exigido_nao_executado_mesmo_sem_item_aberto(tmp_path):
    db = tmp_path / "fila.sqlite"
    chave = {**CHAVE, "id": "doc_outra", "material": False}
    assert chamar(db, "adicionar", [chave]).returncode == 0
    item = json.loads(chamar(db, "proximo").stdout)
    assert chamar(db, "registrar", {"estado": "descartado", "detalhe": "Prova de empresa distinta",
                                     "fundamento": "incompatibilidade_objetiva"},
                  item["numero"]).returncode == 0
    dossie = tmp_path / "dossie.json"
    documento = {
        "empresa": CHAVE["empresa"], "id": CHAVE["id"], "classe": "exigido",
        "vinculos": [{"clausula": CHAVE["clausula"]}],
        "etapas": {e: {"estado": "nao_executada", "detalhe": "Aguardou recuperação do serviço"}
                   for e in ("download", "leitura", "validacao")},
        "tentativas": [{"via": v, "estado": "nao_executada", "resultado": "Serviço indisponível"}
                       for v in ("buscar_identificador", "renovar_link")],
    }
    dossie.write_text(json.dumps({"documentos": [documento], "requisitos": [
        {"empresa": CHAVE["empresa"], "clausula": CHAVE["clausula"],
         "situacao": "pendente", "detalhe": "Original não tentado"}]}))
    resultado = subprocess.run([sys.executable, str(SCRIPTS / "conferir_dossie.py"),
                                str(tmp_path), str(dossie), "--fila", str(db)], capture_output=True, text=True)
    assert resultado.returncode == 2
    assert "documento exigido sem tentativa reconciliada" in resultado.stderr


def test_candidato_material_nao_pode_ser_descartado_so_pelo_indice(tmp_path):
    db = tmp_path / "fila.sqlite"
    assert chamar(db, "adicionar", [CHAVE]).returncode == 0
    item = json.loads(chamar(db, "proximo").stdout)
    descarte = {"estado": "descartado", "fundamento": "incompatibilidade_objetiva",
                "detalhe": "A equivalência do instrumento ótico ainda é incerta"}
    assert chamar(db, "registrar", descarte, item["numero"]).returncode == 2
    assert chamar(db, "adicionar", [{**CHAVE, "material": False}]).returncode == 0
    assert chamar(db, "registrar", descarte, item["numero"]).returncode == 2
    assert chamar(db, "fechar").returncode == 2


def test_salvo_exige_arquivo_e_hash_e_fechamento_nao_e_aceite(tmp_path):
    db = tmp_path / "fila.sqlite"
    assert chamar(db, "adicionar", [CHAVE, {**CHAVE, "id": "at_outro"}]).returncode == 0
    item = json.loads(chamar(db, "proximo").stdout)
    resultado = {"estado": "salvo", "detalhe": "Guardado", "tentativas": [
        {"via": "download", "estado": "ok", "resultado": "HTTP 200"}]}
    assert "arquivo relativo" in chamar(db, "registrar", resultado, item["numero"]).stderr
    copia = guardar(tmp_path, "original.txt", b"Emitido")
    assert chamar(db, "registrar", {**resultado, **copia, "sha256": "0"*64}, item["numero"]).returncode == 2
    caminho = tmp_path / copia["arquivo"]
    caminho.write_bytes(b"Alterado")
    assert "não corresponde" in chamar(db, "registrar", {**resultado, **copia}, item["numero"]).stderr
    caminho.write_bytes(b"Emitido")
    assert chamar(db, "registrar", {**resultado, **copia}, item["numero"]).returncode == 0
    outro = json.loads(chamar(db, "proximo").stdout)
    lacuna = {"estado": "tentativas_esgotadas", "detalhe": "Distribuidor não fornece mais a cópia",
              "tentativas": [{"via": via, "estado": "falhou", "resultado": "Original indisponível"}
                             for via in ("buscar_identificador", "renovar_link")]}
    assert chamar(db, "registrar", lacuna, outro["numero"]).returncode == 0
    final = chamar(db, "fechar")
    assert final.returncode == 0
    dados = json.loads(final.stdout)
    assert dados["encerramento_operacional"]
    assert dados["aceite_cobertura"] == "requer_revisao"
    assert [i["ident"] for i in dados["lacunas_documentais"]] == ["at_outro"]
