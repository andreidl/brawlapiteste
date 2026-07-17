# PLANO — API do Brawl

> Fila priorizada. Trabalhar de cima para baixo. Marcar `[x]` ao concluir
> e mover para CONCLUÍDO com a data.

## P0 — Fundação (sem isso nada funciona) — ✅ CONCLUÍDO 17/07/2026

- [x] Scaffold: `requirements.txt`, venv, `app/main.py` com FastAPI + rota `/`
- [x] `app/coleta/cache.py` — cache em disco com TTL (perfil 10min, meta 6h, eventos 1h)
- [x] `app/coleta/brawlace.py` — `coletar_perfil(tag)`:
  - [x] Baixar HTML com User-Agent correto, tratar 404 (tag inválida)
  - [x] Parsear stats gerais (nick, level, troféus, ranked, vitórias 3v3/solo/duo)
  - [x] Parsear tabela de brawlers
  - [x] Parsear battle log (25 partidas: hash, modo, tipo, mapa, brawler, resultado, duração, timestamp, star player)
  - [x] Salvar fixture HTML em `tests/fixtures/` + testes pytest de parsing
- [x] `app/db.py` — schema do CLAUDE.md §6 + upsert de jogador/snapshot/batalhas (dedupe por hash)

## P1 — Indicadores (parte 2) — ✅ CONCLUÍDO 17/07/2026

- [x] `app/indicadores/performance.py` — winrate geral/por modo/por brawler, uso por brawler, queda de troféus (pandas)
- [x] Evolução de troféus a partir dos snapshots (1 ponto/dia, gráfico SVG inline)
- [x] Página `GET /jogador/{tag}` com tudo renderizado (Jinja2)
- [x] `GET /api/jogador/{tag}` em JSON
- [x] Aviso de "amostra pequena" quando < 20 batalhas acumuladas
- [x] `app/rastrear.py` — rastreamento automático de todos os jogadores do banco (log em data/rastreio.log)
- [ ] **USUÁRIO precisa rodar 1x:** `.\instalar_rastreio.ps1` (PowerShell, na pasta do projeto) — registra a tarefa do Windows a cada 2h. Claude não tem permissão para registrar tarefas agendadas.

## P2 — Meta e correlação (parte 3) — ✅ CONCLUÍDO 17/07/2026

- [x] `coletar_meta()` — parseia /meta (14-15 modos, ranking por Star Player %) + fixture + testes
- [x] `coletar_eventos()` — parseia /events aba ativa (modo + mapa + horários) + fixture + testes
- [x] `app/indicadores/meta.py` — score vs meta 0-100 (percentil ponderado por partidas) + sugestão de picks por evento ativo (meta do modo × brawlers do jogador com power ≥ 9)
- [x] Integrado na página do jogador (seção "Meta atual e recomendações") + `GET /api/meta`
- [x] `meta_snapshots` gravado no SQLite a cada coleta (dedupe por data+modo+brawler)

## P3 — Polimento

- [ ] Home com últimos jogadores consultados
- [ ] CSS decente (tema escuro, cores do Brawl Stars)
- [ ] Tratamento de erros amigável na UI (site fora do ar, tag inválida)
- [ ] git init + primeiro commit (quando o usuário pedir)
- [ ] Avaliar deploy (só se o usuário pedir — por ora roda local)

## CONCLUÍDO

- [x] 17/07/2026 — **Todos os brawlers do período**: extraídos os 104 cards de `/player/TAG/brawlers` do Brawlify (sessão liberada pelo usuário), importados os 82 com batalhas → `historico_brawler` rebuild (V/D/empates/winrate/troféus) + nova `historico_brawler_modo` (V/D por modo de cada brawler). Página mostra a tabela completa. **43 testes passando.**

- [x] 17/07/2026 — **P2 inteiro (meta e correlação)**: parsers de /meta e /events com fixtures, score vs meta (usuário: 84,6/100), sugestões de pick por evento ativo, `GET /api/meta`, 1.422 linhas de meta salvas em `meta_snapshots`. **40 testes passando.** As 3 partes do escopo original do projeto estão completas.

- [x] 17/07/2026 — **Importação do histórico Brawlify (245 dias)**: usuário passou o Cloudflare check no navegador, extraídos 57 dias de jogo (nov/2025→jul/2026) = 1.030 batalhas 652V/377D (63%), +3.527 troféus. Novas tabelas `historico_diario` + `historico_brawler`, troféus absolutos reconstruídos por soma reversa (69.591→73.118, validado contra o resumo do site). Seção "Histórico de longo prazo" na página com gráfico de 8 meses. **29 testes passando.** Processo documentado no CLAUDE.md §3.6 (repetível manualmente; nunca automatizar bypass).

- [x] 17/07/2026 — **Seção Carreira + passado possível**: gráfico de troféus embutido do brawlace (`grafico_trofeus`), fonte complementar brawltime.ninja (`app/coleta/brawltime.py` — ano da conta, record points), seção "Carreira (vida inteira)" na página. Documentada no CLAUDE.md a resposta definitiva sobre "mais passado" (25 batalhas = limite da Supercell). **25 testes passando.**

- [x] 17/07/2026 — **P1 inteiro**: indicadores com pandas (winrate geral 44%, por modo, por brawler, queda de troféus, evolução) renderizados na página + JSON. Rastreador `app/rastrear.py` testado manualmente (2 jogadores no banco). **23 testes passando.** Falta só o usuário instalar a tarefa agendada (`instalar_rastreio.ps1`).
- [x] 17/07/2026 — **P0 inteiro**: scraper de perfil + cache TTL + SQLite com dedupe + páginas home/jogador/erro + API JSON. **16 testes pytest passando.** Validado end-to-end com a tag real #299PGGLQL (25 batalhas coletadas e gravadas; 2ª consulta deduplicou: 0 novas). Adiantado do P1: página do jogador já renderiza stats/batalhas/brawlers e `/api/jogador/{tag}` já existe.
- [x] 17/07/2026 — Decisões de produto/stack/fonte/persistência fechadas com o usuário
- [x] 17/07/2026 — Fonte validada na prática: brawlace.com raspável (brawlify bloqueado por Cloudflare)
- [x] 17/07/2026 — Estrutura de pastas, CLAUDE.md, plano.md, requirements.txt criados
