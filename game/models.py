"""Game part tables (prefix game_). Points themselves live in rewards_point_entry + auth_user.points."""
from core.extensions import db
from game.services import utcnow


class GameRun(db.Model):
    """One play of one mini game by a signed-in customer. Guests play without a run."""
    __tablename__ = 'game_run'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('auth_user.id'), nullable=False)
    game = db.Column(db.String(30), nullable=False)
    day = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(12), nullable=False, default='open')  # open / finished / rejected / expired
    score = db.Column(db.Integer)
    points = db.Column(db.Integer, nullable=False, default=0)
    started_at = db.Column(db.DateTime, nullable=False, default=utcnow)  # naive UTC
    finished_at = db.Column(db.DateTime)
    __table_args__ = (db.Index('ix_game_run_user_day', 'user_id', 'day'),)


class GameDaily(db.Model):
    """Points earned from games per customer per UTC day. Guards the 1,000 P daily cap."""
    __tablename__ = 'game_daily'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('auth_user.id'), nullable=False)
    day = db.Column(db.Date, nullable=False)
    earned = db.Column(db.Integer, nullable=False, default=0)
    __table_args__ = (db.UniqueConstraint('user_id', 'day', name='uq_game_daily_user_day'),
                      db.CheckConstraint('earned >= 0 AND earned <= 1000', name='ck_game_daily_cap'))
