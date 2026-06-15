from models import db
from .user import UserController
from .utils import is_password_strong
from flask_login import login_user, logout_user
from flask import render_template, redirect, url_for, flash

class AuthController:
    def login(self, req, current_user=None):
        if current_user.is_authenticated:
            return redirect(url_for('home'))

        if req.method == 'POST':
            username = req.form.get('username')
            username = username.strip() if username else ''

            password = req.form.get('password')

            if not username:
                flash('O nome de usuário é obrigatório.', 'error')
                return redirect(url_for('login'))
            if not password:
                flash('A senha é obrigatória.', 'error')
                return redirect(url_for('login'))
            
            user = UserController().get_user_by_username(username)

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


    def forgot_password(self, request):
        if request.method == 'POST':
            username = request.form.get('username')
            username = username.strip() if username else ''
            new_password = request.form.get('new_password')
            confirm_new_password = request.form.get('confirm_new_password')

            if not username:
                flash('O nome de usuário é obrigatório.', 'error')
                return redirect(url_for('forgot_password'))

            user = UserController().get_user_by_username(username)

            if user is None:
                flash('Usuário não encontrado.', 'error')
                return redirect(url_for('forgot_password'))
            elif new_password != confirm_new_password:
                flash('As senhas devem ser iguais.', 'error')
                return redirect(url_for('forgot_password'))
            elif not is_password_strong(new_password):
                flash('A senha deve ter no mínimo 8 caracteres, contendo pelo menos 1 número e 1 caractere especial.', 'error')
                return redirect(url_for('forgot_password'))
            else:
                user.set_password(new_password)
                db.session.commit()
                flash('Sua senha foi redefinida com sucesso. Faça login com a nova senha.', 'success')
                return redirect(url_for('login'))
        
        return render_template('forgot_password.html')
    
    def logout(self):
        logout_user()
        return redirect(url_for('login'))