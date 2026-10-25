"""Products registered on the admin "Add product" page (seasonal / limited items).
Stored as JSON in the DB with the same shape as products.json, so every page treats them the same way."""
import re
from datetime import datetime, timezone
from core.extensions import db

INGREDIENTS = ['A-HAT', 'Hovenia dulcis (Oriental raisin tree) fruit']


class CustomProduct(db.Model):
    __tablename__ = 'products_custom'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), nullable=False, unique=True)
    data = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


def slugify(text):
    return re.sub(r'-+', '-', re.sub(r'[^a-z0-9]+', '-', text.lower())).strip('-')[:60] or 'product'


def all_custom():
    try:
        return [row.data for row in db.session.scalars(db.select(CustomProduct).order_by(CustomProduct.id))]
    except Exception:
        return []
