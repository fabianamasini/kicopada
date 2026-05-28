from models import db, Match, Guesses
from flask import flash, redirect, url_for
from datetime import datetime

class MatchesController:
    def get_all_matches(self):
        all_matches = Match.query.order_by(Match.date.desc()).all()
        return all_matches
    
    def get_match_by_id(self, match_id):
        match = Match.query.get(match_id)
        return match

    def get_next_match(self):
        """Retorna a próxima partida programada a partir de agora."""
        now_str = datetime.now().strftime("%Y-%m-%d")
        return Match.query.filter(Match.date >= now_str).order_by(Match.date.asc()).first()

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
            is_knockout = round != 'Fase de Grupos'
            new_match = Match(team_a=team_a,
                              team_b=team_b,
                              date=match_date,
                              round=round,
                              score_a=int(score_a) if score_a else None,
                              score_b=int(score_b) if score_b else None,
                              is_knockout=is_knockout)
            db.session.add(new_match)
            db.session.commit()

            flash('Jogo cadastrado com sucesso.', 'success')
            return redirect(url_for('matches'))    
        
    def delete_match(self, match_id):
        match = Match.query.get(match_id)
        if match:
            Guesses.query.filter_by(match_id=match_id).delete()
            db.session.delete(match)
            db.session.commit()
            flash('Partida e todos os palpites associados foram excluídos com sucesso.', 'success')
        else:
            flash('Partida não encontrada.', 'error')
        return redirect(url_for('matches'))
    
    def edit_match(self, match_id, team_a, team_b, match_date, round, score_a=None, score_b=None):
        match = Match.query.get(match_id)
        if match:
            match.team_a = team_a
            match.team_b = team_b
            match.date = match_date
            match.round = round
            match.is_knockout = round != 'Fase de Grupos'
            match.score_a = int(score_a) if score_a else None
            match.score_b = int(score_b) if score_b else None
            db.session.commit()
            flash('Partida atualizada com sucesso.', 'success')
        else:
            flash('Partida não encontrada.', 'error')
        return redirect(url_for('matches'))
