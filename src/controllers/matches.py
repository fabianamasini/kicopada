import pytz
import calendar as _calendar
from datetime import datetime
from models import db, Match, Guesses
from flask import flash, redirect, url_for

_MESES_PT = {
    1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho',
    7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro',
}


def _build_wc_schedule():
    """Calendário FIXO da Copa 2026 (datas oficiais da ESPN): dia ISO -> fase.
    104 jogos em 34 dias; folgas (8,12,13,16,17/jul) ficam de fora de propósito."""
    import datetime as _dt
    sched = {}

    def faixa(inicio, fim, fase):
        d = _dt.date.fromisoformat(inicio)
        fim = _dt.date.fromisoformat(fim)
        while d <= fim:
            sched[d.isoformat()] = fase
            d += _dt.timedelta(days=1)

    faixa('2026-06-11', '2026-06-27', 'Fase de Grupos')      # 72 jogos
    faixa('2026-06-28', '2026-07-03', 'Rodada de 32')        # 16 jogos
    faixa('2026-07-04', '2026-07-07', 'Oitavas de Final')    # 8 jogos
    for iso in ('2026-07-09', '2026-07-10', '2026-07-11'):
        sched[iso] = 'Quartas de Final'                      # 4 jogos
    for iso in ('2026-07-14', '2026-07-15'):
        sched[iso] = 'Semifinal'                             # 2 jogos
    sched['2026-07-18'] = 'Disputa do 3º Lugar'
    sched['2026-07-19'] = 'Final'
    return sched


WC_SCHEDULE = _build_wc_schedule()
WC_FIRST = min(WC_SCHEDULE)   # primeiro dia da Copa (2026-06-11)
WC_LAST = max(WC_SCHEDULE)    # último dia da Copa (2026-07-19, a final)

# Rótulo curto exibido na célula dos dias de mata-mata ainda sem partidas no banco.
# (Fase de Grupos mostra a contagem de jogos; Final mostra o troféu.)
PHASE_TAG = {
    'Rodada de 32': 'R32',
    'Oitavas de Final': '8ªs',
    'Quartas de Final': '4ªs',
    'Semifinal': 'SF',
    'Disputa do 3º Lugar': '3º',
}

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

    def get_guess_calendar(self, user_id, months=((2026, 6), (2026, 7))):
        """Monta um calendário (jun/jul por padrão) com o estado dos palpites do
        usuário em cada dia, para colorir a grade na tela de cadastrar palpite.

        Estados por dia:
          empty    — sem jogo
          complete — tem jogo(s) e todos foram palpitados
          open     — falta palpite e ainda dá pra palpitar (jogo editável)
          past     — falta palpite mas o prazo já encerrou
        """
        saopaulo_tz = pytz.timezone('America/Sao_Paulo')
        today = datetime.now(saopaulo_tz).date()

        guessed_ids = {
            row[0] for row in
            db.session.query(Guesses.match_id).filter(Guesses.user_id == user_id)
        }

        # Agrupa as partidas por dia (YYYY-MM-DD)
        by_day = {}
        for m in Match.query.all():
            if not m.date:
                continue
            by_day.setdefault(m.date[:10], []).append(m)

        def build_day(iso):
            phase = WC_SCHEDULE.get(iso)          # None se o dia não é da Copa
            is_final = (phase == 'Final')
            day_matches = by_day.get(iso, [])

            if not day_matches:
                if phase is None:
                    # Sem fase: folga (buraco entre as fases, dentro da Copa) ou
                    # dia totalmente fora da Copa (esse fica invisível).
                    is_folga = WC_FIRST <= iso <= WC_LAST
                    return {'iso': iso, 'is_cup_day': False, 'is_folga': is_folga,
                            'has_matches': False, 'match_count': 0, 'guessed_count': 0,
                            'complete': False, 'state': 'folga' if is_folga else 'empty',
                            'clickable': False, 'target_match_id': None,
                            'is_final': False, 'phase': None, 'tag': None}
                # Dia fixo da Copa ainda sem partidas no banco (mata-mata) → agendado
                return {'iso': iso, 'is_cup_day': True, 'is_folga': False, 'has_matches': False,
                        'match_count': 0, 'guessed_count': 0, 'complete': False,
                        'state': 'fixture', 'clickable': False, 'target_match_id': None,
                        'is_final': is_final, 'phase': phase, 'tag': PHASE_TAG.get(phase)}

            guessed = [m for m in day_matches if m.id in guessed_ids]
            missing = [m for m in day_matches if m.id not in guessed_ids]
            complete = len(missing) == 0
            # Jogos que ainda dá pra palpitar (sem palpite e dentro do prazo)
            available = [m for m in missing if m.is_editable()]
            is_final = is_final or any((m.round or '') == 'Final' for m in day_matches)

            if complete:
                state = 'complete'
            elif available:
                state = 'open'
            else:
                state = 'past'

            return {
                'iso': iso, 'is_cup_day': True, 'is_folga': False, 'has_matches': True,
                'match_count': len(day_matches), 'guessed_count': len(guessed),
                'complete': complete, 'state': state, 'clickable': state == 'open',
                'target_match_id': available[0].id if available else None,
                'is_final': is_final, 'phase': phase, 'tag': None,
            }

        cal = _calendar.Calendar(firstweekday=6)  # domingo primeiro (convenção BR)
        result = []
        for year, month in months:
            weeks = []
            month_has_games = False
            for week in cal.monthdayscalendar(year, month):
                row = []
                for daynum in week:
                    if daynum == 0:
                        row.append(None)
                        continue
                    iso = f"{year:04d}-{month:02d}-{daynum:02d}"
                    day = build_day(iso)
                    day['num'] = daynum
                    day['is_today'] = (today.year == year and today.month == month
                                       and today.day == daynum)
                    if day['is_cup_day']:
                        month_has_games = True
                    row.append(day)
                weeks.append(row)
            result.append({'label': f"{_MESES_PT[month]} {year}", 'weeks': weeks,
                           'has_games': month_has_games,
                           'is_current': today.year == year and today.month == month})
        return result

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
