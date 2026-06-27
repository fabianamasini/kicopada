#!/usr/bin/env python3
"""
match_sync.py — Cadastro AUTOMÁTICO das partidas da Copa do Mundo 2026.

Busca o calendário oficial na API pública da ESPN (grátis, sem chave) e INSERE
no banco apenas os jogos que ainda não existem. É idempotente: rodar de novo não
duplica nada e NUNCA altera placar, fase ou qualquer edição manual de um jogo já
cadastrado — só preenche o que está faltando.

Pensado para rodar sozinho no boot do app (no mesmo ponto onde o admin e a tabela
Teams já são semeados em app.py). Também roda pela linha de comando:

    python match_sync.py             # cadastra os jogos que faltam
    python match_sync.py --dry-run   # mostra o que faria, sem gravar nada

Notas de projeto:
  • Uma única chamada HTTP (intervalo de datas) → boot rápido.
  • Sem dependência nova: usa só urllib da stdlib (requests não está no
    requirements e não está disponível em produção).
  • Times de mata-mata ainda não definidos ("Group A Winner", "Round of 32 1
    Winner", "Third Place Group..."), não estão no mapa e são ignorados de
    propósito — entram sozinhos quando a ESPN confirma os classificados e o app
    sincroniza de novo no próximo boot.
  • A fase (round) é derivada da DATA, pelo calendário oficial da Copa 2026
    (datas da ESPN). É autossuficiente de propósito — não depende de nenhuma
    outra feature/branch.
  • Resiliente: se a API falhar, não lança exceção — o app sobe normalmente e
    nenhum jogo é cadastrado naquele boot.
"""

import os
import sys
import json
from datetime import datetime
from urllib.request import Request, urlopen

import pytz

from models import db, Match

# ─── API pública da ESPN (sem chave) ──────────────────────────────────────────
ESPN_SCOREBOARD = (
    "https://site.api.espn.com/apis/site/v2/sports/soccer/FIFA.WORLD/scoreboard"
)
# Intervalo coberto pela Copa 2026 (abertura 11/06; margem após a final 19/07).
WC_START = "20260611"
WC_END = "20260720"
# Timeout curto: roda no boot e a falha é não-fatal/idempotente (se a ESPN estiver
# lenta, simplesmente cadastra no próximo boot) — não vale travar o deploy.
REQUEST_TIMEOUT = 8

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}

SAO_PAULO = pytz.timezone("America/Sao_Paulo")

# ─── Nomes da ESPN (chamada por intervalo) → formato canônico do app ──────────
# As chaves são EXATAMENTE os displayName que o endpoint devolve (atenção a
# "Bosnia-Herzegovina", "Congo DR", "Türkiye"). Os valores espelham as chaves de
# `teams` em src/utils.py, para que um jogo cadastrado aqui seja idêntico a um
# cadastrado à mão pelo admin.
TEAM_MAP = {
    "Algeria":            "🇩🇿 Argélia",
    "Argentina":          "🇦🇷 Argentina",
    "Australia":          "🇦🇺 Austrália",
    "Austria":            "🇦🇹 Áustria",
    "Belgium":            "🇧🇪 Bélgica",
    "Bosnia-Herzegovina": "🇧🇦 Bósnia e Herzegovina",
    "Brazil":             "🇧🇷 Brasil",
    "Canada":             "🇨🇦 Canadá",
    "Cape Verde":         "🇨🇻 Cabo Verde",
    "Colombia":           "🇨🇴 Colômbia",
    "Congo DR":           "🇨🇩 RD do Congo",
    "Croatia":            "🇭🇷 Croácia",
    "Curaçao":            "🇨🇼 Curaçau",
    "Czechia":            "🇨🇿 República Tcheca",
    "Ecuador":            "🇪🇨 Equador",
    "Egypt":              "🇪🇬 Egito",
    "England":            "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inglaterra",
    "France":             "🇫🇷 França",
    "Germany":            "🇩🇪 Alemanha",
    "Ghana":              "🇬🇭 Gana",
    "Haiti":              "🇭🇹 Haiti",
    "Iran":               "🇮🇷 Irã",
    "Iraq":               "🇮🇶 Iraque",
    "Ivory Coast":        "🇨🇮 Costa do Marfim",
    "Japan":              "🇯🇵 Japão",
    "Jordan":             "🇯🇴 Jordânia",
    "Mexico":             "🇲🇽 México",
    "Morocco":            "🇲🇦 Marrocos",
    "Netherlands":        "🇳🇱 Holanda",
    "New Zealand":        "🇳🇿 Nova Zelândia",
    "Norway":             "🇳🇴 Noruega",
    "Panama":             "🇵🇦 Panamá",
    "Paraguay":           "🇵🇾 Paraguai",
    "Portugal":           "🇵🇹 Portugal",
    "Qatar":              "🇶🇦 Catar",
    "Saudi Arabia":       "🇸🇦 Arábia Saudita",
    "Scotland":           "🏴󠁧󠁢󠁳󠁣󠁴󠁿 Escócia",
    "Senegal":            "🇸🇳 Senegal",
    "South Africa":       "🇿🇦 África do Sul",
    "South Korea":        "🇰🇷 Coreia do Sul",
    "Spain":              "🇪🇸 Espanha",
    "Sweden":             "🇸🇪 Suécia",
    "Switzerland":        "🇨🇭 Suíça",
    "Tunisia":            "🇹🇳 Tunísia",
    "Türkiye":            "🇹🇷 Turquia",
    "United States":      "🇺🇸 EUA",
    "Uruguay":            "🇺🇾 Uruguai",
    "Uzbekistan":         "🇺🇿 Uzbequistão",
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _map_team(raw: str):
    """displayName da ESPN → nome canônico do app; None se ainda não definido."""
    if not raw:
        return None
    if raw in TEAM_MAP:
        return TEAM_MAP[raw]
    for k, v in TEAM_MAP.items():        # tolera variação de caixa
        if k.lower() == raw.lower():
            return v
    return None


def _phase_for_date(iso: str) -> str:
    """Fase da Copa a partir da data (YYYY-MM-DD), pelo calendário oficial 2026.
    Comparação lexicográfica de datas ISO. Fora dos intervalos = Fase de Grupos
    (11–27/jun, e fallback seguro).

    Os rótulos espelham EXATAMENTE os de `phases` em src/utils.py (ex.: Round of
    32 = '16-avos de Final'; semis = 'Semifinais'), pra um jogo cadastrado aqui
    ser idêntico a um cadastrado à mão pelo admin. A disputa de 3º lugar não tem
    rótulo canônico — usa um descritivo (e fica is_knockout=True mesmo assim)."""
    if "2026-06-28" <= iso <= "2026-07-03":
        return "16-avos de Final"
    if "2026-07-04" <= iso <= "2026-07-07":
        return "Oitavas de Final"
    if iso in ("2026-07-09", "2026-07-10", "2026-07-11"):
        return "Quartas de Final"
    if iso in ("2026-07-14", "2026-07-15"):
        return "Semifinais"
    if iso == "2026-07-18":
        return "Disputa do 3º Lugar"
    if iso == "2026-07-19":
        return "Final"
    return "Fase de Grupos"


def _utc_to_sp(utc_iso: str) -> str:
    """'2026-06-16T19:00Z' → 'YYYY-MM-DDTHH:MM' no fuso de São Paulo (formato Match.date)."""
    if not utc_iso:
        return ""
    try:
        dt = datetime.fromisoformat(utc_iso.replace("Z", "+00:00")).astimezone(SAO_PAULO)
        return dt.strftime("%Y-%m-%dT%H:%M")
    except (ValueError, TypeError):
        return ""


def _fetch_events() -> list:
    """Uma chamada à ESPN cobrindo toda a Copa. Pode lançar (rede/JSON)."""
    url = f"{ESPN_SCOREBOARD}?dates={WC_START}-{WC_END}&limit=200"
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("events", []) or []


def _parse_event(event: dict):
    """Evento da ESPN → dict pronto p/ Match, ou None se algum time não está definido."""
    if not event:
        return None
    comp = (event.get("competitions") or [{}])[0] or {}
    competitors = comp.get("competitors") or []
    if len(competitors) < 2:
        return None

    home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
    away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])
    team_a = _map_team((home.get("team") or {}).get("displayName", ""))
    team_b = _map_team((away.get("team") or {}).get("displayName", ""))
    if not team_a or not team_b:
        return None                      # mata-mata ainda não definido → ignora

    date_sp = _utc_to_sp(event.get("date", ""))
    if not date_sp:
        return None

    phase = _phase_for_date(date_sp[:10])
    return {
        "team_a": team_a,
        "team_b": team_b,
        "date": date_sp,
        "round": phase,
        "is_knockout": phase != "Fase de Grupos",
    }


