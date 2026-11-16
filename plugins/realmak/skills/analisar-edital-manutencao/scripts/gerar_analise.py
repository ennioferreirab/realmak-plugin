"""Gera as saídas da análise de manutenção a partir de um arquivo de dados JSON.

Uso:
    python gerar_analise.py dados.json pasta_de_saida
    python gerar_analise.py --modelo modelo.xlsx        (planilha em branco)

Saídas na pasta: analise-manutencao.xlsx (planilha), analise-manutencao.html (painel com abas
e filtros), analise-manutencao-relatorio.html (relatório para impressão),
analise-manutencao.pdf (se houver Chrome ou Chromium) e analise-manutencao.md.
Requer Python 3.9+ e openpyxl. O formato do JSON está em assets/exemplo-dados.json.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import calculo  # noqa: E402
import painel  # noqa: E402
import planilha  # noqa: E402
import relatorio  # noqa: E402

NAVEGADORES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome",
    "chromium",
    "chromium-browser",
    "chrome",
    "msedge",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]


def gerar_pdf(html, pdf):
    for nav in NAVEGADORES:
        exe = nav if Path(nav).exists() else shutil.which(nav)
        if not exe:
            continue
        try:
            subprocess.run(
                [
                    exe,
                    "--headless",
                    "--disable-gpu",
                    "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf}",
                    Path(html).resolve().as_uri(),
                ],
                check=True,
                capture_output=True,
                timeout=120,
            )
            return Path(pdf).exists()
        except (subprocess.SubprocessError, OSError):
            continue
    return False


def main(argv):
    if len(argv) == 3 and argv[1] == "--modelo":
        planilha.build(None, argv[2])
        print(f"modelo gravado em {argv[2]}")
        return 0
    if len(argv) != 3:
        print(__doc__)
        return 2
    dados = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    saida = Path(argv[2])
    saida.mkdir(parents=True, exist_ok=True)
    calc = calculo.calcular(dados)
    planilha.build(dados, saida / "analise-manutencao.xlsx")
    relatorio.build(
        dados, calc, saida / "analise-manutencao-relatorio.html", saida / "analise-manutencao.md"
    )
    painel.build(dados, calc, saida / "analise-manutencao.html")
    pdf = gerar_pdf(saida / "analise-manutencao-relatorio.html", saida / "analise-manutencao.pdf")
    n = calc["num"]
    alertas = [c for c in calc["checks"] if c[2] == "ALERTA"]
    print(
        f"carga {n['req']:.1f} h/mês · disponível {n['disp']:.1f} h/mês · cobertura {n['cob'] * 100:.1f}% · folga {n['folga']:.1f} h"
    )
    print("checks: " + ("OK" if not alertas else "; ".join(f"{a[0]} ({a[1]})" for a in alertas)))
    print(
        "pdf: "
        + (
            "gerado"
            if pdf
            else "não gerado (sem Chrome/Chromium); imprima o relatório HTML como PDF"
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
