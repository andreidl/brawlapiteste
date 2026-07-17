# API do Brawl — Guia de Contexto Completo para Claude

> Leia este arquivo inteiro antes de qualquer modificação no projeto.
> **Última atualização: 17/07/2026 — projeto criado, fonte de dados validada na prática.**

## IMPORTANTE — PLANO DE TRABALHO

**Leia `plano.md` no início de cada sessão.**
Esse arquivo contém a fila priorizada de tudo que falta (P0→P3).
Ao terminar uma tarefa, marque `[x]` e atualize a seção "CONCLUÍDO" com a data.

---

## 1. O QUE É O PROJETO

Site web em Python onde o usuário digita a **tag de um jogador de Brawl Stars**
(ex: `#299PGGLQL`) e recebe:

1. **Coleta** — dados públicos do jogador raspados da web (sem chave da API oficial)
2. **Indicadores de performance** — winrate geral e por modo, performance por
   brawler, evolução de troféus ao longo do tempo
3. **Meta** — melhores brawlers por modo/mapa no meta atual, **correlacionados**
   com os dados do jogador (o quanto ele joga com brawlers fortes; sugestões de pick)

**Princípio do projeto: o mais rápido e simples possível.** Nada de microsserviços,
filas, Docker ou frontend framework. Um app FastAPI só, HTML server-side.

### Decisões fechadas com o usuário (17/07/2026 — NÃO reabrir sem ele pedir)

| Decisão | Escolha |
|---|---|
| Produto | Site web completo (não é API pura para terceiros) |
| Fonte de dados | **Scraping de HTML** do brawlace.com (usuário recusou API oficial da Supercell) |
| Stack | Python + FastAPI + httpx + BeautifulSoup + pandas + Jinja2 |
| Persistência | SQLite local, snapshots a cada consulta |
| Indicadores | Todos os 4: winrate por modo, performance por brawler, evolução de troféus, score vs meta |
| Tag de teste | `#299PGGLQL` (perfil do usuário: **SNK \| andreidl**) |

---

## 2. STACK E ESTRUTURA

- **Python 3.11+** — FastAPI + uvicorn, httpx, beautifulsoup4 + lxml, pandas, Jinja2
- **SQLite** via `sqlite3` da stdlib (sem ORM — simplicidade)
- Frontend: templates Jinja2 + CSS puro servidos pelo próprio FastAPI. Sem build step.

```
C:\projetos\api-do-brawl\
  app\
    main.py                  — FastAPI: rotas web + rotas /api
    db.py                    — schema SQLite + upserts (banco em data/brawl.db)
    coleta\
      brawlace.py            — scraper: perfil, meta, eventos
      cache.py               — cache de requisições em disco com TTL
    indicadores\
      performance.py         — KPIs com pandas (parte 2)
      meta.py                — correlação jogador × meta (parte 3)
    templates\               — Jinja2 (base.html, home.html, jogador.html)
    static\                  — CSS/ícones
  tests\
    fixtures\                — HTMLs reais salvos p/ testar parsing offline
  data\                      — brawl.db + cache (NUNCA commitar)
  plano.md                   — fila de trabalho priorizada
  requirements.txt
```

**Rodar:** `uvicorn app.main:app --reload` (na raiz do projeto)
**Testes:** `python -m pytest tests/`

---

## 3. FONTE DE DADOS — brawlace.com (VALIDADO 17/07/2026)

> Tudo abaixo foi **verificado na prática** via curl/navegador em 17/07/2026.
> Se o parsing quebrar no futuro, re-inspecionar o HTML antes de culpar o código.

### Por que brawlace.com

- **brawlify.com**: bloqueado por Cloudflare challenge → INVIÁVEL para scraping
- **api.brawlify.com**: respondeu 522 (origem fora do ar) → retestar no futuro
  como fonte secundária, mas NÃO depender dela
- **brawlace.com**: server-rendered (dados já vêm no HTML, jQuery só para UI),
  sem challenge, respondeu 200 com ~420 KB via curl com User-Agent de navegador ✅

### 3.1 Perfil do jogador — `https://brawlace.com/players/%23TAG`

- Tag em **UPPERCASE**, `#` codificado como `%23`. Tag inválida → título "404 Page Not Found".
- A página contém, em um único GET:
  - **Stats gerais:** nick, level, troféus atuais/máximos, ranked rank (atual e
    máximo), win streak (atual/máx), vitórias 3v3, solo e duo
  - **Tabela de brawlers** (um `<tr>` por brawler): nome, power, tier, troféus,
    troféus máximos, win streaks, hypercharge/gears/star powers/gadgets, skin
  - **Battle log — últimas 25 partidas**, seção `<h2 id='battlelog-section'>`:
    - Resumo pronto: `Victory : 11 (44%)` / `Defeat : 14`
    - Cada batalha é um card com **id = hash hex de 40 chars, ÚNICO por batalha**
      → usar como chave primária para deduplicar no SQLite
    - Header do card: `RANKED - HOT ZONE | Defeat | 01:16` +
      `<time datetime='2026-07-17T03:11:36Z'>` + `data-map-name='Controller Chaos'`
    - Corpo: cada jogador com brawler (atributo `title` do img), power, troféus,
      tag (`data-bs-player-tag`) e badge de star player
    - Filtro por modo via query string: `?filter[gameMode]=hotZone` (valores
      camelCase: `gemGrab`, `brawlBall`, `soloShowdown`, `knockout`, `bounty`, `hotZone`...)

