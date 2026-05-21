from models import db, Guesses, Match
from flask import flash, redirect, url_for
from sqlalchemy.orm import joinedload

class GuessesHelper:
    def get_user_guesses(self, user_id):
        return Guesses.query.filter_by(user_id=user_id).options(joinedload(Guesses.match)).all()
    
    def add_new_guess(self, user_id, match_id, pred_a, pred_b):
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
        
        new_guess = Guesses(user_id=user_id, match_id=match_id, pred_a=int(pred_a), pred_b=int(pred_b))
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
            flash('Palpite excluído com sucesso.', 'success')
        else:
            flash('Palpite não encontrado ou acesso negado.', 'error')
        return redirect(url_for('guesses'))

    def edit_guess(self, guess_id, user_id, pred_a, pred_b):
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
        db.session.commit()
        self._calculate_score_for_guess(guess.id) # Chamada para a função de cálculo de pontuação
        flash('Palpite atualizado com sucesso.', 'success')
        return redirect(url_for('guesses'))

    def _calculate_score_for_guess(self, guess_id):
        """
        Função placeholder para calcular a pontuação de um palpite.
        A lógica de cálculo de pontuação será adicionada aqui posteriormente.
        """
        print(f"DEBUG: Função de cálculo de pontuação acionada para o palpite ID: {guess_id}")
        # TODO: Implementar a lógica de cálculo de pontuação aqui.
        # Exemplo: Obter o palpite, obter o resultado da partida, comparar e atualizar a pontuação do usuário.