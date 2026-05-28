from flask import render_template, redirect, url_for, flash
from flask_login import login_user, logout_user
from .user import UserController

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
    
    def logout(self):
        logout_user()
        return redirect(url_for('login'))