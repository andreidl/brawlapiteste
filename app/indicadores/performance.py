"""Indicadores de performance (parte 2) — calculados sobre o histórico
ACUMULADO de batalhas do SQLite, não só as 25 do site (CLAUDE.md §4).

Winrate = vitórias / (vitórias + derrotas). Draws e resultados de showdown
('Rank N') ficam fora do denominador.
"""
import pandas as pd

LIMIAR_AMOSTRA_PEQUENA: int = 20


def calcular_indicadores(
    batalhas: list[dict],
    brawlers: list[dict],
    snapshots: list[dict],
    historico_diario: list[dict] | None = None,
) -> dict:
    """Recebe o histórico do banco e devolve todos os KPIs prontos para exibir."""
    df = pd.DataFrame(batalhas)
    decididas = (
        df[df["resultado"].isin(["Victory", "Defeat"])]
        if not df.empty else pd.DataFrame()
    )
    return {
        "partidas": int(len(df)),
        "partidas_decididas": int(len(decididas)),
        "amostra_pequena": len(decididas) < LIMIAR_AMOSTRA_PEQUENA,
        "winrate_geral": _winrate(decididas),
        "por_modo": _agrupado(decididas, "modo"),
        "por_brawler": _agrupado(decididas, "brawler"),
        "queda_trofeus": _queda_trofeus(brawlers),
        "evolucao": _evolucao(snapshots),
        "longo_prazo": _longo_prazo(historico_diario or []),
    }


def _longo_prazo(historico: list[dict]) -> dict | None:
    """Agregados do histórico diário importado do Brawlify (245 dias)."""
    if not historico:
        return None
    vitorias: int = sum(d["vitorias"] for d in historico)
    derrotas: int = sum(d["derrotas"] for d in historico)
    decididas: int = vitorias + derrotas
    return {
        "dias_jogados": len(historico),
        "batalhas": sum(d["batalhas"] for d in historico),
        "vitorias": vitorias,
        "derrotas": derrotas,
        "winrate": round(vitorias / decididas * 100, 1) if decididas else None,
        "trofeus_delta": sum(d["trofeus_delta"] for d in historico),
        "inicio": historico[0]["data"],
        "fim": historico[-1]["data"],
        "evolucao": [
            {"dia": d["data"], "trofeus": d["trofeus_fim"]}
            for d in historico if d.get("trofeus_fim")
        ],
    }


def _winrate(decididas: pd.DataFrame) -> float | None:
    if decididas.empty:
        return None
    return round(float((decididas["resultado"] == "Victory").mean()) * 100, 1)


def _agrupado(decididas: pd.DataFrame, coluna: str) -> list[dict]:
    """Winrate e uso agrupados por modo ou por brawler, mais jogados primeiro."""
    if decididas.empty:
        return []
    grupos = decididas.groupby(coluna)["resultado"].agg(
        partidas="count", vitorias=lambda r: int((r == "Victory").sum())
    ).reset_index()
    grupos["winrate"] = (grupos["vitorias"] / grupos["partidas"] * 100).round(1)
    grupos["uso_pct"] = (grupos["partidas"] / len(decididas) * 100).round(1)
    grupos = grupos.sort_values(["partidas", "winrate"], ascending=False)
    return grupos.rename(columns={coluna: "nome"}).to_dict("records")


def _queda_trofeus(brawlers: list[dict], minimo_max: int = 100) -> list[dict]:
    """Brawlers mais distantes do próprio pico — candidatos a recuperar troféus."""
    quedas: list[dict] = []
    for b in brawlers:
        if b["trofeus_max"] < minimo_max:
            continue
        queda: int = b["trofeus_max"] - b["trofeus"]
        if queda <= 0:
            continue
        quedas.append({
            "nome": b["nome"],
            "trofeus": b["trofeus"],
            "trofeus_max": b["trofeus_max"],
            "queda": queda,
            "queda_pct": round(queda / b["trofeus_max"] * 100, 1),
        })
    quedas.sort(key=lambda q: q["queda"], reverse=True)
    return quedas[:10]


def _evolucao(snapshots: list[dict]) -> list[dict]:
    """Série temporal de troféus (1 ponto por dia — o último snapshot do dia)."""
    if not snapshots:
        return []
    df = pd.DataFrame(snapshots)[["criado_em", "trofeus"]].dropna()
    df["dia"] = df["criado_em"].str[:10]
    diario = df.groupby("dia").last().reset_index()
    return diario[["dia", "trofeus"]].to_dict("records")
