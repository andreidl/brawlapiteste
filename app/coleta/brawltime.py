"""Fonte complementar: brawltime.ninja — só dados extras de carreira
(ano de criação da conta, recordes). API JSON pública (tRPC), sem HTML.
Falha aqui NUNCA derruba a consulta principal — retorna None.
"""
import json
import urllib.parse

import httpx

from app.coleta import cache
from app.coleta.brawlace import USER_AGENT, normalizar_tag

TTL_EXTRA_SEG: int = 24 * 3600  # dados quase estáticos


def coletar_extra(tag: str) -> dict | None:
    """{'conta_criada_em': 2018, 'record_level': 6, 'record_points': 22310} ou None."""
    tag_sem_hash: str = normalizar_tag(tag).lstrip("#")
    entrada: str = urllib.parse.quote(json.dumps({"json": tag_sem_hash}))
    url: str = f"https://brawltime.ninja/api/player.byTagExtra?input={entrada}"

    corpo: str | None = cache.obter(url, TTL_EXTRA_SEG)
    if corpo is None:
        try:
            resposta = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=10.0)
            if resposta.status_code != 200:
                return None
            corpo = resposta.text
            cache.salvar(url, corpo)
        except httpx.HTTPError:
            return None

    try:
        dados: dict = json.loads(corpo)["result"]["data"]["json"]
        return {
            "conta_criada_em": dados.get("accountCreationYear"),
            "record_level": dados.get("recordLevel"),
            "record_points": dados.get("recordPoints"),
        }
    except (KeyError, TypeError, json.JSONDecodeError):
        return None
