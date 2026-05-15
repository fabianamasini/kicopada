from models import db, Match
from flask import flash, redirect, url_for

class MatchesHelper:
    def get_user_matches(self, user_id):
        return Match.query.filter((Match.player1_id == user_id) | (Match.player2_id == user_id)).all()
    
    def add_new_match(self, team_a, team_b, match_date, round, score_a=None, score_b=None):
        if not team_a:
            flash('O time A é obrigatório.', 'error')
            return redirect(url_for('create_match'))
        if not team_b:
            flash('O time B é obrigatório.', 'error')
            return redirect(url_for('create_match'))
        if team_a == team_b:
            flash('Os times A e B devem ser diferentes.', 'error')
            return redirect(url_for('create_match'))
        if not match_date:
            flash('A data do jogo é obrigatória.', 'error')
            return redirect(url_for('create_match'))
        if not round:
            flash('A fase do jogo é obrigatória.', 'error')
            return redirect(url_for('create_match'))
        if score_a and not score_a.isdigit():
            flash('O placar do time A deve ser um número.', 'error')
            return redirect(url_for('create_match'))
        if score_b and not score_b.isdigit():
            flash('O placar do time B deve ser um número.', 'error')
            return redirect(url_for('create_match'))
        
        match = Match.query.filter_by(team_a=team_a, team_b=team_b, date=match_date).first()
        if match:
            flash('Este jogo já está cadastrado.', 'error')
            return redirect(url_for('create_match'))
        else:
            new_match = Match(team_a=team_a,
                              team_b=team_b,
                              date=match_date,
                              round=round,
                              score_a=int(score_a) if score_a else None,
                              score_b=int(score_b) if score_b else None)
            db.session.add(new_match)
            db.session.commit()

            flash('Jogo cadastrado com sucesso.', 'success')
            return redirect(url_for('matches'))

    def delete_match(self, match_id):
        match = Match.query.get(match_id)
        if match:
            db.session.delete(match)
            db.session.commit()
            flash('Partida excluída com sucesso.', 'success')
        else:
            flash('Partida não encontrada.', 'error')
        return redirect(url_for('matches'))