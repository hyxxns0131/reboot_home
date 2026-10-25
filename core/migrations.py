"""Additive upgrades for the initial SQLite/PostgreSQL schema. Never drops data."""
from sqlalchemy import inspect, text
from core.extensions import db

ADDITIONS = {
    'auth_user': {'points': 'INTEGER NOT NULL DEFAULT 0', 'language': "VARCHAR(2) NOT NULL DEFAULT 'en'"},
    'shop_order_item': {'points_used': 'INTEGER NOT NULL DEFAULT 0'},
    'shop_order': {'points_used': 'INTEGER NOT NULL DEFAULT 0'},
    'shop_product': {'is_deleted': 'BOOLEAN NOT NULL DEFAULT FALSE'},
    'shop_referral_link': {'landing': "VARCHAR(120) NOT NULL DEFAULT ''"},
    'core_message': {'user_id': 'INTEGER', 'topic': "VARCHAR(30) NOT NULL DEFAULT ''", 'order_id': 'INTEGER',
                     'status': "VARCHAR(12) NOT NULL DEFAULT 'new'", 'reply': 'TEXT', 'replied_at': 'TIMESTAMP'},
}

def _fill_value(column):
    """A safe value for rows that existed before a NOT NULL column was added (README §32)."""
    from sqlalchemy import Boolean, Integer, Numeric, String, Text
    default = column.default.arg if column.default is not None and not callable(column.default.arg) else None
    if isinstance(default, bool): return 'TRUE' if default else 'FALSE'
    if isinstance(default, (int, float)): return str(default)
    if isinstance(default, str): return "'" + default.replace("'", "''") + "'"
    if isinstance(column.type, Boolean): return 'FALSE'
    if isinstance(column.type, (Integer, Numeric)): return '0'
    if isinstance(column.type, (String, Text)): return "''"
    return None


def _add_missing_model_columns():
    """Any column a model has but the existing table lacks is added (tables made by an older version of the code).
    NOT NULL columns get a default for old rows; types without a safe default are added as nullable."""
    insp = inspect(db.engine)
    tables = set(insp.get_table_names())
    for table in db.metadata.sorted_tables:
        if table.name not in tables: continue
        existing = {c['name'] for c in insp.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing: continue
            ddl = f'{column.name} {column.type.compile(dialect=db.engine.dialect)}'
            fill = _fill_value(column)
            if fill is not None:
                ddl += f' DEFAULT {fill}' + ('' if column.nullable else ' NOT NULL')
            db.session.execute(text(f'ALTER TABLE {table.name} ADD COLUMN {ddl}'))


def upgrade_database():
    db.create_all()
    for table, additions in ADDITIONS.items():
        existing = {c['name'] for c in inspect(db.engine).get_columns(table)}
        for column, definition in additions.items():
            if column not in existing:
                db.session.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {definition}'))
    db.session.commit()
    _add_missing_model_columns()
    db.session.commit()
