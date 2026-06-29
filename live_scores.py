#!/usr/bin/env python3
"""
live_scores.py — Feed de placares AO VIVO da Copa do Mundo (saída SOMENTE JSON).

Busca os jogos do dia na API pública da ESPN (grátis, sem chave) e, para cada
jogo ao vivo ou encerrado, busca os GOLS: quem marcou, em que minuto, a
assistência e o tipo (gol normal / pênalti / gol contra).

A saída no stdout é SEMPRE JSON. Nada é gravado no banco — é apenas um feed.
Mensagens de diagnóstico vão para o stderr, então o stdout continua JSON puro.

Esta é uma ferramenta independente: NÃO importa o app Flask nem o banco, então
a dev do projeto pode importá-la em qualquer lugar (rota web, worker, cron...).

─── Uso na linha de comando ───────────────────────────────────────────────────
    python live_scores.py                   # 1 snapshot JSON dos jogos de hoje
    python live_scores.py --date 20221218   # um dia específico (ótimo p/ testar)
    python live_scores.py --watch           # loop: novo JSON a cada 30s (JSONL)
    python live_scores.py --watch --interval 15
    python live_scores.py --no-goals        # mais rápido: pula detalhes de gols
    python live_scores.py --compact         # JSON em uma linha só

─── Uso como módulo (ex.: dentro de uma rota Flask) ──────────────────────────
    from live_scores import snapshot
    data = snapshot()                       # dict pronto para jsonify(...)
    # ex.:  @app.route("/api/ao-vivo")
    #       def ao_vivo(): return jsonify(snapshot())

Dica para a dev: o formato de cada jogo está documentado em `build_match()`.
Para testar com dados reais fora da Copa, use --date com um dia de jogos
passados (ex.: 20221218 = final de 2022, Argentina x França nos pênaltis).
"""

import sys
import json
import time
import argparse
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

try:
    sys.stdout.reconfigure(encoding="utf-8")   # emojis das bandeiras no Windows
except Exception:
    pass

import requests

try:
    import pytz
    SAO_PAULO = pytz.timezone("America/Sao_Paulo")
except Exception:                              # pytz é opcional aqui
    pytz = None
    SAO_PAULO = None

# ─── API pública da ESPN (sem chave) ──────────────────────────────────────────
ESPN_BASE   = "https://site.api.espn.com/apis/site/v2/sports/soccer/FIFA.WORLD"
SCOREBOARD  = ESPN_BASE + "/scoreboard"
SUMMARY     = ESPN_BASE + "/summary"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}

DEFAULT_INTERVAL = 30   # segundos entre cada atualização no modo --watch
HTTP_TIMEOUT = 8        # timeout curto por chamada; falha rápido p/ não prender o worker

# ─── Nomes dos times no formato do app (emoji + português) ────────────────────
# Espelha o TEAM_MAP de seed_matches.py. Times fora do mapa caem no nome cru da
# ESPN (degradação graciosa — o feed nunca quebra por um time desconhecido).
TEAM_MAP = {
    "Mexico": "🇲🇽 México", "South Africa": "🇿🇦 África do Sul",
    "South Korea": "🇰🇷 Coreia do Sul", "Korea Republic": "🇰🇷 Coreia do Sul",
    "Czechia": "🇨🇿 República Tcheca", "Czech Republic": "🇨🇿 República Tcheca",
    "Canada": "🇨🇦 Canadá", "Bosnia & Herzegovina": "🇧🇦 Bósnia e Herzegovina",
    "Bosnia and Herzegovina": "🇧🇦 Bósnia e Herzegovina",
    "USA": "🇺🇸 EUA", "United States": "🇺🇸 EUA", "Paraguay": "🇵🇾 Paraguai",
    "Qatar": "🇶🇦 Catar", "Switzerland": "🇨🇭 Suíça", "Brazil": "🇧🇷 Brasil",
    "Morocco": "🇲🇦 Marrocos", "Haiti": "🇭🇹 Haiti", "Scotland": "🏴󠁧󠁢󠁳󠁣󠁴󠁿 Escócia",
    "Australia": "🇦🇺 Austrália", "Türkiye": "🇹🇷 Turquia", "Turkey": "🇹🇷 Turquia",
    "Germany": "🇩🇪 Alemanha", "Curaçao": "🇨🇼 Curaçau", "Netherlands": "🇳🇱 Holanda",
    "Japan": "🇯🇵 Japão", "Côte d'Ivoire": "🇨🇮 Costa do Marfim",
    "Ivory Coast": "🇨🇮 Costa do Marfim", "Ecuador": "🇪🇨 Equador",
    "Sweden": "🇸🇪 Suécia", "Tunisia": "🇹🇳 Tunísia", "Spain": "🇪🇸 Espanha",
    "Cape Verde": "🇨🇻 Cabo Verde", "Cabo Verde": "🇨🇻 Cabo Verde",
    "Belgium": "🇧🇪 Bélgica", "Egypt": "🇪🇬 Egito", "France": "🇫🇷 França",
    "Iraq": "🇮🇶 Iraque", "Norway": "🇳🇴 Noruega", "Senegal": "🇸🇳 Senegal",
    "Algeria": "🇩🇿 Argélia", "Argentina": "🇦🇷 Argentina", "Austria": "🇦🇹 Áustria",
    "Jordan": "🇯🇴 Jordânia", "Colombia": "🇨🇴 Colômbia", "Portugal": "🇵🇹 Portugal",
    "DR Congo": "🇨🇩 RD do Congo",
    "Democratic Republic of the Congo": "🇨🇩 RD do Congo",
    "Uzbekistan": "🇺🇿 Uzbequistão", "Croatia": "🇭🇷 Croácia", "Ghana": "🇬🇭 Gana",
    "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inglaterra", "Panama": "🇵🇦 Panamá",
    "Saudi Arabia": "🇸🇦 Arábia Saudita", "Uruguay": "🇺🇾 Uruguai",
    "Iran": "🇮🇷 Irã", "New Zealand": "🇳🇿 Nova Zelândia",
}

