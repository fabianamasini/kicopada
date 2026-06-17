"""
Script para gerar dados mockados aleatoriamente em maior volume.
Útil para testes de performance.
Execute com: python scripts/seed_random.py
"""

import os
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv
from app import app
from models import db, User, Match, Guesses, Teams, Odds
from werkzeug.security import generate_password_hash

load_dotenv()

def seed_random_data(num_users=50, num_matches=20):
    """Popula o banco com dados aleatórios."""

    with app.app_context():
        print(f"🌱 Gerando {num_users} usuários e {num_matches} partidas...")

        # ==================== CRIAR TIMES (se não existirem) ====================
        teams_list = [
            "Brasil", "Espanha", "Alemanha", "França", "Argentina",
            "Itália", "Portugal", "Holanda", "Inglaterra", "Bélgica"
        ]

        for team_name in teams_list:
            if not Teams.query.filter_by(name=team_name).first():
                team = Teams(name=team_name, group=random.choice(['A', 'B', 'C', 'D']))
                db.session.add(team)

        db.session.commit()
        all_teams = Teams.query.all()

        # ==================== CRIAR USUÁRIOS ====================
        print(f"\n👥 Criando {num_users} usuários...")

        users = []
        for i in range(num_users):
            username = f"user_{i+1:03d}"
            if not User.query.filter_by(username=username).first():
                user = User(
                    username=username,
                    password_hash=generate_password_hash("senha123"),
                    is_admin=False,
                    points=random.randint(0, 500)
                )
                db.session.add(user)
                users.append(user)

        db.session.commit()
        users = User.query.order_by(User.id.desc()).limit(num_users).all()
        print(f"✓ {len(users)} usuários criados")

        # ==================== CRIAR PARTIDAS ====================
        print(f"\n⚽ Criando {num_matches} partidas...")

        matches = []
        base_date = datetime.now() + timedelta(hours=24)

        for i in range(num_matches):
            team_a = random.choice(all_teams)
            team_b = random.choice(all_teams)

            # Garante que os times são diferentes
            while team_b.id == team_a.id:
                team_b = random.choice(all_teams)

            match_date = base_date + timedelta(days=random.randint(0, 10), hours=random.randint(0, 23))

            existing_match = Match.query.filter_by(
                team_a=team_a.name,
                team_b=team_b.name
            ).first()

            if not existing_match:
                match = Match(
                    team_a=team_a.name,
                    team_b=team_b.name,
                    date=match_date.isoformat(),
                    round=random.choice(["Fase de Grupos", "Oitavas", "Quartas", "Semi"]),
                    is_knockout=random.choice([True, False])
                )
                db.session.add(match)
                matches.append(match)

        db.session.commit()
        matches = Match.query.order_by(Match.id.desc()).limit(num_matches).all()
        print(f"✓ {len(matches)} partidas criadas")

        # ==================== CRIAR ODDS ====================
        print(f"\n💰 Criando odds para as partidas...")

        for match in matches:
            if not Odds.query.filter_by(match_id=match.id).first():
                odd = Odds(
                    match_id=match.id,
                    team_a_odds=round(random.uniform(1.50, 3.50), 2),
                    team_b_odds=round(random.uniform(1.50, 3.50), 2),
                    draw_odds=round(random.uniform(2.50, 4.50), 2)
                )
                db.session.add(odd)

        db.session.commit()
        print(f"✓ Odds criadas")

        # ==================== CRIAR PALPITES ====================
        print(f"\n🎯 Criando palpites aleatórios...")

        guess_count = 0
        for user in users:
            # Cada usuário faz palpites em 30-60% das partidas
            num_guesses = random.randint(int(len(matches) * 0.3), int(len(matches) * 0.6))
            selected_matches = random.sample(matches, min(num_guesses, len(matches)))

            for match in selected_matches:
                if not Guesses.query.filter_by(user_id=user.id, match_id=match.id).first():
                    guess = Guesses(
                        user_id=user.id,
                        match_id=match.id,
                        pred_a=random.randint(0, 5),
                        pred_b=random.randint(0, 5),
                        is_knockout=match.is_knockout
                    )
                    db.session.add(guess)
                    guess_count += 1

        db.session.commit()
        print(f"✓ {guess_count} palpites criados")

        # ==================== RESUMO ====================
        print("\n✅ Seed aleatório concluído!")
        print(f"\n📋 Dados criados:")
        print(f"  - {User.query.count()} usuários")
        print(f"  - {Teams.query.count()} times")
        print(f"  - {Match.query.count()} partidas")
        print(f"  - {Odds.query.count()} registros de odds")
        print(f"  - {Guesses.query.count()} palpites")

if __name__ == "__main__":
    try:
        num_users = int(input("Quantos usuários criar? (padrão: 50): ") or "50")
        num_matches = int(input("Quantas partidas criar? (padrão: 20): ") or "20")
        seed_random_data(num_users, num_matches)
    except ValueError:
        print("❌ Entrada inválida")
