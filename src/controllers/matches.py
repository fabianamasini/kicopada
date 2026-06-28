import pytz
from datetime import datetime
from models import db, Match, Guesses

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
