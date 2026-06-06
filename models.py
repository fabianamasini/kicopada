from datetime import datetime
from flask_login import UserMixin
import locale
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    points = db.Column(db.Integer, default=0)

    def set_password(self, password):
        """Transforma a senha em texto plano em um hash seguro."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Compara a senha digitada com o hash salvo no banco."""
        return check_password_hash(self.password_hash, password)

class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    team_a = db.Column(db.String(50), nullable=False)
    team_b = db.Column(db.String(50), nullable=False)
    date = db.Column(db.String(20))
    round = db.Column(db.String(50))
    score_a = db.Column(db.Integer, nullable=True)
    score_b = db.Column(db.Integer, nullable=True)
    winner = db.Column(db.String(1), nullable=True) # 'A' ou 'B' para mata-mata
    penalty_score_a = db.Column(db.Integer, nullable=True)
    penalty_score_b = db.Column(db.Integer, nullable=True)
    is_knockout = db.Column(db.Boolean, default=False)

    def is_editable(self):
        """Retorna True se o palpite ainda pode ser feito (até 23:59 do dia anterior ao jogo)."""
        if not self.date:
            return False
        try:
            # Considera o início do dia do jogo (00:00:00) como o limite
            match_date = datetime.strptime(self.date[:10], "%Y-%m-%d")
            return datetime.now() < match_date
        except (ValueError, TypeError):
            return False

    @property
    def formatted_date(self):
        """Retorna a data e hora da partida formatada para exibição no front-end."""
        if not self.date:
            return "Data Indisponível"
        try:
            dt_object = datetime.strptime(self.date, "%Y-%m-%dT%H:%M")
            return dt_object.strftime("%A, %d/%m/%Y às %Hh%M")
        except (ValueError, TypeError):
            return self.date

class Guesses(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    match_id = db.Column(db.Integer, db.ForeignKey('match.id'))
    pred_a = db.Column(db.Integer)
    pred_b = db.Column(db.Integer)
    winner_pred = db.Column(db.String(1), nullable=True) # 'A' ou 'B' para mata-mata
    penalty_pred_a = db.Column(db.Integer, nullable=True)
    penalty_pred_b = db.Column(db.Integer, nullable=True)
    is_knockout = db.Column(db.Boolean, default=False)

    user = db.relationship('User', backref=db.backref('guesses', lazy=True))
    match = db.relationship('Match', backref=db.backref('guesses', lazy=True))

class Teams(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    group = db.Column(db.String(10))
    points = db.Column(db.Integer, default=0)
    disqualified = db.Column(db.Boolean, default=False)

class Odds(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('match.id'))
    team_a_odds = db.Column(db.Float, nullable=False)
    team_b_odds = db.Column(db.Float, nullable=False)
    draw_odds = db.Column(db.Float, nullable=False)

    match = db.relationship('Match', backref=db.backref('odds', uselist=False))

    