### 3.2 Meta global — `https://brawlace.com/meta`

- Meta **diário** por modo de jogo, atualizado ~3x/dia, com histórico de datas
- Por modo: ranking de brawlers por **contagem e % de Star Player** + trends
- Modos disponíveis: Solo/Duo/Trio Showdown, Brawl Ball (3v3 e 5v5), Gem Grab,
  Knockout (3v3 e 5v5), Bounty, Hot Zone, Heist, Brawl Arena, Basket Brawl, Wipeout
- Também tem "Game Mode Popularity"

### 3.3 Eventos/mapas ativos — `https://brawlace.com/events`

- Eventos atuais e futuros com modo + mapa (200, ~190 KB)

### 3.4 Brawlers (referência) — `https://brawlace.com/brawlers`

- Lista de todos os brawlers com detalhes (200, ~100 KB)

### 3.4b Fonte complementar — brawltime.ninja (API JSON pública, validada 17/07/2026)

- `GET https://brawltime.ninja/api/player.byTagExtra?input={"json":"TAG"}` (tag SEM `#`,
  input URL-encoded) → `accountCreationYear`, `recordLevel`, `recordPoints`
- Usada só para a seção "Carreira". **Falha nunca derruba a consulta** (retorna None).
- TTL 24 h. Implementada em `app/coleta/brawltime.py`.
- O tracking do BrawlTime para uma tag só começa quando alguém visita o perfil lá —
  histórico deles do usuário começou em 17/07/2026, não tem passado antigo.

### 3.6 Histórico do passado — importação única do Brawlify (FEITA 17/07/2026)

- A Supercell só expõe as últimas **25 batalhas**; batalha antiga só existe em
  quem gravou na época. Descoberta importante: **o brawlify.com rastreava a tag
  do usuário desde 15/11/2025** (245 dias, 1.030 batalhas, 652V/377D = 63%).
- O Brawlify é protegido por Cloudflare → scraping automático IMPOSSÍVEL.
  A coleta foi feita **uma única vez, manualmente**: usuário passou o security
  check no navegador, Claude extraiu os cards diários de cada mês via JS no DOM
  (`/player/TAG/history?year=&month=`), salvou em `dados_brawlify/*.json`.
- `python -m app.importar_brawlify dados_brawlify` parseia e grava nas tabelas
  `historico_diario` (57 dias: batalhas/V/D/delta + brawlers do dia em JSON +
  `trofeus_fim` reconstruído por soma reversa de deltas ancorada em 73.118 no
  dia 17/07/2026) e `historico_brawler` (agregados: EMZ 103 jogos 57% etc.).
  Import é idempotente (INSERT OR REPLACE).
- Também importado (17/07/2026): `dados_brawlify/brawlers_cards.json` — página
  `/player/TAG/brawlers`, cards `article.brawler-card` com V/D totais do período
  POR BRAWLER + detalhe por modo. Atenção: cada card lista só os ~4 modos mais
  jogados; V/D totais são exatos (linha BATTLES), mas `trofeus_delta` somado dos
  modos pode subcontar em brawlers muito jogados. Winrate = V/(V+D), empates fora.
- O battle log batalha-por-batalha do Brawlify é PAGO ($4.99/mês) — não temos.
- Se o usuário quiser atualizar no futuro: repetir o processo manual (ele passa
  o check, extrair só os meses novos). NÃO tentar automatizar o bypass.
- Daqui pra frente quem acumula é o nosso rastreador: tarefa agendada
  `ApiDoBrawl_Rastreio` (instalar com `instalar_rastreio.ps1`).

### 3.5 Regras de coleta (OBRIGATÓRIAS)

- **Sempre** enviar User-Agent de navegador:
  `Mozilla/5.0 (Windows NT 10.0; Win64; x64)` — sem UA o site pode bloquear
- **Cache em disco obrigatório** antes de qualquer request:
  perfil TTL 10 min · meta TTL 6 h · eventos TTL 1 h
- Máximo **1 request por segundo**; nunca crawlear em massa — só a tag consultada
- Todo parser deve ter **teste com fixture HTML salvo** em `tests/fixtures/`
  (scraping quebra quando o site muda de layout; o teste offline detecta isso)
- Parsing falhou / campo sumiu → levantar exceção clara com o nome do campo,
  nunca retornar dado parcial silenciosamente

