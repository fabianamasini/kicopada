"""
Script para popular o banco de dados com dados mockados (volume realista).
Execute com: python scripts/seed.py

Segue as MESMAS regras do front-end, para os dados ficarem o mais próximos do real:
  - As PARTIDAS NÃO são inventadas: vêm da mesma fonte que o app usa no boot —
    o calendário oficial da Copa puxado da ESPN por match_sync.sync_matches().
    O seed só cuida dos dados de teste construídos POR CIMA delas.
  - Times vêm da fonte canônica (src/utils.teams): nomes oficiais com bandeira + grupo.
  - Senhas respeitam is_password_strong e usuários são is_admin=False (como no signup).
  - Partidas já começadas (antes de agora) recebem um placar aleatório para
    simular jogos finalizados e gerar pontuação — só elas; as demais ficam em aberto.
  - Odds NÃO são inventadas: são calculadas pelo ScoringController a partir da
    distribuição dos palpites — exatamente como o app faz ao cadastrar um palpite,
    e só existem para partidas que receberam ao menos 1 palpite.
  - Pontos são DERIVADOS pelo scoring a partir dos resultados.

Volume gerado:
  - 20 usuários.
  - Partidas: as que a ESPN devolver (precisa de rede; sem rede, nenhuma é criada).
  - Partidas já começadas: placar aleatório (finalizadas) + odds; geram pontuação.
  - Partidas de hoje/futuras: placar em aberto; futuras podem ter ou não palpites.
  - Quantidade de palpites por partida e os placares palpitados são aleatórios.
"""

import os
import sys

# Garante que a raiz do projeto esteja no path (o script vive em scripts/)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import random
from datetime import datetime

import pytz
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

from app import app
from match_sync import sync_matches                          # mesma fonte de partidas do boot (ESPN)
from models import db, User, Match, Guesses, Teams, Odds
from src.utils import teams as CANONICAL_TEAMS              # fonte canônica usada pelo front-end
from src.controllers.scoring import ScoringController         # mesma lógica de odds/pontos do app
from src.controllers.utils import is_password_strong          # mesma regra de senha do signup

load_dotenv()

DATE_FMT = "%Y-%m-%dT%H:%M"        # formato canônico (igual ao input datetime-local do form)
DEFAULT_PASSWORD = "Senha@123"     # precisa passar em is_password_strong

NUM_USERS = 20
NAMED_USERS = ["mario", "megu", "fabs", "diabo", "mbappe", "dembele"]


