"""Arquiva os bytes já baixados e imprime caminho e SHA-256 em JSON."""

import argparse
import hashlib
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def guardar(pasta, empresa, origem, nome):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", empresa):
        raise ValueError("use o alias minúsculo da empresa ou o CNPJ sem pontuação")
    if not pasta.is_dir() or not origem.is_file():
        raise ValueError("informe a pasta existente da licitação e o arquivo local baixado")
    nome = Path(nome.replace("\\", "/")).name
    nome = re.sub(r'[<>:"|?*\x00-\x1f]', "_", nome).strip(" .")
    if not nome or re.fullmatch(r"(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])", nome.split(".")[0]):
        raise ValueError("nome de arquivo inválido; informe um nome seguro com a extensão original")
    destino = pasta.resolve()
    for componente in ("documentos_empresa", empresa):
        destino = destino / componente
        if destino.is_symlink():
            raise ValueError("a pasta de destino não pode ser um link simbólico")
        destino.mkdir(exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=".original-", dir=destino) as temporaria:
        etapa = Path(temporaria) / "copia"
        etapa.mkdir()
        copia = etapa / nome
        shutil.copyfile(origem, copia)
        if not copia.stat().st_size:
            raise ValueError("arquivo vazio; confira o download")
        digest = sha256(copia)
        arquivo = destino / digest
        if not arquivo.exists():
            try:
                etapa.rename(arquivo)
            except OSError:
                if not arquivo.is_dir():
                    raise
        if arquivo.is_symlink():
            raise ValueError("o destino do original não pode ser um link simbólico")
        salvos = list(arquivo.iterdir())
        if len(salvos) != 1 or salvos[0].is_symlink() or not salvos[0].is_file() or sha256(salvos[0]) != digest:
            raise ValueError("arquivo existente não corresponde ao SHA-256; preserve-o e confira manualmente")
        return {"arquivo": str(salvos[0]), "sha256": digest}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pasta", type=Path)
    parser.add_argument("empresa")
    parser.add_argument("origem", type=Path)
    parser.add_argument("--nome")
    args = parser.parse_args()
    try:
        print(json.dumps(guardar(args.pasta, args.empresa, args.origem, args.nome or args.origem.name),
                         ensure_ascii=False))
    except (OSError, ValueError) as exc:
        print(f"Arquivamento pendente: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
