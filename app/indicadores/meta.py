"""Correlação jogador × meta (parte 3 do projeto — CLAUDE.md §5).

- Score vs meta (0–100): o quanto os brawlers que o jogador joga estão bem
  posicionados no meta dos modos em que ele os joga. Percentil por posição no
  ranking de Star Player %, ponderado pelo número de partidas do jogador.
- Sugestões de pick: para cada evento ativo, os melhores brawlers do meta do
  modo que o jogador tem em power alto.
"""

POWER_MINIMO_SUGESTAO: int = 9
MAX_PICKS_POR_EVENTO: int = 3


def _percentil(posicao: int, total: int) -> float:
    """1º de N → 1.0; último → próximo de 0."""
    if total <= 1:
        return 1.0
    return 1.0 - (posicao - 1) / total


def score_vs_meta(meta: dict, batalhas: list[dict]) -> dict | None:
    """Média ponderada (por partidas) do percentil de cada dupla modo+brawler
    que o jogador jogou. Retorna score 0–100 + detalhamento."""
    modos_meta: dict = meta.get("modos", {})
    pesos: dict[tuple[str, str], int] = {}
    for b in batalhas:
        modo, brawler = b.get("modo"), b.get("brawler")
        if not modo or not brawler or modo not in modos_meta:
            continue
        pesos[(modo, brawler)] = pesos.get((modo, brawler), 0) + 1
    if not pesos:
        return None

    detalhes: list[dict] = []
    soma: float = 0.0
    peso_total: int = 0
    for (modo, brawler), partidas in pesos.items():
        ranking = modos_meta[modo]
        total = len(ranking)
        entrada = next((r for r in ranking if r["brawler"] == brawler), None)
        posicao = entrada["posicao"] if entrada else total  # fora do ranking = último
        pct = _percentil(posicao, total)
        soma += pct * partidas
        peso_total += partidas
        detalhes.append({
            "modo": modo, "brawler": brawler, "partidas": partidas,
            "posicao_meta": posicao if entrada else None,
            "total_ranking": total,
            "percentil": round(pct * 100, 1),
        })
    detalhes.sort(key=lambda d: d["partidas"], reverse=True)
    return {
        "score": round(soma / peso_total * 100, 1),
        "detalhes": detalhes[:10],
    }


def sugestoes_por_evento(
    meta: dict, eventos: list[dict], brawlers_jogador: list[dict]
) -> list[dict]:
    """Para cada evento ativo: top brawlers do meta do modo que o jogador tem
    com power >= POWER_MINIMO_SUGESTAO, ordenados pela posição no meta."""
    do_jogador: dict[str, dict] = {b["nome"]: b for b in brawlers_jogador}
    modos_meta: dict = meta.get("modos", {})

    sugestoes: list[dict] = []
    vistos: set[tuple[str, str]] = set()
    for evento in eventos:
        modo, mapa = evento["modo"], evento["mapa"]
        if (modo, mapa) in vistos or modo not in modos_meta:
            continue
        vistos.add((modo, mapa))
        picks: list[dict] = []
        for linha in modos_meta[modo]:
            meu = do_jogador.get(linha["brawler"])
            if meu is None or meu["power"] < POWER_MINIMO_SUGESTAO:
                continue
            picks.append({
                "brawler": linha["brawler"],
                "posicao_meta": linha["posicao"],
                "star_player_pct": linha["star_player_pct"],
                "power": meu["power"],
                "trofeus": meu["trofeus"],
            })
            if len(picks) >= MAX_PICKS_POR_EVENTO:
                break
        sugestoes.append({"modo": modo, "mapa": mapa, "picks": picks})
    return sugestoes


def calcular_meta_jogador(
    meta: dict, eventos: list[dict], batalhas: list[dict],
    brawlers_jogador: list[dict],
) -> dict:
    return {
        "data_meta": meta.get("data"),
        "score": score_vs_meta(meta, batalhas),
        "sugestoes": sugestoes_por_evento(meta, eventos, brawlers_jogador),
    }
