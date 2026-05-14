import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from functools import wraps
from models import db, User, Match
from src.helpers.signup_helper import SignupHelper

### App initialization ###
load_dotenv()

signup_helper = SignupHelper()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('SQLALCHEMY_DATABASE_URI')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

db.init_app(app)

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

### App routes ###
@app.route('/', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        username = username.strip() if username else ''
        if not username:
            flash('O nome de usuário é obrigatório.', 'error')
            return redirect(url_for('login'))
        if not password:
            flash('A senha é obrigatória.', 'error')
            return redirect(url_for('login'))

        user = User.query.filter_by(username=username).first()

        if user is None:
            flash('Usuário não encontrado.', 'error')
            return redirect(url_for('login'))

        if not user.check_password(password):
            flash('Senha incorreta.', 'error')
            return redirect(url_for('login'))

        # Credenciais corretas
        login_user(user)
        flash('Login realizado com sucesso.', 'success')
        return redirect(url_for('home'))
        
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if User.query.filter_by(username=username).first():
            flash('Nome de usuário já existe.', 'error')
        elif password != confirm_password:
            flash('As senhas devem ser iguais.', 'error')
        elif not signup_helper.is_password_strong(password):
            flash('A senha deve ter no mínimo 8 caracteres, contendo pelo menos 1 número e 1 caractere especial.', 'error')
        else:
            hashed_password = generate_password_hash(password)
            new_user = User(username=username, password_hash=hashed_password, is_admin=False)
            db.session.add(new_user)
            db.session.commit()
            flash('Cadastro realizado com sucesso.', 'success')
            return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/home')
@login_required
def home():
    return render_template('home.html')

# Admin required route
@app.route('/matches', methods=['GET', 'POST'])
@admin_required
def create_match():
    phases = [
        'Fase de Grupos',
        'Oitavas de Final',
        'Quartas de Final',
        'Semifinal',
        'Final'
    ]

    if request.method == 'POST':
        team_a = request.form.get('team_a')
        team_b = request.form.get('team_b')
        match_date = request.form.get('match_date')
        round = request.form.get('round')
        score_a = request.form.get('score_a')
        score_b = request.form.get('score_b')

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
        
        match = Match.query.filter_by(team_a=team_a, team_b=team_b, match_date=match_date).first()
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

    return render_template('matches.html', phases=phases)

if __name__ == '__main__':
    app.run(debug=True)