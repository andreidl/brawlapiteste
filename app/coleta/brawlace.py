"""Scraper do brawlace.com — fonte única de dados (ver CLAUDE.md §3).

Toda função de parsing levanta ErroParsing com o nome do campo quando o layout
do site mudar — nunca retorna dado parcial silenciosamente.
"""
import re
import time

import httpx
from bs4 import BeautifulSoup, Tag

from app.coleta import cache

BASE_URL: str = "https://brawlace.com"
USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
TTL_PERFIL_SEG: int = 600        # 10 min
TTL_META_SEG: int = 6 * 3600     # 6 h
TTL_EVENTOS_SEG: int = 3600      # 1 h
_INTERVALO_MIN_SEG: float = 1.0  # máx 1 req/s (CLAUDE.md §3.5)

_ultima_requisicao: float = 0.0


class TagInvalida(Exception):
    """Tag não existe no brawlace (página 404)."""


class ErroColeta(Exception):
    """Falha de rede/HTTP ao buscar a página."""


class ErroParsing(Exception):
    """O HTML não tem a estrutura esperada — provável mudança de layout."""


def normalizar_tag(tag: str) -> str:
    """'299pgglql' / '#299pgglql' → '#299PGGLQL'. Levanta TagInvalida se vazia."""
    limpa: str = tag.strip().lstrip("#").upper()
    if not re.fullmatch(r"[0-9A-Z]{3,15}", limpa):
        raise TagInvalida(f"Tag inválida: {tag!r}")
    return "#" + limpa


def _baixar(url: str, ttl_segundos: int) -> str:
    """GET com cache em disco, User-Agent obrigatório e rate limit de 1 req/s."""
    global _ultima_requisicao
    cacheado: str | None = cache.obter(url, ttl_segundos)
    if cacheado is not None:
        return cacheado

    espera: float = _INTERVALO_MIN_SEG - (time.time() - _ultima_requisicao)
    if espera > 0:
        time.sleep(espera)
    try:
        resposta = httpx.get(
            url, headers={"User-Agent": USER_AGENT}, timeout=20.0, follow_redirects=True
        )
    except httpx.HTTPError as erro:
        raise ErroColeta(f"Falha de rede ao buscar {url}: {erro}") from erro
    finally:
        _ultima_requisicao = time.time()

    if resposta.status_code != 200:
        raise ErroColeta(f"HTTP {resposta.status_code} ao buscar {url}")
    cache.salvar(url, resposta.text)
    return resposta.text


def coletar_perfil(tag: str) -> dict:
    """Baixa e parseia o perfil completo do jogador."""
    tag_norm: str = normalizar_tag(tag)
    url: str = f"{BASE_URL}/players/{tag_norm.replace('#', '%23')}"
    html: str = _baixar(url, TTL_PERFIL_SEG)
    return parsear_perfil(html, tag_norm)


# ---------------------------------------------------------------------------
# Parsing (funções puras — testáveis com fixtures offline)
# ---------------------------------------------------------------------------

def parsear_perfil(html: str, tag: str) -> dict:
    if "404 Page Not Found" in html[:4000] or "404 Page Not Found" in html:
        raise TagInvalida(f"Jogador {tag} não encontrado no brawlace")
    soup = BeautifulSoup(html, "lxml")
    return {
        "tag": tag,
        "nick": _parsear_nick(soup),
        "clube": _parsear_clube(soup),
        "stats": _parsear_stats(soup),
        "brawlers": _parsear_brawlers(soup),
        "batalhas": _parsear_batalhas(soup, tag),
        "grafico_trofeus": _parsear_grafico_trofeus(html),
    }


def coletar_meta() -> dict:
    """Meta global diário do brawlace: ranking de brawlers por modo."""
    html: str = _baixar(f"{BASE_URL}/meta", TTL_META_SEG)
    return parsear_meta(html)


def coletar_eventos() -> list[dict]:
    """Eventos ativos (modo + mapa) do brawlace."""
    html: str = _baixar(f"{BASE_URL}/events", TTL_EVENTOS_SEG)
    return parsear_eventos(html)


