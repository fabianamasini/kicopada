import re
from .user import UserController
from werkzeug.security import generate_password_hash
from flask import flash, redirect, url_for, render_template

class SignupController:
    def __is_password_strong(self, password):
        if len(password) < 8:
            return False
        if not re.search(r"\d", password): # Pelo menos 1 número
            return False
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password): # Pelo menos 1 especial
            return False
        return True
    
    def signup(self, request, current_user=None):
        if current_user.is_authenticated:
            return redirect(url_for('home'))
        
        if request.method == 'POST':
            username = request.form.get('username')
            username = username.strip() if username else ''
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')

            if UserController().get_user_by_username(username):
                flash('Nome de usuário já existe.', 'error')
                return redirect(url_for('signup'))
            elif password != confirm_password:
                flash('As senhas devem ser iguais.', 'error')
                return redirect(url_for('signup'))
            elif not self.__is_password_strong(password):
                flash('A senha deve ter no mínimo 8 caracteres, contendo pelo menos 1 número e 1 caractere especial.', 'error')
                return redirect(url_for('signup'))
            else:
                hashed_password = generate_password_hash(password)
                UserController().add_user(username=username, password_hash=hashed_password, is_admin=False)
                flash('Cadastro realizado com sucesso.', 'success')
                return redirect(url_for('login'))
        
        return render_template('signup.html')