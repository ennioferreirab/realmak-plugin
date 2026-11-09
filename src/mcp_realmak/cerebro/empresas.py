"""Descoberta de permissões por empresa, sem conteúdo e com falha fechada.

Cada resultado definitivo (200/403) tem TTL próprio. Falhas nunca substituem
uma negativa por uma liberação, nem são armazenadas. O cache de identidade
usa apenas hashes de e-mail/token; nenhuma chave aparece em diagnósticos.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass
from typing import Literal

import httpx
from fastmcp.server.auth import AccessToken

from ..config import BRAINS_EMPRESAS, EMPRESAS, NOMES_EMPRESAS, Settings, load_settings
from .client import GaleedApiError, GaleedClient

Empresa = Literal["realmak", "aforca", "nortfort", "una", "sublime"]
EMPRESA_DESC = "Empresa cujo cérebro consultar. Padrão realmak. Veja cerebro_empresas."


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True)
class EmpresaLiberada:
    empresa: str
    nivel: str
    areas: tuple[str, ...]
    registros: bool

    def publico(self) -> dict:
        result = {"empresa": self.empresa, "nome": NOMES_EMPRESAS[self.empresa], "nivel": self.nivel, "registros": self.registros}
        if self.nivel == "parcial":
            result["areas"] = list(self.areas)
        return result


@dataclass
class Descoberta:
    empresas: list[EmpresaLiberada]
    indisponiveis: list[str]
    chave_recusada: bool = False

    def publico(self) -> dict:
        ids = [e.empresa for e in self.empresas]
        padrao = "realmak" if "realmak" in ids else ids[0] if len(ids) == 1 else None
        return {"empresas": [e.publico() for e in self.empresas], "indisponiveis": self.indisponiveis, "padrao": padrao}


class Empresas:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self.transport = transport
        self._brains: dict[str, str] = {}
        self._cache: dict[str, dict[str, tuple[float, EmpresaLiberada | None]]] = {}

    def client(self, token: str, email: str = "") -> GaleedClient:
        return GaleedClient(self.settings.galeed_api_url, token, self.settings.galeed_timeout_s, self.transport, email)

    async def brain_da_empresa(self, empresa: str) -> str:
        if empresa not in self._brains:
            data = await self.client(self.settings.service_keys[empresa]).acesso()
            brain = data.get("brain") if isinstance(data, dict) else None
            if not isinstance(brain, str) or brain != BRAINS_EMPRESAS[empresa]:
                raise GaleedApiError(502, "Resposta de acesso inválida")
            self._brains[empresa] = brain
        return self._brains[empresa]

    @staticmethod
    def _liberada(empresa: str, data: object) -> EmpresaLiberada:
        if not isinstance(data, dict) or data.get("nivel") not in ("total", "parcial") or not isinstance(data.get("brain"), str):
            raise GaleedApiError(502, "Resposta de acesso inválida")
        if data["brain"] != BRAINS_EMPRESAS[empresa]:
            raise GaleedApiError(502, "Chave configurada para outro cérebro")
        areas = data.get("areas")
        if not isinstance(areas, list) or not all(isinstance(a, str) for a in areas) or type(data.get("registros")) is not bool:
            raise GaleedApiError(502, "Resposta de acesso inválida")
        return EmpresaLiberada(empresa, data["nivel"], tuple(areas), data["registros"])

    def invalidar(self, access: AccessToken, empresa: str) -> None:
        email = (access.claims or {}).get("email")
        self._cache.get(_hash(email if email else access.token), {}).pop(empresa, None)

    async def descobrir(self, access: AccessToken) -> Descoberta:
        email = (access.claims or {}).get("email")
        identity = _hash(email if email else access.token)
        now = time.monotonic()
        entries = self._cache.get(identity, {})
        if email:
            async def consultar(empresa: str):
                hit = entries.get(empresa)
                if hit and hit[0] > now:
                    return empresa, hit[1], 200 if hit[1] else 403
                try:
                    data = await self.client(self.settings.service_keys[empresa], email).acesso()
                    return empresa, self._liberada(empresa, data), 200
                except GaleedApiError as exc:
                    return empresa, None, exc.status
            results = await asyncio.gather(*(consultar(e) for e in EMPRESAS if e in self.settings.service_keys))
        else:
            hit = next((v for v in entries.values() if v[0] > now and v[1]), None)
            if hit:
                return Descoberta([hit[1]], [])
            try:
                data = await self.client(access.token).acesso()
                if not isinstance(data, dict) or not isinstance(data.get("brain"), str):
                    raise GaleedApiError(502, "Resposta de acesso inválida")
                brains = await asyncio.gather(*(self.brain_da_empresa(e) for e in self.settings.service_keys), return_exceptions=True)
                matched = [e for e, b in zip(self.settings.service_keys, brains, strict=True) if b == data["brain"]]
                if len(matched) != 1:
                    # Não adivinhar a empresa de uma chave, inclusive quando duas configurações usam o mesmo brain.
                    return Descoberta([], list(self.settings.service_keys))
                empresa = matched[0]
                results = [(empresa, self._liberada(empresa, data), 200)]
            except GaleedApiError:
                return Descoberta([], list(self.settings.service_keys))
        liberadas, indisponiveis = [], []
        recusada = False
        for empresa, resultado, status in results:
            if status in (200, 403):
                hit = entries.get(empresa)
                if not hit or hit[0] <= now:
                    entries[empresa] = (now + self.settings.token_cache_ttl_s, resultado)
                if resultado:
                    liberadas.append(resultado)
            else:
                indisponiveis.append(empresa)
                recusada |= status == 401
                entries.pop(empresa, None)
        if len(self._cache) >= 2048 and identity not in self._cache:
            self._cache.clear()
        if entries:
            self._cache[identity] = entries
        return Descoberta(liberadas, indisponiveis, recusada)

    async def empresas_liberadas(self, access: AccessToken) -> list[EmpresaLiberada]:
        return (await self.descobrir(access)).empresas


_instances: dict[str, Empresas] = {}


def get_empresas(settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None) -> Empresas:
    settings = settings or load_settings()
    key = _hash(repr((settings.galeed_api_url, sorted(settings.service_keys.items()), settings.token_cache_ttl_s, settings.galeed_timeout_s, id(transport))))
    if key not in _instances:
        _instances[key] = Empresas(settings, transport)
    return _instances[key]


async def empresas_liberadas(access: AccessToken) -> list[EmpresaLiberada]:
    return await get_empresas().empresas_liberadas(access)
