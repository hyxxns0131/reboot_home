from datetime import datetime, timezone
from flask_login import UserMixin
from core.extensions import db, login_manager

class User(UserMixin, db.Model):
    __tablename__ = 'auth_user'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='customer')
    name = db.Column(db.String(100), nullable=False)
    points = db.Column(db.Integer, nullable=False, default=0)
    language = db.Column(db.String(2), nullable=False, default='en')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id)) if user_id.isdigit() else None
