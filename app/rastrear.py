"""Rastreamento automático — consulta todos os jogadores já vistos e acumula
batalhas novas no banco. Executado pelo Agendador de Tarefas do Windows a cada
2 h (tarefa 'ApiDoBrawl_Rastreio'). Rodar manual: python -m app.rastrear
"""
from datetime import datetime
from pathlib import Path

from app import db
from app.coleta import brawlace

ARQUIVO_LOG: Path = Path(__file__).resolve().parents[1] / "data" / "rastreio.log"


def _log(mensagem: str) -> None:
    linha: str = f"{datetime.now().isoformat(timespec='seconds')} {mensagem}"
    print(linha)
    ARQUIVO_LOG.parent.mkdir(parents=True, exist_ok=True)
    with ARQUIVO_LOG.open("a", encoding="utf-8") as arquivo:
        arquivo.write(linha + "\n")


def main() -> None:
    conexao = db.conectar()
    try:
        tags: list[str] = [
            linha["tag"] for linha in conexao.execute("SELECT tag FROM jogadores")
        ]
        if not tags:
            _log("nenhum jogador no banco ainda — nada a rastrear")
            return
        for tag in tags:
            try:
                perfil: dict = brawlace.coletar_perfil(tag)
                resultado: dict = db.salvar_consulta(conexao, perfil)
                _log(
                    f"{tag} ({perfil['nick']}): +{resultado['batalhas_novas']} batalhas "
                    f"(total {resultado['total_batalhas']})"
                )
            except (brawlace.TagInvalida, brawlace.ErroColeta, brawlace.ErroParsing) as erro:
                _log(f"{tag}: ERRO — {erro}")
    finally:
        conexao.close()


if __name__ == "__main__":
    main()
