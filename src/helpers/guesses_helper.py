from models import db, Guesses, Match, User
from flask import flash, redirect, url_for
from sqlalchemy.orm import joinedload
from src.helpers.odds_helper import OddsHelper

class GuessesHelper:
    def __init__(self):
        self.odds_helper = OddsHelper()

    def get_user_guesses(self, user_id):
        return Guesses.query.filter_by(user_id=user_id).options(joinedload(Guesses.match)).all()
    
    def add_new_guess(self, user_id, match_id, pred_a, pred_b, winner_pred=None, penalty_a=None, penalty_b=None):
        if not match_id:
            flash('Selecione uma partida válida.', 'error')
            return redirect(url_for('create_guess'))

        match = Match.query.get(int(match_id))
        if not match or not match.is_editable():
            flash('Palpites só podem ser feitos até as 23:59 do dia anterior ao jogo.', 'error')
            return redirect(url_for('guesses'))

        if not pred_a or not pred_b or not pred_a.isdigit() or not pred_b.isdigit():
            flash('Os placares devem ser números.', 'error')
            return redirect(url_for('create_guess'))
        
        existing_guess = Guesses.query.filter_by(user_id=user_id, match_id=int(match_id)).first()
        if existing_guess:
            flash('Você já fez um palpite para este jogo.', 'error')
            return redirect(url_for('guesses'))
        
        new_guess = Guesses(
            user_id=user_id, 
            match_id=match_id, 
            pred_a=int(pred_a), 
            pred_b=int(pred_b),
            winner_pred=winner_pred,
            penalty_pred_a=int(penalty_a) if penalty_a else None,
            penalty_pred_b=int(penalty_b) if penalty_b else None,
            is_knockout=match.is_knockout)
        db.session.add(new_guess)
        db.session.commit()
        self._calculate_score_for_guess(new_guess.id) # Chamada para a função de cálculo de pontuação

        flash('Palpite cadastrado com sucesso.', 'success')
        return redirect(url_for('guesses'))

    def delete_guess(self, guess_id, user_id):
        guess = Guesses.query.filter_by(id=guess_id, user_id=user_id).options(joinedload(Guesses.match)).first()
        if guess:
            if not guess.match.is_editable():
                flash('Este palpite não pode mais ser excluído pois o prazo expirou.', 'error')
                return redirect(url_for('guesses'))
                
            db.session.delete(guess)
            db.session.commit()
            self.update_user_points(user_id)
            flash('Palpite excluído com sucesso.', 'success')
        else:
            flash('Palpite não encontrado ou acesso negado.', 'error')
        return redirect(url_for('guesses'))

    def edit_guess(self, guess_id, user_id, pred_a, pred_b, winner_pred=None, penalty_a=None, penalty_b=None):
        guess = Guesses.query.filter_by(id=guess_id, user_id=user_id).options(joinedload(Guesses.match)).first()
        if not guess:
            flash('Palpite não encontrado ou acesso negado.', 'error')
            return redirect(url_for('guesses'))
            
        if not guess.match.is_editable():
            flash('Este palpite não pode mais ser editado pois o prazo expirou.', 'error')
            return redirect(url_for('guesses'))

        if not pred_a or not pred_b or not pred_a.isdigit() or not pred_b.isdigit():
            flash('Os placares devem ser números.', 'error')
            return redirect(url_for('edit_guess', guess_id=guess_id))
        
        guess.pred_a = int(pred_a)
        guess.pred_b = int(pred_b)
        guess.winner_pred = winner_pred
        guess.penalty_pred_a = int(penalty_a) if penalty_a else None
        guess.penalty_pred_b = int(penalty_b) if penalty_b else None
        db.session.commit()
        self._calculate_score_for_guess(guess.id) # Chamada para a função de cálculo de pontuação
        flash('Palpite atualizado com sucesso.', 'success')
        return redirect(url_for('guesses'))

    def _calculate_score_for_guess(self, guess_id):
        """
        Calcula e atualiza a pontuação de um palpite específico e a pontuação total do usuário.
        """
        guess = Guesses.query.get(guess_id)
        if guess:
            self.update_user_points(guess.user_id)

    def update_user_points(self, user_id):
        """Recalcula a pontuação total de um usuário com base em todos os seus palpites."""
        user = User.query.get(user_id)
        if not user:
            return

        total_points = 0
        user_guesses = Guesses.query.filter_by(user_id=user_id).options(joinedload(Guesses.match)).all()
        
        for g in user_guesses:
            if g.match.score_a is not None and g.match.score_b is not None:
                if not g.match.is_knockout:
                    total_points += self.odds_helper.group_phase_result(
                        g.match.score_a, g.match.score_b, g.pred_a, g.pred_b
                    )
                else:
                    total_points += self.odds_helper.knockout_phase_result(
                        g.match.score_a, g.match.score_b, g.pred_a, g.pred_b,
                        g.match.winner, g.winner_pred,
                        g.match.penalty_score_a, g.match.penalty_score_b,
                        g.penalty_pred_a, g.penalty_pred_b
                    )
        
        user.points = total_points
        db.session.commit()

    def update_all_scores_for_match(self, match_id):
        """Atualiza a pontuação de todos os usuários que palpitaram em uma partida específica."""
        guesses = Guesses.query.filter_by(match_id=match_id).all()
        user_ids = set(g.user_id for g in guesses)
        for uid in user_ids:
            self.update_user_points(uid)