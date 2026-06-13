import pytz
from datetime import datetime
from flask_login import UserMixin
from babel.dates import format_datetime
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
        """Retorna True se o palpite ainda pode ser feito (até as 03:00 da manhã do dia do jogo, no fuso horário de São Paulo)."""
        if not self.date:
            return False
        try:
            # Define o fuso horário de São Paulo
            saopaulo_tz = pytz.timezone('America/Sao_Paulo')

            # Obtém a data e hora atual no fuso horário de São Paulo
            now_saopaulo = datetime.now(saopaulo_tz)

            # Converte a data da partida para um objeto datetime e o torna timezone-aware (São Paulo)
            # Primeiro, parse a string da data (que é naive)
            match_dt_naive = datetime.strptime(self.date, "%Y-%m-%dT%H:%M")
            # Em seguida, localize-o para o fuso horário de São Paulo
            match_dt_saopaulo = saopaulo_tz.localize(match_dt_naive)

            # Define o limite como 03:00 AM do dia do jogo no fuso horário de São Paulo
            # Usamos a data da partida, mas com o horário de corte
            limit_time_saopaulo = saopaulo_tz.localize(datetime.strptime(self.date[:10], "%Y-%m-%d")).replace(hour=3, minute=0)

            return now_saopaulo < limit_time_saopaulo
        except (ValueError, TypeError):
            return False

    @property
    def formatted_date(self):
        """Retorna a data e hora da partida formatada para exibição no front-end, no fuso horário de São Paulo."""
        if not self.date:
            return "Data Indisponível"
        try:
            saopaulo_tz = pytz.timezone('America/Sao_Paulo')
            dt_object_naive = datetime.strptime(self.date, "%Y-%m-%dT%H:%M")
            dt_object_saopaulo = saopaulo_tz.localize(dt_object_naive)
            # Usamos o Babel para formatar independente do locale do SO
            return format_datetime(
                dt_object_saopaulo, 
                "EEEE, d 'de' MMMM 'de' y 'às' HH'h'mm", 
                locale='pt_BR'
            )
        except (ValueError, TypeError):
            return self.date

    @property
    def date_header(self):
        """Retorna a data formatada para cabeçalho de grupo na Home (ex: DOMINGO 14/06)."""
        if not self.date:
            return ""
        try:
            # Extrai a data da string ISO (YYYY-MM-DD)
            dt = datetime.strptime(self.date[:10], "%Y-%m-%d")
            # Formata o dia da semana e data em português
            return format_datetime(dt, "EEEE dd/MM", locale='pt_BR').upper()
        except (ValueError, TypeError):
            return ""

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

    