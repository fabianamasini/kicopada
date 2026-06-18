import pytz
from datetime import datetime
from models import db, Guesses
from sqlalchemy.orm import joinedload
from .matches import MatchesController
from .scoring import ScoringController
from flask import flash, redirect, url_for

class GuessesController:
    def __init__(self):
        self.scoring = ScoringController()

    def get_user_guesses(self, user_id):
        guesses = Guesses.query.filter_by(user_id=user_id).options(joinedload(Guesses.match)).all()

        # Define o fuso horário de São Paulo
        saopaulo_tz = pytz.timezone('America/Sao_Paulo')
        
        # Obtém a data e hora atual no fuso horário de São Paulo
        now_saopaulo = datetime.now(saopaulo_tz)
        
        # today_str deve refletir "hoje" no fuso horário de São Paulo
        today_str = now_saopaulo.strftime("%Y-%m-%d")
        
        # Define o limite como o início do dia atual (00:00) em São Paulo.
        # Partidas que ocorreram em dias anteriores são movidas para a aba de anteriores.
        limit_today_start = now_saopaulo.replace(hour=0, minute=0, second=0, microsecond=0)

        active_guesses = []
        previous_guesses = []

        for g in guesses:
            if not g.match.date:
                active_guesses.append(g)
                continue

            try:
                # Converte a data da partida para um objeto datetime e o torna timezone-aware (São Paulo)
                match_dt_naive = datetime.strptime(g.match.date, "%Y-%m-%dT%H:%M")
                match_dt_saopaulo = saopaulo_tz.localize(match_dt_naive)

                # Se a partida ocorreu antes do início de hoje, vai para anteriores
                if match_dt_saopaulo < limit_today_start:
                    previous_guesses.append(g)
                else:
                    active_guesses.append(g)
            except (ValueError, TypeError):
                active_guesses.append(g)
        
        # Ordenação Active: Jogos de hoje primeiro, depois os mais próximos para os mais futuros
        active_guesses.sort(key=lambda x: (x.match.date[:10] != today_str, x.match.date))

        # Ordenação Previous: Data decrescente (mais recentes primeiro)
        previous_guesses.sort(key=lambda x: x.match.date, reverse=True)

        return {'active': active_guesses, 'previous': previous_guesses}

    def get_guess_by_id(self, user_id, match_id):
        return Guesses.query.filter_by(user_id=user_id, match_id=int(match_id)).first()
    
    def add_guess(self, request, current_user):
        match_id = request.form.get('match_id')
        user_id = current_user.id
        pred_a_str = request.form.get('pred_a')
        pred_b_str = request.form.get('pred_b')
        winner_pred = request.form.get('winner_pred')

        if not match_id:
            flash('Selecione uma partida válida.', 'error')
            return redirect(url_for('create_guess'))
        
        match = MatchesController().get_match_by_id(int(match_id))
        if not match or not match.is_editable():
            flash('Palpites só podem ser feitos até as 23:59 do dia anterior ao jogo.', 'error')
            return redirect(url_for('guesses'))
        
        if not pred_a_str or not pred_b_str or not pred_a_str.isdigit() or not pred_b_str.isdigit():
            flash('Os placares devem ser números.', 'error')
            return redirect(url_for('create_guess'))
        
        pred_a = int(pred_a_str)
        pred_b = int(pred_b_str)

        # Lógica para deduzir winner_pred em mata-mata
        if match.is_knockout:
            if pred_a > pred_b:
                winner_pred = 'A'
            elif pred_b > pred_a:
                winner_pred = 'B'
            else: # Empate no tempo normal, precisa de um classificado
                if winner_pred not in ['A', 'B']:
                    flash('Escolha quem se classifica nos pênaltis.', 'error')
                    return redirect(url_for('create_guess'))
        else:
            winner_pred = None # Não se aplica a fase de grupos

        existing_guess = self.get_guess_by_id(user_id, match_id)
        if existing_guess:
            flash('Você já fez um palpite para este jogo.', 'error')
            return redirect(url_for('guesses'))
        
        new_guess = Guesses(
            user_id=current_user.id,
            match_id=match_id,
            pred_a=pred_a,
            pred_b=pred_b,
            winner_pred=winner_pred,
            is_knockout=match.is_knockout)

        db.session.add(new_guess)
        db.session.commit()

        self.scoring.calculate_odds_for_match(match_id)

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

            # Recalcular Odds e pontos do usuário
            self.scoring.calculate_odds_for_match(guess.match_id)
            self.scoring.update_user_points(user_id)
            flash('Palpite excluído com sucesso.', 'success')
        else:
            flash('Palpite não encontrado ou acesso negado.', 'error')
        return redirect(url_for('guesses'))
    
    def edit_guess(self, guess_id, user_id, pred_a, pred_b, winner_pred=None):
        guess = Guesses.query.filter_by(id=guess_id, user_id=user_id).options(joinedload(Guesses.match)).first()
        if not guess:
            flash('Palpite não encontrado ou acesso negado.', 'error')
            return redirect(url_for('guesses'))
            
        if not guess.match.is_editable():
            flash('Este palpite não pode mais ser editado pois o prazo expirou.', 'error')
            return redirect(url_for('guesses'))

        if not pred_a or not pred_b or not str(pred_a).isdigit() or not str(pred_b).isdigit():
            flash('Os placares devem ser números.', 'error')
            return redirect(url_for('edit_guess', guess_id=guess_id))
        
        pred_a_int = int(pred_a)
        pred_b_int = int(pred_b)

        # Lógica para deduzir winner_pred em mata-mata
        if guess.match.is_knockout:
            if pred_a_int > pred_b_int:
                winner_pred = 'A'
            elif pred_b_int > pred_a_int:
                winner_pred = 'B'
            else: # Empate no tempo normal, precisa de um classificado
                if winner_pred not in ['A', 'B']:
                    flash('Escolha quem se classifica nos pênaltis.', 'error')
                    return redirect(url_for('edit_guess', guess_id=guess_id))
        else:
            winner_pred = None # Não se aplica a fase de grupos

        guess.pred_a = pred_a_int
        guess.pred_b = pred_b_int
        guess.winner_pred = winner_pred
        db.session.commit()
        
        self.scoring.calculate_odds_for_match(guess.match_id) # Atualiza as odds para a partida
        flash('Palpite atualizado com sucesso.', 'success')
        return redirect(url_for('guesses'))
