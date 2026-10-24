"""Additive upgrades for the initial SQLite/PostgreSQL schema. Never drops data."""
from sqlalchemy import inspect, text
from core.extensions import db

ADDITIONS = {
    'auth_user': {'points': 'INTEGER NOT NULL DEFAULT 0', 'language': "VARCHAR(2) NOT NULL DEFAULT 'en'"},
    'shop_order_item': {'points_used': 'INTEGER NOT NULL DEFAULT 0'},
    'shop_order': {'points_used': 'INTEGER NOT NULL DEFAULT 0'},
}

def upgrade_database():
    db.create_all()
    for table, additions in ADDITIONS.items():
        existing = {c['name'] for c in inspect(db.engine).get_columns(table)}
        for column, definition in additions.items():
            if column not in existing:
                db.session.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {definition}'))
    db.session.commit()
