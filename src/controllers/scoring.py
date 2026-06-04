from models import db, User, Guesses, Odds
from sqlalchemy.orm import joinedload

class ScoringController:

    def calculate_odds_for_match(self, match_id):
        """Calcula as odds para uma partida específica com base nos palpites dos usuários.

        Odd = 1 + ((y - x) / (y - 1))

        y = numero total de palpites para aquela partida
        x = numero de palpites para aquele time
        
        """
        guesses = Guesses.query.filter_by(match_id=match_id).all()
        total_guesses = len(guesses)

        if total_guesses <= 1:
            return 2.0, 2.0, 2.0  # Odds padrão se houver poucos palpites para evitar divisão por zero

        count_a = sum(1 for g in guesses if g.pred_a > g.pred_b)
        count_b = sum(1 for g in guesses if g.pred_b > g.pred_a)
        count_draw = sum(1 for g in guesses if g.pred_a == g.pred_b)

        odds_a = 1 + ((total_guesses - count_a)/(total_guesses - 1))
        odds_b = 1 + ((total_guesses - count_b)/(total_guesses - 1))
        odds_draw = 1 + ((total_guesses - count_draw)/(total_guesses - 1))

        odds = Odds.query.filter_by(match_id=match_id).first()
        if not odds:
            odds = Odds(match_id=match_id, team_a_odds=odds_a, team_b_odds=odds_b, draw_odds=odds_draw)
            db.session.add(odds)
        else:
            odds.team_a_odds = odds_a
            odds.team_b_odds = odds_b
            odds.draw_odds = odds_draw
        db.session.commit()

    def group_phase_result(self, score_a, score_b, pred_a, pred_b):
        """"
        Calcula a pontuação para um palpite na fase de grupos, considerando o resultado exato e o saldo de gols.
         - 10 pontos para o resultado exato (placar correto)
         - 5 pontos para o saldo de gols correto (diferença entre os placares)
         - 0 pontos para qualquer outro resultado

         Params:
            - score_a: Placar real do time A
            - score_b: Placar real do time B
            - pred_a: Placar previsto do time A
            - pred_b: Placar previsto do time B
        """
        if score_a is None or score_b is None:
            return 0

        real_diff = score_a - score_b # Saldo de gols real
        pred_diff = pred_a - pred_b # Saldo de gols do palpite

        def sign(x):
            if x > 0: return 1
            if x == 0: return 0
            return -1

        if score_a == pred_a and score_b == pred_b:
            return 10
        elif real_diff == pred_diff:
            return 5
        elif sign(real_diff) == sign(pred_diff):
            return 2
        return 0
    
    def knockout_phase_result(self, score_a, score_b, pred_a, pred_b, winner_real, winner_pred, pen_a=None, pen_b=None, p_pen_a=None, p_pen_b=None):
        if score_a is None or score_b is None:
            return 0

        saldo_real = score_a - score_b
        saldo_palpite = pred_a - pred_b

        fdd_real = 1 if saldo_real == 0 else 0
        fdd_palpite = 1 if saldo_palpite == 0 else 0

        # Determina Classificado Real (C) e Palpitado (Cx)
        # Se não for empate, o vencedor é óbvio pelo placar. Se for empate, usa o campo winner.
        if score_a != score_b:
            c_real = 'A' if score_a > score_b else 'B'
        else:
            c_real = 'A' if (pen_a or 0) > (pen_b or 0) else 'B' if (pen_b or 0) > (pen_a or 0) else winner_real

        if pred_a != pred_b:
            c_pred = 'A' if pred_a > pred_b else 'B'
        else:
            c_pred = 'A' if (p_pen_a or 0) > (p_pen_b or 0) else 'B' if (p_pen_b or 0) > (p_pen_a or 0) else winner_pred

        cx_eq_c = (c_real is not None and c_real == c_pred)

        # Regras hierárquicas
        if cx_eq_c and pred_a == score_a and pred_b == score_b:
            return 15
        elif cx_eq_c and saldo_palpite == saldo_real:
            return 8
        elif cx_eq_c and fdd_palpite == fdd_real:
            return 6
        elif cx_eq_c:
            return 5
        elif pred_a == score_a and pred_b == score_b:
            return 2
        elif saldo_palpite == saldo_real:
            return 1
        elif fdd_palpite == fdd_real:
            return 1
        return 0

    def calculate_score_for_guess(self, guess):
        """
        Calcula e atualiza a pontuação de um palpite específico e a pontuação total do usuário.
        """
        guess = Guesses.query.get(guess.id)
        if guess:
            self.update_user_points(guess.user_id)

    def get_odds_for_guess(self, guess):
        odds = Odds.query.filter_by(match_id=guess.match_id).first()
        if not odds:
            return 2.0 

        if guess.pred_a > guess.pred_b:
            return odds.team_a_odds
        elif guess.pred_b > guess.pred_a:
            return odds.team_b_odds
        else:
            return odds.draw_odds

    def update_user_points(self, user_id):
        """Recalcula a pontuação total de um usuário com base em todos os seus palpites."""
        user = User.query.get(user_id)
        if user:
            total_points = 0
            user_guesses = Guesses.query.filter_by(user_id=user_id).options(joinedload(Guesses.match)).all()
            
            for g in user_guesses:
                if g.match.score_a is not None and g.match.score_b is not None:
                    odds = self.get_odds_for_guess(g)

                    if not g.match.is_knockout:
                        total_points += (self.group_phase_result(
                            g.match.score_a, g.match.score_b, g.pred_a, g.pred_b
                        ) * odds)
                    else:
                        total_points += (self.knockout_phase_result(
                            g.match.score_a, g.match.score_b, g.pred_a, g.pred_b,
                            g.match.winner, g.winner_pred,
                            g.match.penalty_score_a, g.match.penalty_score_b,
                            g.penalty_pred_a, g.penalty_pred_b
                        ) * odds)
            
            user.points = total_points
            db.session.commit()

    def update_all_scores_for_match(self, match_id):
        """Atualiza a pontuação de todos os usuários que palpitaram em uma partida específica."""
        guesses = Guesses.query.filter_by(match_id=match_id).all()
        user_ids = set(g.user_id for g in guesses)
        for uid in user_ids:
            self.update_user_points(uid)
