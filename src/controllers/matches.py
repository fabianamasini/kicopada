import pytz
from datetime import datetime
from models import db, Match, Guesses
from flask import flash, redirect, url_for

class MatchesController:
    def get_all_matches(self):
        all_matches = Match.query.order_by(Match.date.desc()).all()
        return all_matches

    def get_available_matches_for_user(self, user_id):
        """Retorna partidas que o usuário ainda não palpitou, ordenadas por data crescente."""
        guessed_ids = db.session.query(Guesses.match_id).filter(Guesses.user_id == user_id)
        return Match.query.filter(~Match.id.in_(guessed_ids)).order_by(Match.date.asc()).all()

    def get_categorized_matches(self):
        """Retorna partidas divididas entre ativas e anteriores com ordenação específica."""
        matches = Match.query.all()
        saopaulo_tz = pytz.timezone('America/Sao_Paulo')
        now_saopaulo = datetime.now(saopaulo_tz)
        today_str = now_saopaulo.strftime("%Y-%m-%d")
        # Define o limite como o início do dia atual (00:00) em São Paulo
        limit_today_start = now_saopaulo.replace(hour=0, minute=0, second=0, microsecond=0)

        active_matches = []
        previous_matches = []

        for m in matches:
            if not m.date:
                active_matches.append(m)
                continue
            try:
                match_dt_naive = datetime.strptime(m.date, "%Y-%m-%dT%H:%M")
                match_dt_saopaulo = saopaulo_tz.localize(match_dt_naive)
                if match_dt_saopaulo < limit_today_start:
                    previous_matches.append(m)
                else:
                    active_matches.append(m)
            except (ValueError, TypeError):
                active_matches.append(m)

        # Ordenação Active: Jogos de hoje primeiro, depois cronológica (mais próximos primeiro)
        active_matches.sort(key=lambda x: (x.date[:10] != today_str, x.date))
        # Ordenação Anteriores: Mais recentes para mais antigos
        previous_matches.sort(key=lambda x: x.date, reverse=True)

        return {'active': active_matches, 'previous': previous_matches}

    def get_match_by_id(self, match_id):
        match = Match.query.get(match_id)
        return match

    def get_next_match(self):
        """Retorna a próxima partida programada a partir de agora."""
        saopaulo_tz = pytz.timezone('America/Sao_Paulo')
        now_str = datetime.now(saopaulo_tz).strftime("%Y-%m-%d")
        return Match.query.filter(Match.date >= now_str).order_by(Match.date.asc()).first()

    def get_upcoming_matches(self):
        """Retorna as próximas partidas programadas a partir de agora."""
        saopaulo_tz = pytz.timezone('America/Sao_Paulo')
        now_str = datetime.now(saopaulo_tz).strftime("%Y-%m-%d")
        return Match.query.filter(Match.date >= now_str).order_by(Match.date.asc()).all()

    def add_new_match(self, team_a, team_b, match_date, round, score_a=None, score_b=None, winner=None):
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
            
            winner_real = None
            if is_knockout and score_a and score_b:
                score_a_int = int(score_a)
                score_b_int = int(score_b)

                if score_a_int > score_b_int:
                    winner_real = 'A'
                elif score_b_int > score_a_int:
                    winner_real = 'B'
                else:
                    if winner not in ['A', 'B']:
                        flash('Escolha quem se classificou nos pênaltis.', 'error')
                        return redirect(url_for('create_match'))
                    winner_real = winner

            new_match = Match(team_a=team_a,
                              team_b=team_b,
                              date=match_date,
                              round=round,
                              score_a=int(score_a) if score_a else None,
                              score_b=int(score_b) if score_b else None,
                              is_knockout=is_knockout,
                              winner=winner_real)
            
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
    
    def edit_match(self, match_id, team_a, team_b, match_date, round, score_a=None, score_b=None, winner=None):
        match = Match.query.get(match_id)
        if match:
            is_knockout = round != 'Fase de Grupos'
            
            winner_real = None
            if is_knockout and score_a and score_b:
                score_a_int = int(score_a)
                score_b_int = int(score_b)

                if score_a_int > score_b_int:
                    winner_real = 'A'
                elif score_b_int > score_a_int:
                    winner_real = 'B'
                else:
                    if winner not in ['A', 'B']:
                        flash('Escolha quem se classificou nos pênaltis.', 'error')
                        return redirect(url_for('edit_match', match_id=match_id))
                    winner_real = winner

            match.team_a = team_a
            match.team_b = team_b
            match.date = match_date
            match.round = round
            match.is_knockout = is_knockout
            match.score_a = int(score_a) if score_a else None
            match.score_b = int(score_b) if score_b else None
            match.winner = winner_real
            db.session.commit()
            flash('Partida atualizada com sucesso.', 'success')
        else:
            flash('Partida não encontrada.', 'error')
        return redirect(url_for('matches'))
