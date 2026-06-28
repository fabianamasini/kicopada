import os
import sys
import time
import pytz
import locale

from functools import wraps
from datetime import datetime
from dotenv import load_dotenv
from src.utils import teams
from sqlalchemy.orm import joinedload
from models import db, User, Teams, Match, Guesses
from werkzeug.security import generate_password_hash
from flask_login import LoginManager, login_required, current_user
from flask import Flask, render_template, request, redirect, url_for, flash

from match_sync import sync_matches
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

# Sincronização automática das partidas com a ESPN (cadastro + placar). A ESPN é a
# ÚNICA fonte — não há cadastro manual. Roda no boot e também a cada acesso, mas no
# máximo uma busca por minuto (_SYNC_TTL), pra o placar não ficar preso a restart.
_SYNC_TTL = 60          # segundos entre buscas (cache p/ não martelar a API)
_last_sync = [0.0]

def _sync_matches_and_scores(force=False):
    now = time.time()
    if not force and now - _last_sync[0] < _SYNC_TTL:
        return
    _last_sync[0] = now
    try:
        result = sync_matches(log=lambda _m: None)
        for match_id in result.get('updated', []):
            scoring_controller.update_all_scores_for_match(match_id)
        if result.get('inserted'):
            print(f"{result['inserted']} partida(s) cadastrada(s) automaticamente.")
    except Exception as e:
        print(f"Aviso: sincronização automática de partidas falhou ({e}).")

@app.before_request
def _auto_sync_before_request():
    # Atualiza jogos/placar ao acessar o app (cacheado). Pulado em testes e quando
    # desligado por env; ignora estáticos e requisições sem rota.
    if app.config.get('TESTING') or os.getenv('AUTO_SYNC_MATCHES', '1') == '0':
        return
    if request.endpoint in (None, 'static'):
        return
    _sync_matches_and_scores()

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

    # Sincroniza as partidas (cadastro + placar) já no boot. Pulado na suíte de
    # testes (sem rede no CI) e desligável com AUTO_SYNC_MATCHES=0.
    _running_tests = 'pytest' in sys.modules or 'unittest' in sys.modules
    if os.getenv('AUTO_SYNC_MATCHES', '1') != '0' and not _running_tests:
        _sync_matches_and_scores(force=True)

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
    selected_match_id = request.args.get('match_id', type=int)
    return render_template('add_guess.html', matches=matches_list, selected_match_id=selected_match_id)

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