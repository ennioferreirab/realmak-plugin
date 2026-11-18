"""Cliente interno do visualizador do Brain. O conversor recebe só os bytes e a extensão."""

from __future__ import annotations

import asyncio

import httpx

EXTENSOES = {".doc", ".docx", ".xls", ".xlsx"}
MAX_ENTRADA = 16 * 1024 * 1024
MAX_PDF = 24 * 1024 * 1024
PRAZO_S = 85
_vaga = asyncio.Semaphore(1)


class ErroPrevia(Exception):
    def __init__(self, status: int, mensagem: str) -> None:
        super().__init__(mensagem)
        self.status = status


async def _ler_limitado(resp: httpx.Response, limite: int, erro: ErroPrevia) -> bytes:
    tamanho = resp.headers.get("content-length", "")
    if tamanho.isdecimal() and int(tamanho) > limite:
        raise erro
    partes = bytearray()
    async for parte in resp.aiter_bytes(chunk_size=64 * 1024):
        if len(partes) + len(parte) > limite:
            raise erro
        partes.extend(parte)
    return bytes(partes)


async def converter(url: str, ext: str, origem: httpx.Response) -> bytes:
    if _vaga.locked():
        raise ErroPrevia(503, "O visualizador está ocupado. Tente de novo ou use Baixar arquivo.")
    try:
        async with _vaga, asyncio.timeout(PRAZO_S):
            documento = await _ler_limitado(
                origem, MAX_ENTRADA, ErroPrevia(413, "O arquivo excede 16 MiB. Use Baixar arquivo.")
            )
            async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=70) as cliente:
                async with cliente.stream(
                    "POST", f"{url}/pdf", params={"ext": ext.lstrip(".")}, content=documento,
                    headers={"Content-Type": "application/octet-stream", "Accept-Encoding": "identity"},
                ) as resp:
                    if resp.status_code in (400, 413, 422):
                        raise ErroPrevia(422, "Este arquivo não pôde ser visualizado. Use Baixar arquivo.")
                    if resp.status_code == 504:
                        raise TimeoutError
                    if resp.status_code != 200 or resp.headers.get("content-type", "").split(";")[0] != "application/pdf":
                        raise ErroPrevia(502, "O visualizador não retornou um PDF. Use Baixar arquivo.")
                    pdf = await _ler_limitado(
                        resp, MAX_PDF, ErroPrevia(422, "A prévia excede 24 MiB. Use Baixar arquivo.")
                    )
                    if not pdf.startswith(b"%PDF-"):
                        raise ErroPrevia(502, "O visualizador não retornou um PDF válido. Use Baixar arquivo.")
                    return pdf
    except (TimeoutError, httpx.TimeoutException):
        raise ErroPrevia(504, "O tempo da prévia se esgotou. Tente de novo ou use Baixar arquivo.") from None
    except (httpx.HTTPError, httpx.InvalidURL):
        raise ErroPrevia(502, "O visualizador está indisponível. Use Baixar arquivo.") from None
