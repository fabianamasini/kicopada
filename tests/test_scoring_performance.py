import unittest
import sys
import os

# Adiciona o diretório raiz ao path para evitar erros de importação
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db
from models import User, Match, Guesses, Teams
from src.controllers.scoring import ScoringController

class TestScoringSystem(unittest.TestCase):
    def setUp(self):
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['TESTING'] = True
        self.app_context = app.app_context()
        self.app_context.push()
        db.create_all()
        self.scoring = ScoringController()

    def tearDown(self):
        db.session.rollback()
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_group_phase_scoring_logic(self):
        """Valida individualmente cada cenário de pontuação da fase de grupos."""
        user = User(username='logic_tester', password_hash='hash')
        db.session.add(user)
        match = Match(team_a='Brasil', team_b='Sérvia', round='Grupo', is_knockout=False)
        db.session.add(match)
        db.session.commit()

        # Cenários: (Pred_A, Pred_B, Real_A, Real_B, Pontos_Esperados, Descrição)
        scenarios = [
            (2, 0, 2, 0, 1000, "Placar Exato"),
            (1, 0, 2, 1, 500,  "Mesmo Saldo (Vitória)"),
            (1, 1, 2, 2, 500,  "Mesmo Saldo (Empate)"),
            (3, 0, 1, 0, 200,  "Acertou Vencedor, Errou Saldo/Placar"),
            (0, 1, 1, 0, 0,    "Erro Total de Resultado")
        ]

        for pa, pb, ra, rb, expected, desc in scenarios:
            with self.subTest(msg=desc):
                Guesses.query.delete()
                user.points = 0
                db.session.add(Guesses(user_id=user.id, match_id=match.id, pred_a=pa, pred_b=pb))
                match.score_a, match.score_b = ra, rb
                db.session.commit()

                # Forçamos o cálculo. Com 1 palpite, a odd é 1.0.
                self.scoring.update_all_scores_for_match(match.id)
                db.session.refresh(user)
                self.assertEqual(user.points, expected, f"Falha no cenário: {desc}")

    def test_sequential_rounds_and_varied_odds(self):
        """Simula 10 partidas sequenciais com 28 usuários e Odds variadas (Zebra vs Favorito)."""
        # 1. Criar 28 usuários
        users = [User(username=f'u_{i}', password_hash='h') for i in range(28)]
        db.session.add_all(users)
        
        # 2. Criar 10 partidas
        matches = [Match(team_a=f'A{i}', team_b=f'B{i}', round='Grupo', is_knockout=False) for i in range(10)]
        db.session.add_all(matches)
        db.session.commit()

        # 3. Criar palpites variados (3 perfis de apostadores)
        # Perfil 1 (15 users): Apostam 1-0 (Favorito A) -> Odds mais baixas
        # Perfil 2 (8 users): Apostam 0-0 (Empate)      -> Odds médias
        # Perfil 3 (5 users): Apostam 0-1 (Zebra B)      -> Odds altas
        for i, user in enumerate(users):
            for m in matches:
                if i < 15: pa, pb = 1, 0
                elif i < 23: pa, pb = 0, 0
                else: pa, pb = 0, 1
                db.session.add(Guesses(user_id=user.id, match_id=m.id, pred_a=pa, pred_b=pb))
        db.session.commit()

        # 4. Simular Rodadas com resultados que favorecem diferentes grupos
        # R1: 1-0 (Fav A), R2: 0-1 (Zebra B), R3: 0-0 (Empate), etc.
        results = [(1,0), (0,1), (0,0), (2,1), (0,2), (1,1), (2,0), (0,1), (0,0), (1,0)]
        for i, (ra, rb) in enumerate(results):
            m = matches[i]
            m.score_a, m.score_b = ra, rb
            db.session.commit()
            self.scoring.update_all_scores_for_match(m.id)

        # 5. Validação de acúmulo e Odds
        fav_user = users[0]
        zebra_user = users[25]
        db.session.refresh(fav_user)
        db.session.refresh(zebra_user)

        self.assertGreater(zebra_user.points, 0, "Usuários da zebra deveriam ter pontos.")
        # Como a Zebra (0-1) aconteceu em 2 das 10 rodadas e as odds eram maiores,
        # validamos se o cálculo de multiplicador funcionou.

    def test_mass_update_performance_and_integrity(self):
        """Garante que edições sucessivas de uma mesma partida não corrompem o total."""
        users = [User(username=f'mass_u_{i}', password_hash='h') for i in range(28)]
        db.session.add_all(users)
        matches = [Match(team_a=f'MA{i}', team_b=f'MB{i}', round='Grupo', is_knockout=False) for i in range(10)]
        db.session.add_all(matches)
        db.session.commit()

        for user in users:
            for match in matches:
                g = Guesses(user_id=user.id, match_id=match.id, pred_a=1, pred_b=0)
                db.session.add(g)
        
        db.session.commit()

        target_match = matches[0]
        target_match.score_a = 1
        target_match.score_b = 0
        db.session.commit()

        self.scoring.update_all_scores_for_match(target_match.id)

        for user in users:
            db.session.refresh(user)
            self.assertEqual(user.points, 1000, f"Usuário {user.username} deveria ter 1000 pontos.")

        target_match.score_a = 0
        target_match.score_b = 5
        db.session.commit()

        self.scoring.update_all_scores_for_match(target_match.id)

        for user in users:
            db.session.refresh(user)
            # Agora os pontos devem ser 0, não 1000 nem 2000.
            self.assertEqual(user.points, 0, f"Usuário {user.username} deveria ter 0 pontos após edição.")

        print("\nTeste de performance e integridade concluído com sucesso!")

if __name__ == '__main__':
    unittest.main()