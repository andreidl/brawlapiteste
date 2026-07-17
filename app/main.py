"""API do Brawl — app FastAPI. Rodar: uvicorn app.main:app --reload"""
from pathlib import Path

from fastapi import FastAPI, Form
from fastapi.requests import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import db
from app.coleta import brawlace, brawltime
from app.indicadores import meta as indicadores_meta
from app.indicadores import performance

DIR_APP: Path = Path(__file__).resolve().parent

app = FastAPI(title="API do Brawl")
app.mount("/static", StaticFiles(directory=DIR_APP / "static"), name="static")
templates = Jinja2Templates(directory=DIR_APP / "templates")


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    conexao = db.conectar()
    try:
        recentes = conexao.execute(
            "SELECT tag, nick, ultimo_visto FROM jogadores ORDER BY ultimo_visto DESC LIMIT 10"
        ).fetchall()
        return templates.TemplateResponse(
            request, "home.html", {"recentes": [dict(r) for r in recentes]}
        )
    finally:
        conexao.close()


@app.post("/buscar")
def buscar(tag: str = Form(...)):
    try:
        tag_norm: str = brawlace.normalizar_tag(tag)
    except brawlace.TagInvalida:
        return RedirectResponse("/?erro=tag", status_code=303)
    return RedirectResponse(f"/jogador/{tag_norm.lstrip('#')}", status_code=303)


def _consultar(tag: str) -> dict:
    """Coleta o perfil, grava no banco, calcula indicadores sobre o histórico."""
    perfil: dict = brawlace.coletar_perfil(tag)
    conexao = db.conectar()
    try:
        gravacao: dict = db.salvar_consulta(conexao, perfil)
        historico: list[dict] = db.batalhas_do_jogador(conexao, perfil["tag"])
        snapshots: list[dict] = db.snapshots_do_jogador(conexao, perfil["tag"])
        diario: list[dict] = db.historico_diario_do_jogador(conexao, perfil["tag"])
        brawlers_lp: list[dict] = db.historico_brawler_do_jogador(conexao, perfil["tag"])
    finally:
        conexao.close()
    indicadores: dict = performance.calcular_indicadores(
        historico, perfil["brawlers"], snapshots, diario
    )
    extra: dict | None = brawltime.coletar_extra(perfil["tag"])
    correlacao: dict | None = _correlacao_meta(perfil, historico)
    return {
        "perfil": perfil, "gravacao": gravacao,
        "indicadores": indicadores, "extra": extra,
        "brawlers_longo_prazo": brawlers_lp,
        "correlacao": correlacao,
    }


def _correlacao_meta(perfil: dict, batalhas: list[dict]) -> dict | None:
    """Meta + eventos + correlação. Falha aqui nunca derruba a página."""
    try:
        dados_meta: dict = brawlace.coletar_meta()
        eventos: list[dict] = brawlace.coletar_eventos()
    except (brawlace.ErroColeta, brawlace.ErroParsing):
        return None
    conexao = db.conectar()
    try:
        db.salvar_meta(conexao, dados_meta)
    finally:
        conexao.close()
    return indicadores_meta.calcular_meta_jogador(
        dados_meta, eventos, batalhas, perfil["brawlers"]
    )


@app.get("/jogador/{tag}", response_class=HTMLResponse)
def pagina_jogador(request: Request, tag: str):
    try:
        dados: dict = _consultar(tag)
    except brawlace.TagInvalida as erro:
        return templates.TemplateResponse(
            request, "erro.html", {"mensagem": str(erro)}, status_code=404
        )
    except brawlace.ErroColeta as erro:
        return templates.TemplateResponse(
            request, "erro.html", {"mensagem": f"brawlace.com indisponível: {erro}"},
            status_code=502,
        )
    return templates.TemplateResponse(request, "jogador.html", dados)


@app.get("/api/meta")
def api_meta():
    try:
        dados_meta: dict = brawlace.coletar_meta()
        eventos: list[dict] = brawlace.coletar_eventos()
    except (brawlace.ErroColeta, brawlace.ErroParsing) as erro:
        return JSONResponse({"erro": str(erro)}, status_code=502)
    conexao = db.conectar()
    try:
        db.salvar_meta(conexao, dados_meta)
    finally:
        conexao.close()
    return {"meta": dados_meta, "eventos": eventos}


@app.get("/api/jogador/{tag}")
def api_jogador(tag: str):
    try:
        dados: dict = _consultar(tag)
    except brawlace.TagInvalida as erro:
        return JSONResponse({"erro": str(erro)}, status_code=404)
    except brawlace.ErroColeta as erro:
        return JSONResponse({"erro": str(erro)}, status_code=502)
    return dados