def parsear_meta(html: str) -> dict:
    """{'data': 'YYYY-MM-DD hh:mm:ss', 'modos': {'HOT ZONE': [{posicao, brawler,
    star_player, star_player_pct}, ...]}} — todas as tabelas vêm num único GET,
    em divs id='gameModeData<modoCamelCase>'."""
    soup = BeautifulSoup(html, "lxml")

    select_data = soup.find("select", id="metaDate") or soup.find("select")
    data: str | None = None
    if isinstance(select_data, Tag):
        opcao = select_data.find("option")
        if opcao:
            data = opcao.get_text(strip=True)

    modos: dict[str, list[dict]] = {}
    for div in soup.find_all("div", id=re.compile(r"^gameModeData")):
        titulo = div.find("h3")
        if titulo is None:
            continue
        nome_modo: str = titulo.get_text(" ", strip=True)
        linhas: list[dict] = []
        tabela = div.find("table")
        if not isinstance(tabela, Tag):
            continue
        corpo = tabela.find("tbody")
        if not isinstance(corpo, Tag):
            continue
        for tr in corpo.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue
            pct_texto: str = tds[3].get_text(strip=True).replace("%", "").strip()
            try:
                pct = float(pct_texto)
            except ValueError:
                raise ErroParsing(f"meta {nome_modo}: pct inválido {pct_texto!r}")
            linhas.append({
                "posicao": _numero(tds[0].get_text(strip=True)),
                "brawler": tds[1].get_text(" ", strip=True),
                "star_player": _numero(tds[2].get_text(strip=True)),
                "star_player_pct": pct,
            })
        if linhas:
            modos[nome_modo] = linhas
    if not modos:
        raise ErroParsing("meta: nenhuma tabela gameModeData encontrada")
    return {"data": data, "modos": modos}


def parsear_eventos(html: str) -> list[dict]:
    """Eventos ATIVOS: [{'modo': 'BRAWL BALL', 'mapa': 'Backyard Bowl',
    'inicio': ..., 'fim': ...}] — aba id='nav-active-events'."""
    soup = BeautifulSoup(html, "lxml")
    aba = soup.find("div", id="nav-active-events")
    if not isinstance(aba, Tag):
        raise ErroParsing("eventos: aba nav-active-events não encontrada")
    eventos: list[dict] = []
    for tr in aba.select("tbody tr"):
        tds = tr.find_all("td")
        if len(tds) < 6:
            continue
        mapa_img = tds[2].find("img", attrs={"data-map-name": True})
        tempos = tr.find_all("time")
        eventos.append({
            "modo": tds[1].get_text(" ", strip=True),
            "mapa": str(mapa_img.get("data-map-name")) if mapa_img else tds[2].get_text(" ", strip=True),
            "inicio": str(tempos[0].get("datetime")) if len(tempos) > 0 else None,
            "fim": str(tempos[1].get("datetime")) if len(tempos) > 1 else None,
        })
    if not eventos:
        raise ErroParsing("eventos: nenhuma linha de evento ativo encontrada")
    return eventos


_RE_GRAFICO = re.compile(
    r"profile-line-chart.*?\"data\":\[([\d,]+)\]", re.S
)


def _parsear_grafico_trofeus(html: str) -> list[int]:
    """Troféus totais nas últimas N partidas registradas pelo brawlace
    (gráfico Chart.js embutido na página; cresce conforme o site acumula).
    Campo opcional — lista vazia se o gráfico não existir.
    """
    m = _RE_GRAFICO.search(html)
    if not m:
        return []
    return [int(v) for v in m.group(1).split(",") if v]


def _parsear_nick(soup: BeautifulSoup) -> str:
    icone = soup.find("img", alt="player-icon")
    if icone is None or icone.parent is None:
        raise ErroParsing("nick: img[alt=player-icon] não encontrada")
    nick: str = icone.parent.get_text(strip=True)
    if not nick:
        raise ErroParsing("nick: texto vazio no h2 do jogador")
    return nick


def _parsear_clube(soup: BeautifulSoup) -> str | None:
    link = soup.select_one("a[href*='/clubs/']")
    return link.get_text(strip=True) if link else None


def _numero(texto: str) -> int:
    """'73,118' → 73118. Pega o último número do texto."""
    numeros = re.findall(r"[\d,]+", texto)
    if not numeros:
        raise ErroParsing(f"número esperado em {texto!r}")
    return int(numeros[-1].replace(",", ""))


def _parsear_stats(soup: BeautifulSoup) -> dict:
    stats: dict = {}
    rotulos: dict[str, str] = {
        "LEVEL": "level",
        "TROPHIES": "trofeus",
        "HIGHEST TROPHIES": "trofeus_max",
        "WIN STREAK (CURRENT)": "win_streak_atual",
        "WIN STREAK (MAX)": "win_streak_max",
        "3 VS 3": "vitorias_3v3",
        "SOLO VICTORIES": "vitorias_solo",
        "DUO VICTORIES": "vitorias_duo",
    }
    for th in soup.select("table th"):
        rotulo: str = th.get_text(" ", strip=True)
        td = th.find_next_sibling("td")
        if td is None:
            continue
        if rotulo == "RANKED RANK":
            texto: str = td.get_text(" ", strip=True)
            m = re.search(r"CURRENT\s*(.+?)\s*HIGHEST\s*(.+)", texto)
            if m:
                stats["ranked_atual"] = m.group(1).strip()
                stats["ranked_max"] = m.group(2).strip()
        elif rotulo in rotulos:
            stats[rotulos[rotulo]] = _numero(td.get_text(" ", strip=True))
    faltando = [c for c in ("level", "trofeus", "trofeus_max") if c not in stats]
    if faltando:
        raise ErroParsing(f"stats gerais: campos não encontrados: {faltando}")
    return stats


