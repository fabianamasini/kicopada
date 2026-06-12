import os
import locale
from functools import wraps
from dotenv import load_dotenv
from src.utils import phases, teams
from sqlalchemy.orm import joinedload
from models import db, User, Teams, Match, Guesses
from werkzeug.security import generate_password_hash
from flask_login import LoginManager, login_required, current_user
from flask import Flask, render_template, request, redirect, url_for, flash
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

### Signup ###
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    return SignupController().signup(request, current_user)

@app.route('/home')
@login_required
def home():
    ranking = user_controller.get_ranked_users()
    upcoming_matches = matches_controller.get_upcoming_matches()
    return render_template('home.html', ranking=ranking, upcoming_matches=upcoming_matches)

@app.route('/matches', methods=['GET'])
@login_required
def matches():
    all_matches = matches_controller.get_all_matches()
    return render_template('matches.html', matches=all_matches)

@app.route('/guesses', methods=['GET'])
@login_required
def guesses():
    categorized_guesses = guesses_controller.get_user_guesses(current_user.id)
    return render_template('guesses.html', active_guesses=categorized_guesses['active'], previous_guesses=categorized_guesses['previous'])

@app.route('/add_guess', methods=['GET', 'POST'])
@login_required
def create_guess():
    if request.method == 'POST':
        return guesses_controller.add_guess(request, current_user)
    matches_list = matches_controller.get_all_matches()
    return render_template('add_guess.html', matches=matches_list)

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
                                             winner_pred=request.form.get('winner_pred'),
                                         penalty_a=request.form.get('penalty_a'),
                                         penalty_b=request.form.get('penalty_b'))

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
                                            score_b = request.form.get('score_b'))
    
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
        guesses_controller.update_user_points(uid)

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
                                          score_b=request.form.get('score_b'))
        scoring_controller.update_all_scores_for_match(match_id)
        return response
    else:
        match = Match.query.get(match_id)
        teams_list = [team[0] for team in Teams.query.with_entities(Teams.name).order_by(Teams.name.asc()).all()]
        return render_template('edit_match.html', match=match, phases=phases, teams=teams_list)

if __name__ == '__main__':
    app.run(debug=True)