# Notas da ESPN (inglês) → nome da fase no formato do app
ESPN_ROUND_NAMES = {
    "round of 32": "Rodada de 32", "round of 16": "Oitavas de Final",
    "quarterfinal": "Quartas de Final", "semifinal": "Semifinal",
    "3rd place": "Disputa do 3º Lugar", "final": "Final", "group": "Fase de Grupos",
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def warn(msg: str) -> None:
    """Diagnóstico vai para o stderr — o stdout fica 100% JSON."""
    print(msg, file=sys.stderr, flush=True)


def map_team(raw: str) -> str:
    """Nome cru da ESPN → emoji + PT; se desconhecido, devolve o nome cru."""
    if not raw:
        return raw
    if raw in TEAM_MAP:
        return TEAM_MAP[raw]
    for k, v in TEAM_MAP.items():
        if k.lower() == raw.lower():
            return v
    return raw


def to_sao_paulo(utc_iso: str) -> str:
    """'2022-12-18T15:00Z' → 'YYYY-MM-DDTHH:MM' no fuso de São Paulo."""
    if not utc_iso:
        return ""
    try:
        dt = datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
        if SAO_PAULO is not None:
            dt = dt.astimezone(SAO_PAULO)
        return dt.strftime("%Y-%m-%dT%H:%M")
    except Exception:
        return str(utc_iso)


def parse_minute(clock: str):
    """ "36'" / "45'+2'" / "120'" → 36 / 45 / 120 (int) ;  "" → None."""
    if not clock:
        return None
    digits = ""
    for ch in clock:
        if ch.isdigit():
            digits += ch
        else:
            break
    return int(digits) if digits else None


def round_name(competition: dict) -> str:
    """Best-effort: lê a fase nas 'notes' do confronto."""
    for note in competition.get("notes", []) or []:
        if not note:
            continue
        text = (note.get("headline") or note.get("text") or "").lower()
        for key, label in ESPN_ROUND_NAMES.items():
            if key in text:
                return label
    return "Fase de Grupos"


def http_json(url: str, params: dict = None, session=None):
    """GET → dict JSON, ou None em caso de erro (logado no stderr).
    Reaproveita a requests.Session passada (Keep-Alive) quando houver."""
    try:
        caller = session if session is not None else requests
        r = caller.get(url, headers=HEADERS, params=params, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        warn(f"[live_scores] erro ao buscar {url} {params or ''}: {e}")
        return None


# ─── Gols e cartões (endpoint summary) ────────────────────────────────────────

def fetch_events(event_id: str, home_id: str, away_id: str, session=None) -> dict:
    """
    Gols e cartões de uma partida (uma única chamada ao summary).
    Retorno: {"goals": [...], "cards": [...]}, cada lista em ordem cronológica.

    Gol:    {minute, minute_value, side('A'|'B'), team, scorer, assist,
             kind('goal'|'penalty'|'own_goal'), text}
    Cartão: {minute, minute_value, side('A'|'B'), team, player, kind('yellow'|'red')}
    """
    data = http_json(f"{SUMMARY}", params={"event": event_id}, session=session)
    if not data:
        return {"goals": [], "cards": []}

    def side_of(ev):
        tid = str((ev.get("team", {}) or {}).get("id", ""))
        if tid == str(home_id):
            return "A"
        if tid == str(away_id):
            return "B"
        return None

    goals, cards = [], []
    for ev in data.get("keyEvents", []) or []:
        if not ev:
            continue
        type_text = (ev.get("type", {}) or {}).get("text", "") or ""
        low = type_text.lower()
        clock = (ev.get("clock", {}) or {}).get("displayValue", "")
        team_name = map_team((ev.get("team", {}) or {}).get("displayName", ""))
        participants = ev.get("participants", []) or []

        # ── Cartões ──
        if "card" in low:
            player = None
            if participants and participants[0]:
                player = (participants[0].get("athlete", {}) or {}).get("displayName")
            cards.append({
                "minute": clock,
                "minute_value": parse_minute(clock),
                "side": side_of(ev),
                "team": team_name,
                "player": player,
                "kind": "red" if "red" in low else "yellow",
            })
            continue

        # ── Gols ── (ignora pênaltis perdidos e a disputa de pênaltis)
        if not ev.get("scoringPlay") or ev.get("shootout"):
            continue
        if "own" in low:
            kind = "own_goal"
        elif "penalty" in low:
            kind = "penalty"
        else:
            kind = "goal"

        scorer = assist = None
        if participants and participants[0]:
            scorer = (participants[0].get("athlete", {}) or {}).get("displayName")
        if len(participants) > 1 and participants[1]:
            assist = (participants[1].get("athlete", {}) or {}).get("displayName")
        if not scorer:
            scorer = (ev.get("shortText") or "").replace(" Goal", "").strip() or None

        goals.append({
            "minute": clock,
            "minute_value": parse_minute(clock),
            "side": side_of(ev),
            "team": team_name,
            "scorer": scorer,
            "assist": assist,
            "kind": kind,
            "text": ev.get("text", ""),
        })

    keyfn = lambda x: (x["minute_value"] is None, x["minute_value"] or 0)
    goals.sort(key=keyfn)
    cards.sort(key=keyfn)
    return {"goals": goals, "cards": cards}


# ─── Construção de um jogo ────────────────────────────────────────────────────

def status_block(status_type: dict, clock: str, shootout: bool, detail: str) -> dict:
    """Normaliza o status do jogo, com um rótulo amigável em português."""
    state = status_type.get("state", "")          # pre | in | post
    live = state == "in"
    finished = state == "post"

    if state == "pre":
        label = "Agendado"
    elif live:
        label = f"Ao vivo · {clock}" if clock else "Ao vivo"
    elif finished:
        label = "Encerrado"
        if shootout or "pen" in (detail or "").lower():
            label = "Encerrado (pênaltis)"
        elif "et" in (detail or "").lower() or "aet" in (detail or "").lower():
            label = "Encerrado (prorrogação)"
    else:
        label = status_type.get("description", "") or state

    return {
        "state": state,
        "live": live,
        "finished": finished,
        "label": label,
        "minute": parse_minute(clock),
        "clock": clock,
        "detail": detail,
        "description": status_type.get("description", ""),
        "espn_status": status_type.get("name", ""),
    }


def build_match(event: dict, include_goals: bool = True, session=None) -> dict:
    """
    Converte 1 evento da ESPN no formato JSON do feed.

    Formato de cada jogo:
        {
          "id": "633850",
          "round": "Final",
          "date": "2022-12-18T12:00",        # horário de São Paulo
          "status": { ...status_block... },
          "team_a": {"name": "🇦🇷 Argentina", "raw": "Argentina", "score": 3},
          "team_b": {"name": "🇫🇷 França",     "raw": "France",    "score": 3},
          "penalties": {"a": 4, "b": 2} | None,   # só se houve disputa
          "goals": [ ...ver fetch_events()... ],  # [] se --no-goals ou sem gols
          "cards": [ ...ver fetch_events()... ]   # cartões amarelos/vermelhos
        }
    """
    comp = (event.get("competitions") or [{}])[0] or {}
    competitors = comp.get("competitors", []) or []
    home = next((c for c in competitors if c and c.get("homeAway") == "home"),
               competitors[0] if competitors else {}) or {}
    away = next((c for c in competitors if c and c.get("homeAway") == "away"),
               competitors[1] if len(competitors) > 1 else {}) or {}

    home_team = home.get("team", {}) or {}
    away_team = away.get("team", {}) or {}
    home_id = home_team.get("id", "")
    away_id = away_team.get("id", "")

    def score(c):
        s = c.get("score")
        try:
            return int(s)
        except (TypeError, ValueError):
            return None

    def pens(c):
        s = c.get("shootoutScore")
        try:
            return int(s)
        except (TypeError, ValueError):
            return None

    status_obj = comp.get("status") or {}
    status_type = status_obj.get("type") or {}
    clock = status_obj.get("displayClock", "") or ""
    detail = status_type.get("detail", "") or ""
    pen_a, pen_b = pens(home), pens(away)
    shootout = pen_a is not None and pen_b is not None

    state = status_type.get("state", "")
    goals, cards = [], []
    if include_goals and state in ("in", "post"):
        evs = fetch_events(event.get("id", ""), home_id, away_id, session=session)
        goals, cards = evs["goals"], evs["cards"]

    return {
        "id": event.get("id", ""),
        "round": round_name(comp),
        "date": to_sao_paulo(event.get("date", "")),
        "date_utc": event.get("date", ""),   # ISO UTC cru (ex.: 2026-06-25T19:00Z) p/ o front localizar no fuso do usuário
        "status": status_block(status_type, clock, shootout, detail),
        "team_a": {"name": map_team(home_team.get("displayName", "")),
                   "raw": home_team.get("displayName", ""), "score": score(home)},
        "team_b": {"name": map_team(away_team.get("displayName", "")),
                   "raw": away_team.get("displayName", ""), "score": score(away)},
        "penalties": {"a": pen_a, "b": pen_b} if shootout else None,
        "goals": goals,
        "cards": cards,
    }


# ─── Snapshot (a função que a dev importa) ────────────────────────────────────

def snapshot(date: str = None, include_goals: bool = True) -> dict:
    """
    Devolve um dict com todos os jogos de um dia (padrão: hoje), pronto para
    `jsonify(...)` numa rota Flask.

    Args:
        date: "YYYYMMDD". Se None, usa a data de hoje (fuso de São Paulo).
        include_goals: se False, não busca os gols (mais rápido / menos chamadas).

    Retorno:
        {
          "generated_at": "2026-06-19T18:42:05-03:00",
          "date": "20260619",
          "source": "ESPN",
          "match_count": 4,
          "live_count": 1,
          "matches": [ ...ver build_match()... ]
        }
    """
    if not date:
        now = datetime.now(SAO_PAULO) if SAO_PAULO else datetime.now()
        date = now.strftime("%Y%m%d")

    # Uma única requests.Session pro snapshot inteiro: reaproveita a conexão
    # TCP/TLS (Keep-Alive) nas N chamadas paralelas ao summary, em vez de abrir e
    # fechar uma conexão por jogo. (Session é thread-safe pra requests.)
    matches = []
    with requests.Session() as session:
        data = http_json(SCOREBOARD, params={"dates": date, "limit": 50}, session=session)
        events = (data or {}).get("events", []) or []

        # Cada jogo ao vivo/encerrado faz 1 GET no summary (gols/cartões). Em série
        # isso prenderia o worker por N×latência; busca em paralelo e reordena no fim.
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(build_match, ev, include_goals, session) for ev in events]
            for ev, future in zip(events, futures):
                try:
                    matches.append(future.result())
                except Exception as e:
                    event_id = ev.get("id") if ev else "desconhecido"
                    warn(f"[live_scores] erro ao montar jogo {event_id}: {e}")

    matches.sort(key=lambda m: m["date"])
    now = datetime.now(SAO_PAULO) if SAO_PAULO else datetime.now(timezone.utc)
    return {
        "generated_at": now.isoformat(timespec="seconds"),
        "date": date,
        "source": "ESPN",
        "match_count": len(matches),
        "live_count": sum(1 for m in matches if m["status"]["live"]),
        "matches": matches,
        "error": None if data is not None else "falha ao consultar a API da ESPN",
    }


# ─── CLI ──────────────────────────────────────────────────────────────────────

def _emit(payload: dict, compact: bool) -> None:
    if compact:
        print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), flush=True)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2), flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Feed JSON de placares ao vivo da Copa do Mundo (API ESPN, grátis).")
    ap.add_argument("--date", help="Dia no formato YYYYMMDD (padrão: hoje).")
    ap.add_argument("--watch", action="store_true",
                    help="Loop contínuo: imprime um JSON por ciclo (JSONL).")
    ap.add_argument("--interval", type=int, default=DEFAULT_INTERVAL,
                    help=f"Segundos entre atualizações no --watch (padrão {DEFAULT_INTERVAL}).")
    ap.add_argument("--no-goals", action="store_true",
                    help="Não busca os detalhes de gols (mais rápido).")
    ap.add_argument("--compact", action="store_true",
                    help="JSON em uma linha só.")
    args = ap.parse_args()

    include_goals = not args.no_goals

    if not args.watch:
        _emit(snapshot(date=args.date, include_goals=include_goals), args.compact)
        return

    # Modo watch: no --watch a saída é JSONL (1 objeto JSON compacto por linha),
    # ideal para consumir como stream. Ctrl+C encerra.
    warn(f"[live_scores] modo watch — atualizando a cada {args.interval}s "
         f"(Ctrl+C para sair)")
    try:
        while True:
            _emit(snapshot(date=args.date, include_goals=include_goals), compact=True)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        warn("[live_scores] encerrado.")


if __name__ == "__main__":
    main()
