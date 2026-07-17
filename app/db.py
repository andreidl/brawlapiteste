"""SQLite — schema e gravação (CLAUDE.md §6). Banco em data/brawl.db."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

CAMINHO_BANCO: Path = Path(__file__).resolve().parents[1] / "data" / "brawl.db"

_SCHEMA: str = """
CREATE TABLE IF NOT EXISTS jogadores (
  tag TEXT PRIMARY KEY,
  nick TEXT,
  primeiro_visto TEXT,
  ultimo_visto TEXT
);
CREATE TABLE IF NOT EXISTS snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tag TEXT REFERENCES jogadores(tag),
  criado_em TEXT,
  trofeus INTEGER, trofeus_max INTEGER, level INTEGER,
  vitorias_3v3 INTEGER, vitorias_solo INTEGER, vitorias_duo INTEGER,
  brawlers_json TEXT
);
CREATE TABLE IF NOT EXISTS batalhas (
  hash TEXT PRIMARY KEY,
  tag TEXT REFERENCES jogadores(tag),
  ocorrida_em TEXT,
  modo TEXT,
  tipo TEXT,
  mapa TEXT,
  brawler TEXT,
  resultado TEXT,
  duracao_seg INTEGER,
  trofeus_delta INTEGER,
  star_player INTEGER
);
CREATE TABLE IF NOT EXISTS meta_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  data TEXT, modo TEXT, brawler TEXT,
  star_player_pct REAL, posicao INTEGER
);
CREATE TABLE IF NOT EXISTS historico_diario (
  tag TEXT, data TEXT, batalhas INTEGER, vitorias INTEGER, derrotas INTEGER,
  trofeus_delta INTEGER, trofeus_fim INTEGER, brawlers_json TEXT,
  fonte TEXT DEFAULT 'brawlify',
  PRIMARY KEY (tag, data)
);
CREATE TABLE IF NOT EXISTS historico_brawler (
  tag TEXT, brawler TEXT, jogos INTEGER, vitorias INTEGER, derrotas INTEGER,
  empates INTEGER, winrate_pct REAL, trofeus_delta INTEGER,
  fonte TEXT DEFAULT 'brawlify',
  PRIMARY KEY (tag, brawler, fonte)
);
CREATE TABLE IF NOT EXISTS historico_brawler_modo (
  tag TEXT, brawler TEXT, modo TEXT, vitorias INTEGER, derrotas INTEGER,
  empates INTEGER, trofeus_delta INTEGER,
  PRIMARY KEY (tag, brawler, modo)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_meta_snapshot
  ON meta_snapshots (data, modo, brawler);
"""


def conectar(caminho: Path | None = None) -> sqlite3.Connection:
    caminho = caminho or CAMINHO_BANCO
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conexao = sqlite3.connect(caminho)
    conexao.row_factory = sqlite3.Row
    conexao.executescript(_SCHEMA)
    return conexao


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def salvar_consulta(conexao: sqlite3.Connection, perfil: dict) -> dict:
    """Grava jogador + snapshot + batalhas novas (dedupe por hash).

    Retorna {'batalhas_novas': int, 'total_batalhas': int}.
    """
    agora: str = _agora()
    tag: str = perfil["tag"]
    stats: dict = perfil["stats"]

    conexao.execute(
        """INSERT INTO jogadores (tag, nick, primeiro_visto, ultimo_visto)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(tag) DO UPDATE SET nick = excluded.nick, ultimo_visto = excluded.ultimo_visto""",
        (tag, perfil["nick"], agora, agora),
    )
    conexao.execute(
        """INSERT INTO snapshots (tag, criado_em, trofeus, trofeus_max, level,
                                  vitorias_3v3, vitorias_solo, vitorias_duo, brawlers_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            tag, agora,
            stats.get("trofeus"), stats.get("trofeus_max"), stats.get("level"),
            stats.get("vitorias_3v3"), stats.get("vitorias_solo"), stats.get("vitorias_duo"),
            json.dumps(perfil["brawlers"], ensure_ascii=False),
        ),
    )

    novas: int = 0
    for batalha in perfil["batalhas"]:
        cursor = conexao.execute(
            """INSERT OR IGNORE INTO batalhas
               (hash, tag, ocorrida_em, modo, tipo, mapa, brawler, resultado,
                duracao_seg, trofeus_delta, star_player)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                batalha["hash"], tag, batalha["ocorrida_em"], batalha["modo"],
                batalha["tipo"], batalha["mapa"], batalha["brawler"],
                batalha["resultado"], batalha["duracao_seg"],
                batalha["trofeus_delta"], int(batalha["star_player"]),
            ),
        )
        novas += cursor.rowcount
    conexao.commit()

    total: int = conexao.execute(
        "SELECT COUNT(*) FROM batalhas WHERE tag = ?", (tag,)
    ).fetchone()[0]
    return {"batalhas_novas": novas, "total_batalhas": total}


def batalhas_do_jogador(conexao: sqlite3.Connection, tag: str) -> list[dict]:
    linhas = conexao.execute(
        "SELECT * FROM batalhas WHERE tag = ? ORDER BY ocorrida_em DESC", (tag,)
    ).fetchall()
    return [dict(linha) for linha in linhas]


def snapshots_do_jogador(conexao: sqlite3.Connection, tag: str) -> list[dict]:
    linhas = conexao.execute(
        "SELECT * FROM snapshots WHERE tag = ? ORDER BY criado_em", (tag,)
    ).fetchall()
    return [dict(linha) for linha in linhas]


def historico_diario_do_jogador(conexao: sqlite3.Connection, tag: str) -> list[dict]:
    linhas = conexao.execute(
        "SELECT * FROM historico_diario WHERE tag = ? ORDER BY data", (tag,)
    ).fetchall()
    return [dict(linha) for linha in linhas]


def historico_brawler_do_jogador(conexao: sqlite3.Connection, tag: str) -> list[dict]:
    linhas = conexao.execute(
        "SELECT * FROM historico_brawler WHERE tag = ? ORDER BY jogos DESC", (tag,)
    ).fetchall()
    return [dict(linha) for linha in linhas]


def salvar_meta(conexao: sqlite3.Connection, meta: dict) -> int:
    """Grava o snapshot do meta (dedupe por data+modo+brawler). Retorna novas linhas."""
    novas: int = 0
    for modo, ranking in meta.get("modos", {}).items():
        for linha in ranking:
            cursor = conexao.execute(
                """INSERT OR IGNORE INTO meta_snapshots
                   (data, modo, brawler, star_player_pct, posicao)
                   VALUES (?, ?, ?, ?, ?)""",
                (meta.get("data"), modo, linha["brawler"],
                 linha["star_player_pct"], linha["posicao"]),
            )
            novas += cursor.rowcount
    conexao.commit()
    return novas