---

## 4. INDICADORES (PARTE 2) — especificação

Calculados com pandas em `app/indicadores/performance.py`:

| Indicador | Fonte | Cálculo |
|---|---|---|
| Winrate geral | battle log acumulado no SQLite | vitórias / (vitórias+derrotas), excluir draws do denominador |
| Winrate por modo | battle log | mesmo cálculo agrupado por `modo` |
| Winrate por brawler | battle log | agrupado pelo brawler usado pelo jogador |
| Uso por brawler | battle log | % de partidas com cada brawler |
| Queda de troféus | tabela de brawlers | `(highest - atual) / highest` — brawlers "em queda" |
| Evolução de troféus | snapshots SQLite | série temporal de `trofeus` por consulta |

> O battle log só expõe as últimas 25 partidas. O valor do SQLite é **acumular**:
> cada consulta insere as batalhas novas (dedupe por hash) — com o tempo o
> histórico fica rico. Deixar claro na UI quando a amostra é pequena (<20 partidas).

## 5. META E CORRELAÇÃO (PARTE 3) — especificação

`app/indicadores/meta.py`:

- **Tier por modo:** posição de cada brawler no ranking de Star Player % do /meta
- **Score vs meta do jogador:** para os brawlers mais jogados dele (parte 2),
  média ponderada da posição no meta dos modos que ele joga →
  "você joga com brawlers meta?" (score 0–100)
- **Sugestão de picks:** cruzar eventos ativos (/events) × meta do modo ×
  brawlers do jogador com maior power/troféus → "para o mapa X, seus melhores
  picks são A, B, C"

## 6. BANCO — SQLite (`data/brawl.db`)

```sql
CREATE TABLE jogadores (
  tag TEXT PRIMARY KEY,           -- '#299PGGLQL'
  nick TEXT,
  primeiro_visto TEXT,            -- ISO 8601 UTC
  ultimo_visto TEXT
);
CREATE TABLE snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tag TEXT REFERENCES jogadores(tag),
  criado_em TEXT,                 -- ISO 8601 UTC
  trofeus INTEGER, trofeus_max INTEGER, level INTEGER,
  vitorias_3v3 INTEGER, vitorias_solo INTEGER, vitorias_duo INTEGER,
  brawlers_json TEXT              -- tabela de brawlers inteira em JSON
);
CREATE TABLE batalhas (
  hash TEXT PRIMARY KEY,          -- hash de 40 chars do brawlace (único)
  tag TEXT REFERENCES jogadores(tag),
  ocorrida_em TEXT,               -- do <time datetime>
  modo TEXT,                      -- 'HOT ZONE'
  tipo TEXT,                      -- 'RANKED' | 'TROPHIES' etc (prefixo do header)
  mapa TEXT,
  brawler TEXT,                   -- brawler usado pelo dono da tag
  resultado TEXT,                 -- 'Victory' | 'Defeat' | 'Draw'
  duracao_seg INTEGER,
  star_player INTEGER             -- 0/1
);
CREATE TABLE meta_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  data TEXT, modo TEXT, brawler TEXT,
  star_player_pct REAL, posicao INTEGER
);
```

## 7. ROTAS

| Rota | Tipo | Descrição |
|---|---|---|
| `GET /` | HTML | home: input de tag + últimos jogadores consultados |
| `GET /jogador/{tag}` | HTML | página completa: stats, indicadores, gráfico, meta |
| `GET /api/jogador/{tag}` | JSON | mesmos dados em JSON |
| `GET /api/meta` | JSON | meta atual por modo |

Fluxo de `/jogador/{tag}`: normaliza tag → cache/scrape perfil → grava snapshot +
batalhas novas → calcula indicadores → cache/scrape meta → correlaciona → renderiza.

## 8. CONVENÇÕES

- Nomes de variáveis, funções e UI em **português** (padrão dos projetos do usuário)
- Tipagem explícita em todas as assinaturas (`def winrate(df: pd.DataFrame) -> float:`)
- UI em português (pt-BR)
- `data/` (banco + cache) fora do git; fixtures de teste DENTRO do git
- Sem ORM, sem async desnecessário, sem framework de frontend — simplicidade primeiro
- **Nunca** usar `--no-verify` nos commits; **nunca** adicionar `Co-Authored-By`

## 9. RISCOS CONHECIDOS

| Risco | Mitigação |
|---|---|
| brawlace.com muda o layout → parsers quebram | fixtures + exceções claras por campo |
| brawlace.com adota Cloudflare no futuro | reavaliar com o usuário: API oficial (developer.brawlstars.com + proxy RoyaleAPI) é o plano B já discutido |
| Battle log só tem 25 partidas | SQLite acumula; avisar na UI quando amostra < 20 |
| Rate limit / bloqueio por abuso | cache com TTL + 1 req/s + só a tag consultada |
