from models import db, User

class UserController:
    def add_user(self, username, password_hash, is_admin=False):
        new_user = User(username=username, password_hash=password_hash, is_admin=is_admin)
        db.session.add(new_user)
        db.session.commit()
        return new_user

    def get_user_by_username(self, username):
        user = User.query.filter_by(username=username).first()
        return user
    
    def get_ranked_users(self):
        ranking = User.query.order_by(User.points.desc(), User.username.asc()).all()
        return ranking
