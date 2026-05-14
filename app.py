import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash
from flask_login import LoginManager, logout_user, login_required, current_user
from functools import wraps
from models import db, User
from src.utils import phases
from src.helpers.login_helper import LoginHelper
from src.helpers.signup_helper import SignupHelper
from src.helpers.matches_helper import MatchesHelper

### App initialization ###
load_dotenv()

login_helper = LoginHelper()
signup_helper = SignupHelper()
matches_helper = MatchesHelper()

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
        return login_helper.login(username = request.form.get('username'), 
                                  password = request.form.get('password'))
        
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    if request.method == 'POST':
        return signup_helper.signup(username = request.form.get('username'),
                                    password = request.form.get('password'),
                                    confirm_password = request.form.get('confirm_password'))

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

@app.route('/matches', methods=['GET'])
def matches():
    return render_template('matches.html')

# Admin required route
@app.route('/add_match', methods=['GET', 'POST'])
@admin_required
def create_match():
    if request.method == 'POST':
        return matches_helper.add_new_match(team_a = request.form.get('team_a'),
                                            team_b = request.form.get('team_b'),
                                            match_date = request.form.get('match_date'),
                                            round = request.form.get('round'),
                                            score_a = request.form.get('score_a'),
                                            score_b = request.form.get('score_b'))

    return render_template('add_match.html', phases=phases)

if __name__ == '__main__':
    app.run(debug=True)