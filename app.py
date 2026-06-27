import os
import re
import time
import pytz
import locale

from functools import wraps
from itertools import groupby
from datetime import datetime
from dotenv import load_dotenv
from src.utils import phases, teams
from sqlalchemy.orm import joinedload
from models import db, User, Teams, Match, Guesses
from werkzeug.security import generate_password_hash
from flask_login import LoginManager, login_required, current_user
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify

from live_scores import snapshot
from src.controllers.auth import AuthController
from src.controllers.user import UserController
from src.controllers.signup import SignupController
from src.controllers.matches import MatchesController
from src.controllers.guesses import GuessesController
from src.controllers.scoring import ScoringController

### App initialization ###
load_dotenv()

auth_controller = AuthController()
user_controller = UserController()
matches_controller = MatchesController()
guesses_controller = GuessesController()
scoring_controller = ScoringController()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

db.init_app(app)

# Set locale for date formatting
try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, 'pt_BR')
    except locale.Error:
        print("Warning: Could not set locale to pt_BR. Date formatting might not be in Portuguese.")

# Login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Faça login para acessar esta página.'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def admin_required(f):
    """"
    Decorator function that determines if a route is Admin only.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # If the user is not logged in, send to login page (so login manager
        # can prompt for authentication). If logged in but not admin, show
        # an explicit unauthorized message and redirect to home.
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        if not current_user.is_admin:
            flash('Acesso negado. Usuário não autorizado.', 'error')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

with app.app_context():
    """"
    Database initialization. Currently local.
    When initializes, creates default Admin user.
    """
    db.create_all()
    # Verifica se o admin já existe
    if not User.query.filter_by(username=os.getenv('ADMIN_USER')).first():
        hashed_password = generate_password_hash(os.getenv('ADMIN_PASSWORD'))
        admin_user = User(username=os.getenv('ADMIN_USER'), password_hash=hashed_password, is_admin=True)
        db.session.add(admin_user)
        db.session.commit()
        print('Usuário default Admin criado com sucesso.')

    for team_name, team_group in teams.items():
        if not Teams.query.filter_by(name=team_name).first():
            new_team = Teams(name=team_name, group=team_group)
            db.session.add(new_team)
            db.session.commit()
            print(f'Time {team_name} criado com sucesso.')

### App routes ###
### Auth ###
@app.route('/', methods=['GET', 'POST'])
def login():
    return auth_controller.login(request, current_user)

@app.route('/logout')
@login_required
def logout():
    return auth_controller.logout()

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    return auth_controller.forgot_password(request)

### Signup ###
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    return SignupController().signup(request, current_user)

@app.route('/home')
@login_required
def home():
    ranking = user_controller.get_ranked_users()
    upcoming_matches = matches_controller.get_upcoming_matches()

    # Busca os palpites do usuário logado para mapear nos jogos
    user_guesses = Guesses.query.filter_by(user_id=current_user.id).all()
    guesses_dict = {guess.match_id: guess for guess in user_guesses}

    return render_template('home.html', ranking=ranking, upcoming_matches=upcoming_matches, user_guesses=guesses_dict)

@app.route('/matches', methods=['GET'])
@login_required
def matches():
    categorized_matches = matches_controller.get_categorized_matches()
    return render_template('matches.html', active_matches=categorized_matches['active'], previous_matches=categorized_matches['previous'])

@app.route('/guesses', methods=['GET'])
@login_required
def guesses():
    categorized_guesses = guesses_controller.get_user_guesses(current_user.id)
    pending_matches = guesses_controller.get_pending_matches_tomorrow(current_user.id)
    return render_template('guesses.html',
                           active_guesses=categorized_guesses['active'],
                           previous_guesses=categorized_guesses['previous'],
                           pending_matches=pending_matches)

@app.route('/add_guess', methods=['GET', 'POST'])
@login_required
def create_guess():
    if request.method == 'POST':
        return guesses_controller.add_guess(request, current_user)
    matches_list = matches_controller.get_available_matches_for_user(current_user.id)
    # Agrupa os jogos disponíveis por dia para montar a lista (optgroup) por data.
    editable = [m for m in matches_list if m.is_editable() and m.date]
    match_groups = []
    # groupby agrupa só elementos adjacentes — ordena por data antes (a query já
    # vem ordenada, mas deixamos explícito p/ não depender disso silenciosamente).
    for _day, grp in groupby(sorted(editable, key=lambda m: m.date), key=lambda m: m.date[:10]):
        items = list(grp)
        match_groups.append({'label': items[0].date_header,
                             'date': items[0].date[:10], 'matches': items})
    selected_match_id = request.args.get('match_id', type=int)
    calendar_months = matches_controller.get_guess_calendar(current_user.id)
    return render_template('add_guess.html', match_groups=match_groups,
                           selected_match_id=selected_match_id,
                           calendar_months=calendar_months)

### Ao Vivo (placares em tempo real via ESPN) ###
# Cache curto do snapshot: o front faz poll a cada 5s e vários usuários batem na
# mesma rota — sem isso, cada request dispara 1+N chamadas à ESPN e prende o
# worker. Com TTL curto, todos compartilham a mesma busca (dado ~no máximo 10s
# velho, ok para placar ao vivo). Processo único (gunicorn 1 worker) → dict local serve.
_AOVIVO_TTL = 10  # segundos
_aovivo_cache = {}  # 'hoje'|'YYYYMMDD' -> (timestamp, snapshot)

def _cached_aovivo(date):
    key = date or 'hoje'
    now = time.time()
    hit = _aovivo_cache.get(key)
    if hit and now - hit[0] < _AOVIVO_TTL:
        return hit[1]
    data = snapshot(date=date)
    _aovivo_cache[key] = (now, data)
    return data

@app.route('/ao-vivo')
@login_required
def ao_vivo():
    return render_template('ao_vivo.html')

@app.route('/api/ao-vivo')
@login_required
def api_ao_vivo():
    # ?date=YYYYMMDD é opcional — útil pra testar fora da Copa apontando pra um dia
    # de jogos passado. Valida o formato; qualquer coisa fora dele usa o dia de hoje.
    date = request.args.get('date')
    if not date or not re.fullmatch(r'\d{8}', date):
        date = None
    return jsonify(_cached_aovivo(date))

@app.route('/delete_guess/<int:guess_id>', methods=['POST'])
@login_required
def delete_guess(guess_id):
    return guesses_controller.delete_guess(guess_id, current_user.id)

@app.route('/edit_guess/<int:guess_id>', methods=['GET', 'POST'])
@login_required
def edit_guess(guess_id):
    if request.method == 'POST':
        return guesses_controller.edit_guess(guess_id,
                                             user_id=current_user.id,
                                             pred_a=request.form.get('pred_a'),
                                             pred_b=request.form.get('pred_b'),
                                             winner_pred=request.form.get('winner_pred'))

    guess = Guesses.query.filter_by(id=guess_id, user_id=current_user.id).options(joinedload(Guesses.match)).first()
    if not guess:
        flash('Palpite não encontrado.', 'error')
        return redirect(url_for('guesses'))

    if not guess.match.is_editable():
        flash('O prazo para editar este palpite expirou.', 'error')
        return redirect(url_for('guesses'))

    return render_template('edit_guess.html', guess=guess)

# Admin required route
@app.route('/add_match', methods=['GET', 'POST'])
@admin_required
def create_match():
    if request.method == 'POST':
        return matches_controller.add_new_match(team_a = request.form.get('team_a'),
                                            team_b = request.form.get('team_b'),
                                            match_date = request.form.get('match_date'),
                                            round = request.form.get('round'),
                                            score_a = request.form.get('score_a'),
                                            score_b = request.form.get('score_b'),
                                            winner = request.form.get('winner'))

    teams_list = [team[0] for team in Teams.query.with_entities(Teams.name).order_by(Teams.name.asc()).all()]

    return render_template('add_match.html', phases=phases, teams=teams_list)

@app.route('/delete_match/<int:match_id>', methods=['POST'])
@admin_required
def delete_match(match_id):
    # Captura os IDs dos usuários que tinham palpites nesta partida para recalcular o ranking depois
    user_ids = [g.user_id for g in Guesses.query.filter_by(match_id=match_id).all()]

    response = matches_controller.delete_match(match_id)

    # Recalcula a pontuação de todos os usuários afetados
    for uid in set(user_ids):
        scoring_controller.update_user_points(uid)

    return response

@app.route('/edit_match/<int:match_id>', methods=['GET', 'POST'])
@admin_required
def edit_match(match_id):
    if request.method == 'POST':
        response = matches_controller.edit_match(match_id,
                                          team_a=request.form.get('team_a'),
                                          team_b=request.form.get('team_b'),
                                          match_date=request.form.get('match_date'),
                                          round=request.form.get('round'),
                                          score_a=request.form.get('score_a'),
                                          score_b=request.form.get('score_b'),
                                          winner=request.form.get('winner'))
        scoring_controller.update_all_scores_for_match(match_id)
        return response
    else:
        match = Match.query.get(match_id)
        teams_list = [team[0] for team in Teams.query.with_entities(Teams.name).order_by(Teams.name.asc()).all()]
        return render_template('edit_match.html', match=match, phases=phases, teams=teams_list)

@app.route('/all_guesses', methods=['GET'])
@login_required
def all_guesses():
    # "Partidas Anteriores" é visível para todos; "Próximos Jogos" só para admin
    # (esconde os palpites de jogos futuros para evitar cópia).
    is_admin = current_user.is_admin

    categorized_matches = matches_controller.get_categorized_matches()
    previous_matches = categorized_matches['previous']
    active_matches = categorized_matches['active'] if is_admin else []
    previous_ids = {m.id for m in previous_matches}

    # Carrega só os palpites que serão exibidos (não-admin não recebe palpites de jogos futuros).
    base_query = Guesses.query.options(joinedload(Guesses.match), joinedload(Guesses.user))
    if is_admin:
        all_guesses_list = base_query.all()
    elif previous_ids:
        all_guesses_list = base_query.filter(Guesses.match_id.in_(previous_ids)).all()
    else:
        all_guesses_list = []

    # Ordenação dos palpites:
    #  - Próximos Jogos: alfabético por usuário
    #  - Partidas Anteriores: por acerto (exato > saldo > vencedor > erro) e então alfabético
    def acerto_rank(g):
        return scoring_controller.group_phase_result(
            g.match.score_a, g.match.score_b, g.pred_a, g.pred_b)

    active_guesses = sorted(
        (g for g in all_guesses_list if g.match_id not in previous_ids),
        key=lambda g: g.user.username.lower()
    ) if is_admin else []
    previous_guesses = sorted(
        (g for g in all_guesses_list if g.match_id in previous_ids),
        key=lambda g: (-acerto_rank(g), g.user.username.lower()))

    # Filtro padrão: primeira partida futura; senão a primeira ativa; senão a primeira anterior
    saopaulo_tz = pytz.timezone('America/Sao_Paulo')
    now_sp = datetime.now(saopaulo_tz)

    default_match_id = None
    is_default_in_active = True

    for m in active_matches:
        if m.date:
            m_dt = saopaulo_tz.localize(datetime.strptime(m.date, "%Y-%m-%dT%H:%M"))
            if m_dt >= now_sp:
                default_match_id = m.id
                break

    if not default_match_id:
        if active_matches:
            default_match_id = active_matches[0].id
        elif previous_matches:
            default_match_id = previous_matches[0].id
            is_default_in_active = False

    # Não-admin só tem a aba de Partidas Anteriores
    if not is_admin:
        is_default_in_active = False

    return render_template('all_guesses.html',
                           active_matches=active_matches,
                           previous_matches=previous_matches,
                           active_guesses=active_guesses,
                           previous_guesses=previous_guesses,
                           default_match_id=default_match_id,
                           is_default_in_active=is_default_in_active)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False, port=int(os.getenv('PORT', 5000)))