def seed_database():
    """Popula o banco com volume, seguindo as regras reais do app."""

    with app.app_context():
        db.drop_all()
        db.create_all()
        scoring = ScoringController()
        assert is_password_strong(DEFAULT_PASSWORD), "A senha padrão não passa na regra real do signup!"

        saopaulo_tz = pytz.timezone('America/Sao_Paulo')
        now = datetime.now(saopaulo_tz)
        today = now.date()

        print("🌱 Iniciando seed do banco de dados...")

        # ==================== USUÁRIOS ====================
        # Mesmas regras do signup: senha forte + hash + is_admin=False.
        extra = [f"user{n:02d}" for n in range(len(NAMED_USERS) + 1, NUM_USERS + 1)]
        usernames = NAMED_USERS + extra
        users = []
        for username in usernames:
            users.append(User(
                username=username,
                password_hash=generate_password_hash(DEFAULT_PASSWORD),
                is_admin=False,
                points=0,
            ))
        db.session.add_all(users)
        db.session.commit()
        print(f"\n📝 {len(users)} usuários criados")

        # ==================== TIMES (fonte canônica) ====================
        for name, group in CANONICAL_TEAMS.items():
            db.session.add(Teams(name=name, group=group))
        db.session.commit()
        print(f"⚽ {len(CANONICAL_TEAMS)} times criados a partir da lista canônica")

        # ==================== PARTIDAS (fonte real: ESPN, igual ao boot) ====================
        # Não inventamos jogos: puxamos o calendário oficial da Copa pela mesma função
        # que o app roda no boot. Precisa de rede; se a ESPN falhar, nenhuma partida é
        # criada (e o resto do seed simplesmente não terá palpites/odds/pontos).
        inserted = sync_matches(log=lambda _m: None)
        all_matches = Match.query.all()
        if not all_matches:
            print("⚠️  Nenhuma partida disponível (ESPN indisponível?). "
                  "Sem partidas não há palpites, odds nem pontuação.")

        def _kickoff(m):
            """datetime da partida no fuso de São Paulo, ou None se data inválida."""
            try:
                return saopaulo_tz.localize(datetime.strptime(m.date, DATE_FMT))
            except (ValueError, TypeError):
                return None

        # Classifica cada partida em relação a AGORA: já começou / hoje / futura.
        matches = []  # tuplas (Match, is_past, is_future)
        for m in all_matches:
            ko = _kickoff(m)
            is_past = bool(ko) and ko < now
            is_future = bool(ko) and ko.date() > today
            # Partidas já começadas viram "finalizadas" com placar aleatório, para
            # gerar pontuação real (a ESPN não traz placar pelo sync). Só fase de
            # grupos — não há mata-mata no passado neste momento da Copa.
            if is_past and not m.is_knockout:
                m.score_a = random.randint(0, 4)
                m.score_b = random.randint(0, 4)
            matches.append((m, is_past, is_future))
        db.session.commit()
        n_past = sum(1 for _, p, _ in matches if p)
        n_future = sum(1 for _, _, f in matches if f)
        n_today = len(matches) - n_past - n_future
        print(f"🎮 {len(matches)} partidas da ESPN ({inserted} inseridas agora) — "
              f"{n_past} já começaram, {n_today} hoje, {n_future} futuras")

        # ==================== PALPITES (quantidade e placares aleatórios) ====================
        matches_with_guesses = set()
        for m, is_past, is_future in matches:
            # futuras podem NÃO ter palpites
            if is_future and random.random() < 0.30:
                continue
            # encerradas/de hoje: muita gente já palpitou; futuras (em aberto): menos gente
            if is_future:
                k = random.randint(3, max(3, len(users) // 2 + 4))
            else:
                k = random.randint(8, len(users))
            for user in random.sample(users, k):
                db.session.add(Guesses(
                    user_id=user.id,
                    match_id=m.id,
                    pred_a=random.randint(0, 4),
                    pred_b=random.randint(0, 4),
                    is_knockout=m.is_knockout,
                ))
            matches_with_guesses.add(m.id)
        db.session.commit()
        print(f"🎯 {Guesses.query.count()} palpites criados (quantidade aleatória por partida)")

        # ==================== ODDS (calculadas, só onde há palpites) ====================
        # Mesma chamada que o app faz ao cadastrar um palpite. Sem palpites = sem odds,
        # como no app (a linha de Odds só nasce quando o primeiro palpite é feito).
        for m, _, _ in matches:
            if m.id in matches_with_guesses:
                scoring.calculate_odds_for_match(m.id)
        print(f"💰 Odds calculadas para {Odds.query.count()} partidas (todas em [1.0, 2.0])")

        # ==================== PONTOS (derivados dos resultados) ====================
        # As partidas anteriores têm placar -> o scoring transforma os palpites em pontos.
        for user in users:
            scoring.update_user_points(user.id, commit=False)
        db.session.commit()

        # ==================== RESUMO ====================
        ranking = User.query.order_by(User.points.desc()).limit(5).all()
        print("\n✅ Seed concluído com sucesso!")
        print("\n📋 Dados criados:")
        print(f"  - {User.query.count()} usuários")
        print(f"  - {Teams.query.count()} times (lista canônica)")
        print(f"  - {Match.query.count()} partidas ({n_past} anteriores / {n_today} hoje / {n_future} futuras)")
        print(f"  - {Odds.query.count()} registros de odds (calculadas)")
        print(f"  - {Guesses.query.count()} palpites")
        print("\n🏆 Top 5 do ranking (pontuação derivada dos resultados):")
        for i, u in enumerate(ranking, 1):
            print(f"  {i}º {u.username} — {u.points} pts")

        print("\n🔑 Credenciais de teste (senha forte, válida no signup):")
        print(f"  - Usuários: {', '.join(usernames)}")
        print(f"  - Senha (todos): {DEFAULT_PASSWORD}")
        print("\nℹ️  Todos são is_admin=False (como no cadastro real). Para testar telas")
        print("   de admin, promova um usuário manualmente no banco.")


if __name__ == "__main__":
    seed_database()