def _parsear_brawlers(soup: BeautifulSoup) -> list[dict]:
    tabela = soup.find("table", id="brawlersOwnedTable")
    if not isinstance(tabela, Tag):
        raise ErroParsing("brawlers: tabela #brawlersOwnedTable não encontrada")
    corpo = tabela.find("tbody")
    if not isinstance(corpo, Tag):
        raise ErroParsing("brawlers: tbody não encontrado")

    brawlers: list[dict] = []
    for linha in corpo.find_all("tr"):
        celulas = linha.find_all("td")
        if len(celulas) < 12:
            raise ErroParsing(f"brawlers: linha com {len(celulas)} células (esperado 12)")
        tier_attr = celulas[2].get("data-order")
        brawlers.append({
            "nome": celulas[0].get_text(strip=True),
            "power": _numero(celulas[1].get_text(strip=True)),
            "tier": int(tier_attr) if tier_attr else None,
            "trofeus": _numero(celulas[3].get_text(strip=True)),
            "trofeus_max": _numero(celulas[4].get_text(strip=True)),
            "win_streak_atual": _numero(celulas[5].get_text(strip=True) or "0"),
            "win_streak_max": _numero(celulas[6].get_text(strip=True) or "0"),
            "skin": celulas[11].get_text(" ", strip=True) or None,
        })
    if not brawlers:
        raise ErroParsing("brawlers: tabela vazia")
    return brawlers


_RE_HASH = re.compile(r"^[0-9a-f]{40}$")
_RE_DURACAO = re.compile(r"^(\d{2}):(\d{2})$")
_RE_TROFEUS_DELTA = re.compile(r"^[+-]?\d+$")


def _parsear_batalhas(soup: BeautifulSoup, tag: str) -> list[dict]:
    """Cada batalha é um card com id = hash hex de 40 chars (único, usado p/ dedupe).

    Header no formato: 'TIPO - MODO | Resultado | [±troféus] | mm:ss'.
    Em showdown o resultado pode ser 'Rank N' em vez de Victory/Defeat.
    """
    cards = soup.find_all("div", id=_RE_HASH)
    batalhas: list[dict] = []
    for card in cards:
        header = card.find("div", class_="card-header")
        if header is None:
            raise ErroParsing(f"batalha {card.get('id')}: card-header não encontrado")

        partes: list[str] = [
            p.strip() for p in header.get_text(" ", strip=True).split("|") if p.strip()
        ]
        if len(partes) < 2:
            raise ErroParsing(f"batalha {card.get('id')}: header inesperado {partes!r}")

        modo_bruto: str = partes[0]
        tipo, _, modo = modo_bruto.partition(" - ")
        if not modo:  # sem prefixo 'RANKED - '
            tipo, modo = "TROPHIES", modo_bruto

        duracao_seg: int | None = None
        trofeus_delta: int | None = None
        for parte in partes[2:]:
            m = _RE_DURACAO.match(parte)
            if m:
                duracao_seg = int(m.group(1)) * 60 + int(m.group(2))
            elif _RE_TROFEUS_DELTA.match(parte):
                trofeus_delta = int(parte)

        tempo = header.find("time")
        mapa_img = header.find("img", attrs={"data-map-name": True})

        brawler, star_player = _brawler_do_jogador(card, tag)
        batalhas.append({
            "hash": str(card.get("id")),
            "ocorrida_em": str(tempo.get("datetime")) if tempo else None,
            "tipo": tipo.strip(),
            "modo": modo.strip(),
            "resultado": partes[1],
            "mapa": str(mapa_img.get("data-map-name")) if mapa_img else None,
            "duracao_seg": duracao_seg,
            "trofeus_delta": trofeus_delta,
            "brawler": brawler,
            "star_player": star_player,
        })
    if not batalhas:
        raise ErroParsing("batalhas: nenhum card de batalha encontrado")
    return batalhas


def _brawler_do_jogador(card: Tag, tag: str) -> tuple[str | None, bool]:
    """Acha o brawler usado pelo dono da tag e se ele foi star player.

    Estrutura: <img class=icon-medium title=BRAWLER> ... <a data-bs-player-tag=#TAG>
    e, se star player, um <span title='Star Player'> logo após o <a>.
    """
    ancora = card.find("a", attrs={"data-bs-player-tag": tag})
    if ancora is None:
        return None, False

    brawler: str | None = None
    for anterior in ancora.find_all_previous("img"):
        classes = anterior.get("class") or []
        if "icon-medium" in classes and anterior.get("title"):
            brawler = str(anterior.get("title"))
            break

    star_player: bool = False
    for proximo in ancora.find_next_siblings():
        if proximo.name == "hr":
            break
        if proximo.name == "span" and proximo.get("title") == "Star Player":
            star_player = True
            break
        if proximo.find("span", title="Star Player") is not None:
            star_player = True
            break
    return brawler, star_player