# ─── Sincronização (a função chamada no boot do app) ──────────────────────────

def sync_matches(dry_run: bool = False, log=print) -> int:
    """Cadastra os jogos que ainda não existem no banco. Idempotente.

    Deve ser chamada dentro de um app_context (o boot do app já fornece um).
    Retorna a quantidade de partidas inseridas. Falha de rede não lança: apenas
    registra um aviso e retorna 0, para o app subir normalmente.
    """
    try:
        events = _fetch_events()
    except Exception as e:
        log(f"[match_sync] API indisponível; nenhum jogo cadastrado neste boot ({e}).")
        return 0

    inserted = 0
    for event in events:
        parsed = _parse_event(event)
        if not parsed:
            continue

        a, b = parsed["team_a"], parsed["team_b"]
        # Existência ignorando mando de campo (evita duplicar um jogo já cadastrado
        # à mão pelo admin caso a ordem dos times venha invertida).
        exists = Match.query.filter(
            db.or_(
                db.and_(Match.team_a == a, Match.team_b == b),
                db.and_(Match.team_a == b, Match.team_b == a),
            )
        ).first()
        if exists:
            continue

        log(f"[match_sync] + {a} x {b}  {parsed['date']}  [{parsed['round']}]")
        inserted += 1
        if not dry_run:
            db.session.add(Match(
                team_a=a,
                team_b=b,
                date=parsed["date"],
                round=parsed["round"],
                is_knockout=parsed["is_knockout"],
            ))

    if inserted and not dry_run:
        try:
            db.session.commit()
        except Exception:
            # Rollback pra não deixar a sessão num estado quebrado — como isto roda
            # no boot, uma sessão pendente poderia derrubar requisições seguintes.
            db.session.rollback()
            raise
    return inserted


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    try:
        sys.stdout.reconfigure(encoding="utf-8")   # emojis das bandeiras no Windows
    except Exception:
        pass

    ap = argparse.ArgumentParser(
        description="Cadastro automático das partidas da Copa 2026 (API ESPN, grátis).")
    ap.add_argument("--dry-run", action="store_true",
                    help="Mostra os jogos que seriam cadastrados, sem gravar.")
    args = ap.parse_args()

    # Evita o sync rodar duas vezes: o import do app dispara o boot, então o
    # desligamos ali e fazemos a chamada explícita logo abaixo.
    os.environ.setdefault("AUTO_SYNC_MATCHES", "0")
    from app import app

    with app.app_context():
        n = sync_matches(dry_run=args.dry_run)

    verb = "seriam cadastrada(s) (dry-run)" if args.dry_run else "cadastrada(s)"
    print(f"\n✓ {n} partida(s) {verb}.")
