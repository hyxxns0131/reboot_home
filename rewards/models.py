from datetime import datetime, timezone
from core.extensions import db

def now():
    return datetime.now(timezone.utc)

class Activity(db.Model):
    __tablename__ = 'auth_activity'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('auth_user.id'), nullable=False, index=True)
    action = db.Column(db.String(40), nullable=False)
    details = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    user = db.relationship('User')

class CartItem(db.Model):
    __tablename__ = 'shop_cart_item'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('auth_user.id'), nullable=False)
    option_id = db.Column(db.Integer, db.ForeignKey('shop_product_option.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    option = db.relationship('ProductOption')
    __table_args__ = (db.UniqueConstraint('user_id', 'option_id'), db.CheckConstraint('quantity >= 1 AND quantity <= 10'))

class Game(db.Model):
    __tablename__ = 'rewards_game'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('auth_user.id'), nullable=False)
    day = db.Column(db.Date, nullable=False)
    board = db.Column(db.JSON, nullable=False)
    matched = db.Column(db.JSON, nullable=False, default=list)
    first = db.Column(db.Integer)
    moves = db.Column(db.Integer, nullable=False, default=0)
    version = db.Column(db.Integer, nullable=False, default=0)
    complete = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    completed_at = db.Column(db.DateTime)
    __table_args__ = (db.UniqueConstraint('user_id', 'day', name='uq_game_user_day'),)

class PointEntry(db.Model):
    __tablename__ = 'rewards_point_entry'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('auth_user.id'), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(30), nullable=False)
    reference = db.Column(db.String(100), nullable=False, unique=True)
    order_id = db.Column(db.Integer, db.ForeignKey('shop_order.id'))
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    user = db.relationship('User')

class CheckoutReceipt(db.Model):
    __tablename__ = 'shop_checkout_receipt'
    token = db.Column(db.String(100), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('auth_user.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('shop_order.id'), unique=True)
