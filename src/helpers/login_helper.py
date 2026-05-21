from models import User
from flask_login import login_user
from flask import flash, redirect, url_for

class LoginHelper:

    def login(self, username, password):
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

