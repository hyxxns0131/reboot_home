from datetime import datetime, timezone
from core.extensions import db


class Review(db.Model):
    """Customer product review. Sentiment is derived from the star rating (see products/reviews.py)."""
    __tablename__ = 'products_review'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('shop_product.id'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('auth_user.id'))  # NULL for dummy reviews
    reviewer_name = db.Column(db.String(60), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(100), nullable=False, default='')
    body = db.Column(db.String(1000), nullable=False)
    sentiment = db.Column(db.String(10), nullable=False)  # positive / neutral / negative
    status = db.Column(db.String(10), nullable=False, default='published')  # published / held
    is_dummy = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    product = db.relationship('Product')
    __table_args__ = (db.UniqueConstraint('product_id', 'user_id', name='uq_review_product_user'),
                      db.CheckConstraint('rating >= 1 AND rating <= 5', name='ck_review_rating'))
