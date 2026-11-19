"""Localiza o resumo IA do ConLicitação, reaproveitando o que o CRM já baixou.

Uso: python3 resumo_conlicitacao.py <licitacao_id>
Contrato: realmak-crm/docs/superpowers/specs/2026-10-15-resumo-conlicitacao-na-pasta.md.
Ordem: arquivo do CRM -> banco (transitório) -> cópia do agente -> site.
`sem_resumo` encerra a busca sem rede. O fallback do site tem prazo total de 20 s;
falhas viram pendência, sem impedir a leitura do edital. O resumo é sugestão
externa, frequentemente parcial, e não evidência documental.
"""
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# O daemon passa PASTA_LICITACOES e NOME_AGENTE; o padrão é o caminho do acervo no container.
PASTA_LICITACOES = Path(os.environ.get("PASTA_LICITACOES", "/data/conlicitacao/licitacoes"))
NOME_AGENTE = os.environ.get("NOME_AGENTE", "analisador-edital")
CRM_DB_CONTAINER = "realmak-crm-postgres-1"
AVISO = ("Leitura por IA do ConLicitação, sem conhecimento estratégico da Realmak. "
         "Costuma vir incompleta: campo vazio significa não informado pelo resumo, "
         "não ausência no edital. Usar como sugestão e conferir no edital.")


def da_pasta(pasta: Path):
    arquivo = pasta / "resumo_conlicitacao.json"
    if not arquivo.exists():
        return None
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    return arquivo, dados, "pasta (CRM)"


def gravar_copia(pasta: Path, licitacao_id: int, resumo: dict | None, consultado_em: str | None, origem: str):
    dados: dict[str, Any] = {"licitacao_id": licitacao_id, "consultado_em": consultado_em,
             "situacao": "disponivel" if resumo else "sem_resumo", "aviso": AVISO,
             "resumo": resumo or None}
    arquivo = pasta / "agents" / NOME_AGENTE / "fontes" / "resumo_conlicitacao.json"
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    return arquivo, dados, origem


def do_banco_transitorio(pasta: Path, licitacao_id: int):
    sql = ("select json_build_object('resumo', licitacao_resumo, 'consultado_em', licitacao_resumo_consultado_em)"
           f" from crm_lead where conlicitacao_id = {int(licitacao_id)} and licitacao_resumo is not null"
           " order by licitacao_resumo_consultado_em desc nulls last limit 1")
    cmd = ["docker", "exec", CRM_DB_CONTAINER, "sh", "-c",
           'psql -U "${POSTGRES_USER:-odoo}" -d odoo -At -v ON_ERROR_STOP=1 -c "$0"', sql]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0 or not out.stdout.strip():
        return None
    linha = json.loads(out.stdout.strip().splitlines()[0])
    resumo = linha.get("resumo")
    if not isinstance(resumo, dict) or not resumo:
        return None
    consultado_em = linha.get("consultado_em")
    if consultado_em:
        consultado_em = datetime.fromisoformat(consultado_em).replace(tzinfo=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    return gravar_copia(pasta, licitacao_id, resumo, consultado_em, "banco do CRM (transitório)")


def baixado_antes(pasta: Path):
    arquivo = pasta / "agents" / NOME_AGENTE / "fontes" / "resumo_conlicitacao.json"
    if not arquivo.exists():
        return None
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    if dados.get("situacao") not in ("disponivel", "sem_resumo"):
        return None
    return arquivo, dados, "cópia do agente"


def do_site(pasta: Path, licitacao_id: int):
    sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "referencias" / "conlicitacao"))
    from cl import get_json
    try:
        status, data = get_json(
            f"/chatbots/bidding_chat/bidding_summary?conlicitacao_id={int(licitacao_id)}", prazo=20,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if status == 204:
        resumo = None
    elif status == 200 and isinstance(data, dict):
        resumo = data.get("summary")
        if resumo and not isinstance(resumo, dict):
            return None
    else:
        return None
    consultado_em = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    return gravar_copia(pasta, licitacao_id, resumo, consultado_em, "site (baixado pelo agente)")


def main():
    if len(sys.argv) < 2 or not sys.argv[1].isdigit():
        raise SystemExit("uso: resumo_conlicitacao.py <licitacao_id>")
    lid = int(sys.argv[1])
    pasta = PASTA_LICITACOES / str(lid)
    if not (pasta / "manifesto.json").exists():
        raise SystemExit(f"licitação {lid} sem manifesto")

    achado = (da_pasta(pasta) or do_banco_transitorio(pasta, lid)
              or baixado_antes(pasta) or do_site(pasta, lid))
    if achado is None:
        print(json.dumps({"licitacao_id": lid, "arquivo": None,
                          "pendencia": "falha ao consultar o resumo no ConLicitação; seguir pelo edital"}, ensure_ascii=False))
        return
    arquivo, dados, origem = achado
    saida = {"licitacao_id": lid, "arquivo": str(arquivo), "origem": origem,
             "situacao": dados["situacao"], "natureza": "sugestao_externa",
             "consultado_em": dados.get("consultado_em"), "campos": len(dados.get("resumo") or {})}
    if dados["situacao"] == "sem_resumo":
        saida["pendencia"] = "licitação sem resumo no ConLicitação"
    elif origem in ("site (baixado pelo agente)", "cópia do agente"):
        saida["aviso"] = "cópia transitória do agente; conferir no edital"
    print(json.dumps(saida, ensure_ascii=False))


if __name__ == "__main__":
    main()
