"""
Script para popular o banco de dados com dados mockados.
Execute com: python seed.py
"""

import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from app import app
from models import db, User, Match, Guesses, Teams, Odds
from werkzeug.security import generate_password_hash

load_dotenv()

def seed_database():
    """Popula o banco de dados com dados de exemplo."""

    with app.app_context():
        # Limpa dados existentes (opcional - descomente se quiser limpar)
        # db.drop_all()
        # db.create_all()

        print("🌱 Iniciando seed do banco de dados...")

        # ==================== CRIAR USUÁRIOS ====================
        print("\n📝 Criando usuários...")

        users_data = [
            {"username": "alice", "password": "senha123"},
            {"username": "bob", "password": "senha123"},
            {"username": "carlos", "password": "senha123"},
            {"username": "diana", "password": "senha123"},
            {"username": "eva", "password": "senha123"},
        ]

        users = []
        for user_data in users_data:
            # Verifica se o usuário já existe
            existing_user = User.query.filter_by(username=user_data["username"]).first()
            if not existing_user:
                user = User(
                    username=user_data["username"],
                    password_hash=generate_password_hash(user_data["password"]),
                    is_admin=False,
                    points=0
                )
                db.session.add(user)
                users.append(user)
                print(f"  ✓ Usuário '{user_data['username']}' criado")
            else:
                users.append(existing_user)
                print(f"  - Usuário '{user_data['username']}' já existe")

        db.session.commit()

        # ==================== CRIAR TIMES ====================
        print("\n⚽ Criando times...")

        teams_data = [
            {"name": "Brasil", "group": "A"},
            {"name": "Espanha", "group": "A"},
            {"name": "Alemanha", "group": "B"},
            {"name": "França", "group": "B"},
            {"name": "Argentina", "group": "C"},
            {"name": "Itália", "group": "C"},
            {"name": "Portugal", "group": "D"},
            {"name": "Holanda", "group": "D"},
        ]

        for team_data in teams_data:
            existing_team = Teams.query.filter_by(name=team_data["name"]).first()
            if not existing_team:
                team = Teams(name=team_data["name"], group=team_data["group"])
                db.session.add(team)
                print(f"  ✓ Time '{team_data['name']}' criado")
            else:
                print(f"  - Time '{team_data['name']}' já existe")

        db.session.commit()

        # ==================== CRIAR JOGOS ====================
        print("\n🎮 Criando partidas...")

        # Datas futuras (próximos 7 dias)
        base_date = datetime.now() + timedelta(hours=24)

        matches_data = [
            {
                "team_a": "Brasil",
                "team_b": "Espanha",
                "date": base_date.replace(hour=19, minute=0).isoformat(),
                "round": "Fase de Grupos",
                "is_knockout": False
            },
            {
                "team_a": "Alemanha",
                "team_b": "França",
                "date": (base_date + timedelta(days=1)).replace(hour=20, minute=30).isoformat(),
                "round": "Fase de Grupos",
                "is_knockout": False
            },
            {
                "team_a": "Argentina",
                "team_b": "Itália",
                "date": (base_date + timedelta(days=2)).replace(hour=17, minute=0).isoformat(),
                "round": "Fase de Grupos",
                "is_knockout": False
            },
            {
                "team_a": "Portugal",
                "team_b": "Holanda",
                "date": (base_date + timedelta(days=3)).replace(hour=21, minute=0).isoformat(),
                "round": "Fase de Grupos",
                "is_knockout": False
            },
            {
                "team_a": "Brasil",
                "team_b": "Alemanha",
                "date": (base_date + timedelta(days=4)).replace(hour=19, minute=0).isoformat(),
                "round": "Oitavas de Final",
                "is_knockout": True
            },
        ]

        matches = []
        for match_data in matches_data:
            existing_match = Match.query.filter_by(
                team_a=match_data["team_a"],
                team_b=match_data["team_b"],
                date=match_data["date"]
            ).first()

            if not existing_match:
                match = Match(
                    team_a=match_data["team_a"],
                    team_b=match_data["team_b"],
                    date=match_data["date"],
                    round=match_data["round"],
                    is_knockout=match_data["is_knockout"]
                )
                db.session.add(match)
                matches.append(match)
                print(f"  ✓ Partida '{match_data['team_a']} vs {match_data['team_b']}' criada")
            else:
                matches.append(existing_match)
                print(f"  - Partida '{match_data['team_a']} vs {match_data['team_b']}' já existe")

        db.session.commit()

        # ==================== CRIAR ODDS ====================
        print("\n💰 Criando odds...")

        odds_data = [
            {"match_idx": 0, "team_a_odds": 2.15, "team_b_odds": 1.75, "draw_odds": 3.40},
            {"match_idx": 1, "team_a_odds": 1.95, "team_b_odds": 1.90, "draw_odds": 3.60},
            {"match_idx": 2, "team_a_odds": 2.30, "team_b_odds": 1.65, "draw_odds": 3.50},
            {"match_idx": 3, "team_a_odds": 2.10, "team_b_odds": 1.80, "draw_odds": 3.55},
            {"match_idx": 4, "team_a_odds": 1.85, "team_b_odds": 2.05, "draw_odds": 0},
        ]

        for odds_item in odds_data:
            match = matches[odds_item["match_idx"]]
            existing_odds = Odds.query.filter_by(match_id=match.id).first()

            if not existing_odds:
                odd = Odds(
                    match_id=match.id,
                    team_a_odds=odds_item["team_a_odds"],
                    team_b_odds=odds_item["team_b_odds"],
                    draw_odds=odds_item["draw_odds"]
                )
                db.session.add(odd)
                print(f"  ✓ Odds para '{match.team_a} vs {match.team_b}' criadas")
            else:
                print(f"  - Odds para '{match.team_a} vs {match.team_b}' já existem")

        db.session.commit()

        # ==================== CRIAR PALPITES ====================
        print("\n🎯 Criando palpites dos usuários...")

        guesses_data = [
            # Alice
            {"user_idx": 0, "match_idx": 0, "pred_a": 2, "pred_b": 1},
            {"user_idx": 0, "match_idx": 1, "pred_a": 1, "pred_b": 1},
            {"user_idx": 0, "match_idx": 2, "pred_a": 3, "pred_b": 0},
            # Bob
            {"user_idx": 1, "match_idx": 0, "pred_a": 1, "pred_b": 1},
            {"user_idx": 1, "match_idx": 1, "pred_a": 2, "pred_b": 0},
            {"user_idx": 1, "match_idx": 2, "pred_a": 1, "pred_b": 2},
            # Carlos
            {"user_idx": 2, "match_idx": 0, "pred_a": 3, "pred_b": 2},
            {"user_idx": 2, "match_idx": 1, "pred_a": 0, "pred_b": 0},
            {"user_idx": 2, "match_idx": 3, "pred_a": 2, "pred_b": 1},
            # Diana
            {"user_idx": 3, "match_idx": 0, "pred_a": 1, "pred_b": 0},
            {"user_idx": 3, "match_idx": 2, "pred_a": 2, "pred_b": 2},
            {"user_idx": 3, "match_idx": 4, "pred_a": 2, "pred_b": 0},
            # Eva
            {"user_idx": 4, "match_idx": 1, "pred_a": 1, "pred_b": 2},
            {"user_idx": 4, "match_idx": 3, "pred_a": 0, "pred_b": 1},
        ]

        for guess_data in guesses_data:
            user = users[guess_data["user_idx"]]
            match = matches[guess_data["match_idx"]]

            existing_guess = Guesses.query.filter_by(
                user_id=user.id,
                match_id=match.id
            ).first()

            if not existing_guess:
                guess = Guesses(
                    user_id=user.id,
                    match_id=match.id,
                    pred_a=guess_data["pred_a"],
                    pred_b=guess_data["pred_b"],
                    is_knockout=match.is_knockout
                )
                db.session.add(guess)
                print(f"  ✓ Palpite de {user.username} para '{match.team_a} vs {match.team_b}' criado")
            else:
                print(f"  - Palpite de {user.username} para '{match.team_a} vs {match.team_b}' já existe")

        db.session.commit()

        print("\n✅ Seed concluído com sucesso!")
        print("\n📋 Dados criados:")
        print(f"  - {len(users)} usuários")
        print(f"  - {Teams.query.count()} times")
        print(f"  - {len(matches)} partidas")
        print(f"  - {Odds.query.count()} registros de odds")
        print(f"  - {Guesses.query.count()} palpites")

        print("\n🔑 Credenciais de teste:")
        for user_data in users_data:
            print(f"  - Usuário: {user_data['username']}, Senha: {user_data['password']}")

if __name__ == "__main__":
    seed_database()
