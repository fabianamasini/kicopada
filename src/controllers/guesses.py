from datetime import datetime, timedelta
from models import db, Guesses
from .matches import MatchesController
from .scoring import ScoringController
from flask import flash, redirect, url_for
from sqlalchemy.orm import joinedload

class GuessesController:
    def __init__(self):
        self.scoring = ScoringController()

    def get_user_guesses(self, user_id):
        guesses = Guesses.query.filter_by(user_id=user_id).options(joinedload(Guesses.match)).all()

        now = datetime.now()
        today_str = now.strftime("%Y-%m-%d")
        limit_previous = now - timedelta(days=1)

        active_guesses = []
        previous_guesses = []

        for g in guesses:
            if not g.match.date:
                active_guesses.append(g)
                continue

            try:
                match_dt = datetime.strptime(g.match.date, "%Y-%m-%dT%H:%M")
                if match_dt < limit_previous:
                    previous_guesses.append(g)
                else:
                    active_guesses.append(g)
            except (ValueError, TypeError):
                active_guesses.append(g)

        # Ordenação Active: Jogos de hoje primeiro, depois por data decrescente
        active_guesses.sort(key=lambda x: (x.match.date[:10] == today_str, x.match.date), reverse=True)

        # Ordenação Previous: Data decrescente (mais recentes primeiro)
        previous_guesses.sort(key=lambda x: x.match.date, reverse=True)

        return {'active': active_guesses, 'previous': previous_guesses}

    def get_guess_by_id(self, user_id, match_id):
        return Guesses.query.filter_by(user_id=user_id, match_id=int(match_id)).first()
    
    def add_guess(self, request, current_user):
        match_id = request.form.get('match_id')
        user_id = current_user.id
        pred_a = request.form.get('pred_a')
        pred_b = request.form.get('pred_b')
        winner_pred = request.form.get('winner_pred')
        penalty_a = request.form.get('penalty_a')
        penalty_b = request.form.get('penalty_b')

        if not match_id:
            flash('Selecione uma partida válida.', 'error')
            return redirect(url_for('create_guess'))
        
        match = MatchesController().get_match_by_id(int(match_id))
        if not match or not match.is_editable():
            flash('Palpites só podem ser feitos até as 23:59 do dia anterior ao jogo.', 'error')
            return redirect(url_for('guesses'))
        
        if not pred_a or not pred_b or not pred_a.isdigit() or not pred_b.isdigit():
            flash('Os placares devem ser números.', 'error')
            return redirect(url_for('create_guess'))
        
        existing_guess = self.get_guess_by_id(user_id, match_id)
        if existing_guess:
            flash('Você já fez um palpite para este jogo.', 'error')
            return redirect(url_for('guesses'))
        
        new_guess = Guesses(
            user_id=current_user.id, 
            match_id=match_id, 
            pred_a=int(pred_a), 
            pred_b=int(pred_b),
            winner_pred=winner_pred,
            penalty_pred_a=int(penalty_a) if penalty_a else None,
            penalty_pred_b=int(penalty_b) if penalty_b else None,
            is_knockout=match.is_knockout)

        db.session.add(new_guess)
        db.session.commit()

        self.scoring.calculate_odds_for_match(match_id)
        self.scoring.calculate_score_for_guess(new_guess)

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

            # Recalcular Odds
            self.scoring.calculate_odds_for_match(guess.match_id)
            self.scoring.update_user_points(user_id)
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
        
        self.scoring.calculate_odds_for_match(guess.match_id) # Atualiza as odds para a partida
        self.scoring.calculate_score_for_guess(guess) # Chamada para a função de cálculo de pontuação
        flash('Palpite atualizado com sucesso.', 'success')
        return redirect(url_for('guesses'))
