import re
from models import db, User
from werkzeug.security import generate_password_hash
from flask import flash, redirect, url_for

class SignupHelper:
    def __is_password_strong(self, password):
        if len(password) < 8:
            return False
        if not re.search(r"\d", password): # Pelo menos 1 número
            return False
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password): # Pelo menos 1 especial
            return False
        return True
    
    def signup(self, username, password, confirm_password):
        if User.query.filter_by(username=username).first():
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
            new_user = User(username=username, password_hash=hashed_password, is_admin=False)
            db.session.add(new_user)
            db.session.commit()
            flash('Cadastro realizado com sucesso.', 'success')
            return redirect(url_for('login'))