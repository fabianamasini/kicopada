from models import db, User, Guesses, Odds, Match
from sqlalchemy.orm import joinedload
from models import db, User, Guesses, Odds

class ScoringController:

    def __calculate_odd(self, total, count):
        if total <= 0:
            return 1.0
        if total == 1:
            return 1.0 if count == 1 else 2.0
        if count <= 0:
            return 2.0
        
        odd = 1 + ((total - count) / (total - 1))
        return max(1.0, min(2.0, odd))

    def __calculate_points(self, guess, odds_map=None):
        # Busca a odd no mapa em cache ou faz a query se não houver mapa
        odd_value = self.get_odds_for_guess(guess, odds_map)
        points = 0
        if not guess.match.is_knockout:
            points += (self.group_phase_result(
                guess.match.score_a, guess.match.score_b, guess.pred_a, guess.pred_b
            ) * odd_value)
        else:
            points += (self.knockout_phase_result(
                guess.match.score_a, guess.match.score_b, guess.pred_a, guess.pred_b,
                guess.match.winner, guess.winner_pred
            ) * odd_value)

        return points

    def calculate_odds_for_match(self, match_id):
        """Calcula as odds para uma partida específica com base nos palpites dos usuários.

        Odd = 1 + ((y - x) / (y - 1))

        y = numero total de palpites para aquela partida
        x = numero de palpites para aquele time
        
        """
        guesses = Guesses.query.filter_by(match_id=match_id).all()
        match = Match.query.get(match_id)
        total_guesses = len(guesses)

        if match.is_knockout:
            # Para mata-mata, contamos palpites por classificado
            count_a = sum(1 for g in guesses if g.winner_pred == 'A')
            count_b = sum(1 for g in guesses if g.winner_pred == 'B')
            count_draw = 0 # Não há odd para empate em mata-mata
        else:
            # Para fase de grupos, contamos por vitória A, empate, vitória B
            count_a = sum(1 for g in guesses if g.pred_a > g.pred_b)
            count_b = sum(1 for g in guesses if g.pred_b > g.pred_a)
            count_draw = sum(1 for g in guesses if g.pred_a == g.pred_b)

        odds_a = self.__calculate_odd(total_guesses, count_a)
        odds_b = self.__calculate_odd(total_guesses, count_b)
        odds_draw = self.__calculate_odd(total_guesses, count_draw) if not match.is_knockout else 1.0 # Em mata-mata, a odd de empate é neutra (1.0)

        odds = Odds.query.filter_by(match_id=match_id).first()
        if not odds:
            odds = Odds(match_id=match_id, team_a_odds=odds_a, team_b_odds=odds_b, draw_odds=odds_draw)
            db.session.add(odds)
        else:
            # Atualiza as odds existentes
            odds.team_a_odds = odds_a
            odds.team_b_odds = odds_b
            odds.draw_odds = odds_draw
        db.session.commit()

    def group_phase_result(self, score_a, score_b, pred_a, pred_b):
        """"
        Calcula a pontuação para um palpite na fase de grupos, considerando o resultado exato e o saldo de gols.
         - 1000 pontos para o resultado exato (placar correto)
         - 500 pontos para o saldo de gols correto (diferença entre os placares)
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
            return 1000
        elif real_diff == pred_diff:
            return 500
        elif sign(real_diff) == sign(pred_diff):
            return 200
        return 0
    
    def knockout_phase_result(self, score_a, score_b, pred_a, pred_b, winner_real, winner_pred):
        if score_a is None or score_b is None:
            return 0

        saldo_real = score_a - score_b
        saldo_palpite = pred_a - pred_b

        # Flag para indicar se o placar final foi empate (independentemente de quem classificou)
        is_real_draw = (saldo_real == 0)
        is_pred_draw = (saldo_palpite == 0)

        # Determina Classificado Real (C) e Palpitado (Cx)
        # Se não for empate no tempo normal, o vencedor é óbvio pelo placar. Se for empate, usa o winner_real/winner_pred.
        if score_a != score_b:
            c_real = 'A' if score_a > score_b else 'B'
        else:
            c_real = winner_real
        if pred_a != pred_b:
            c_pred = 'A' if pred_a > pred_b else 'B'
        else:
            c_pred = winner_pred

        cx_eq_c = (c_real is not None and c_real == c_pred)

        # Regras hierárquicas
        if cx_eq_c and pred_a == score_a and pred_b == score_b:
            return 1500
        elif cx_eq_c and saldo_palpite == saldo_real:
            return 800
        elif cx_eq_c and is_pred_draw == is_real_draw: # Acertou se foi empate ou não no tempo normal
            return 600
        elif cx_eq_c:
            return 500
        elif pred_a == score_a and pred_b == score_b:
            return 200
        elif saldo_palpite == saldo_real:
            return 100 # Acertou o saldo, mas não o classificado
        elif is_pred_draw == is_real_draw:
            return 100 # Acertou se foi empate ou não no tempo normal, mas não o classificado
        return 0

    def calculate_score_for_guess(self, guess):
        """
        Calcula e atualiza a pontuação de um palpite específico e a pontuação total do usuário.
        """
        # Este método não é mais usado diretamente após a refatoração para update_user_points
        # que recalcula todos os palpites do usuário.
        # Mantido por compatibilidade, mas pode ser removido se não houver chamadas externas.
        if guess and guess.user_id:
            self.update_user_points(guess.user_id) # Garante que o usuário é atualizado

    def get_odds_for_guess(self, guess, odds_map=None):
        odds = Odds.query.filter_by(match_id=guess.match_id).first()
        if not odds:
            return 2.0 

        if guess.match.is_knockout:
            if guess.winner_pred == 'A':
                return odds.team_a_odds
            elif guess.winner_pred == 'B':
                return odds.team_b_odds
            return 1.0 # Se não houver winner_pred (erro ou não aplicável), retorna odd neutra
        else:
            if guess.pred_a > guess.pred_b:
                return odds.team_a_odds
            elif guess.pred_b > guess.pred_a:
                return odds.team_b_odds
            else:
                return odds.draw_odds

    def update_user_points(self, user_id, commit=True, odds_map=None):
        """Recalcula a pontuação total de um usuário com base em todos os seus palpites
        ou em algum palpite específico."""
        user = User.query.get(user_id)
        if not user:
            return

        total_points = user.adjustment_points or 0
        user_guesses = Guesses.query.filter_by(user_id=user_id).options(joinedload(Guesses.match)).all()
        
        for g in user_guesses:
            if g.match and g.match.score_a is not None and g.match.score_b is not None:
                total_points += self.__calculate_points(g, odds_map)
        
        user.points = int(total_points + 0.5)
        if commit:
            db.session.commit()

    def update_all_scores_for_match(self, match_id):
        """Atualiza a pontuação de todos os usuários que palpitaram em uma partida específica."""
        self.calculate_odds_for_match(match_id)
        
        # Otimização: Carrega todas as Odds de uma vez para evitar N+1 queries no loop
        all_odds = Odds.query.all()
        odds_map = {o.match_id: o for o in all_odds}
        
        guesses = Guesses.query.filter_by(match_id=match_id).all()
        for g in guesses:
            self.update_user_points(g.user_id, commit=False, odds_map=odds_map)
        db.session.commit()
