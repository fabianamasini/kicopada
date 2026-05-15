from flask_login import UserMixin
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

class Prediction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    match_id = db.Column(db.Integer, db.ForeignKey('match.id'))
    pred_a = db.Column(db.Integer)
    pred_b = db.Column(db.Integer)

class Teams(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    group = db.Column(db.String(10))
    points = db.Column(db.Integer, default=0)
    disqualified = db.Column(db.Boolean, default=False)

    