import re
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from functools import wraps
from models import db, User

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///bolao.db'
app.config['SECRET_KEY'] = 'e59aa8041cb2c6df6c48ec2ab693b242'

db.init_app(app)

# Login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Faça login para acessar esta página.'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Admin routes
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('Acesso negado. Usuário não autorizado.', 'error')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

# DB Init
with app.app_context():
    db.create_all()
    # Verifica se o admin já existe
    if not User.query.filter_by(username='admin').first():
        hashed_password = generate_password_hash('Admin@1234')
        admin_user = User(username='admin', password=hashed_password, is_admin=True)
        db.session.add(admin_user)
        db.session.commit()
        print("Usuário Admin criado com sucesso!")

# --- FUNÇÃO DE VALIDAÇÃO DE SENHA ---
def is_password_strong(password):
    if len(password) < 8:
        return False
    if not re.search(r"\d", password): # Pelo menos 1 número
        return False
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password): # Pelo menos 1 especial
        return False
    return True

# --- ROTAS ---

@app.route('/', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Regra: Campos em branco
        if not username or not password:
            flash("Campo obrigatório faltando.", "error")
            return redirect(url_for('login'))

        user = User.query.filter_by(username=username).first()

        # Regra: Usuário ou senha inexistentes/incorretos
        if not user or not check_password_hash(user.password, password):
            flash("Usuário ou senha inexistentes/incorretos.", "error")
            return redirect(url_for('login'))

        login_user(user)
        return redirect(url_for('home'))
        
    return render_template('login.html')

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Regras de negócio
        if User.query.filter_by(username=username).first():
            flash("Este usuário já existe. Escolha outro.", "error")
        elif password != confirm_password:
            flash("As senhas não coincidem.", "error")
        elif not is_password_strong(password):
            flash("A senha deve ter no mínimo 8 caracteres, contendo pelo menos 1 número e 1 caractere especial.", "error")
        else:
            # Tudo certo, cria o usuário
            hashed_password = generate_password_hash(password)
            new_user = User(username=username, password=hashed_password, is_admin=False)
            db.session.add(new_user)
            db.session.commit()
            flash("Cadastro realizado com sucesso! Faça login.", "success")
            return redirect(url_for('login'))

    return render_template('cadastro.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# Rota genérica apenas para logged in users
@app.route('/home')
@login_required
def home():
    return render_template('home.html') # Crie este HTML depois com os menus

# Apenas Admin pode acessar
@app.route('/create_match')
@admin_required
def create_match():
    return "Página de criação de jogos (Apenas Admin pode ver isso!)"

if __name__ == '__main__':
    app.run(debug=True)