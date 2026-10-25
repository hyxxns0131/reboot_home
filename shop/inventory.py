"""Inventory per sales option (SKU). Orders placed on the site take stock; admins set stock by hand or by CSV."""
import csv
import io
import random
from datetime import datetime, timezone
from flask import g, has_request_context
from flask_login import current_user
from core.extensions import db
from shop.models import ProductOption


def now():
    return datetime.now(timezone.utc)


class Inventory(db.Model):
    __tablename__ = 'shop_inventory'
    id = db.Column(db.Integer, primary_key=True)
    option_id = db.Column(db.Integer, db.ForeignKey('shop_product_option.id'), nullable=False, unique=True)
    on_hand = db.Column(db.Integer, nullable=False, default=0)
    reorder_level = db.Column(db.Integer, nullable=False, default=50)
    updated_at = db.Column(db.DateTime, nullable=False, default=now)
    option = db.relationship('ProductOption')
    __table_args__ = (db.CheckConstraint('on_hand >= 0', name='ck_inventory_on_hand'),)


class StockMove(db.Model):
    """Every stock change: seed / manual / csv_set / csv_add / order."""
    __tablename__ = 'shop_stock_move'
    id = db.Column(db.Integer, primary_key=True)
    option_id = db.Column(db.Integer, db.ForeignKey('shop_product_option.id'), nullable=False, index=True)
    change = db.Column(db.Integer, nullable=False)
    on_hand_after = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(20), nullable=False)
    note = db.Column(db.String(200), nullable=False, default='')
    user_id = db.Column(db.Integer, db.ForeignKey('auth_user.id'))
    created_at = db.Column(db.DateTime, nullable=False, default=now)
    option = db.relationship('ProductOption')


def seed_inventory(seed=11):
    """Dummy stock for every active option that has none yet. Same numbers on every machine.
    Two options start low so the admin page shows its alerts."""
    rng = random.Random(seed)
    options = db.session.scalars(db.select(ProductOption).order_by(ProductOption.id)).all()
    have = set(db.session.scalars(db.select(Inventory.option_id)))
    for i, o in enumerate(options):
        qty = rng.randint(120, 480)
        if o.sku == 'drink-balance-cherry': qty = 18          # low stock example
        if o.sku == 'jelly-balance-pouch': qty = 35           # low stock example
        if o.id in have: continue
        db.session.add(Inventory(option_id=o.id, on_hand=qty, reorder_level=40 if o.unit_count == 1 else 25))
        db.session.add(StockMove(option_id=o.id, change=qty, on_hand_after=qty, reason='seed', note='Dummy opening stock'))


def stock_map():
    """{sku: (on_hand, reorder_level)} for tracked options, cached for the request."""
    if has_request_context() and 'stock_map' in g: return g.stock_map
    rows = db.session.execute(db.select(ProductOption.sku, Inventory.on_hand, Inventory.reorder_level).join(Inventory, Inventory.option_id == ProductOption.id)).all()
    result = {sku: (on, re) for sku, on, re in rows}
    if has_request_context(): g.stock_map = result
    return result


def stock_for(sku):
    """Template helper: None = not tracked, else dict(on_hand, low, out)."""
    s = stock_map().get(sku)
    if s is None: return None
    return dict(on_hand=s[0], low=0 < s[0] <= s[1], out=s[0] <= 0)


def take(option, qty, note=''):
    """Remove stock for an order. Returns False (and changes nothing) if not enough is left."""
    row = db.session.scalar(db.select(Inventory).filter_by(option_id=option.id))
    if row is None: return True  # untracked option
    done = db.session.execute(db.update(Inventory).where(Inventory.id == row.id, Inventory.on_hand >= qty)
                              .values(on_hand=Inventory.on_hand - qty, updated_at=now()), execution_options={'synchronize_session': False})
    if done.rowcount != 1: return False
    after = db.session.scalar(db.select(Inventory.on_hand).filter_by(id=row.id))
    db.session.add(StockMove(option_id=option.id, change=-qty, on_hand_after=after, reason='order', note=note,
                             user_id=current_user.id if current_user.is_authenticated else None))
    return True


def set_stock(option, on_hand=None, reorder_level=None, add=None, reason='manual', note=''):
    row = db.session.scalar(db.select(Inventory).filter_by(option_id=option.id))
    if row is None:
        row = Inventory(option_id=option.id, on_hand=0, reorder_level=50); db.session.add(row); db.session.flush()
    before = row.on_hand
    if add is not None: row.on_hand = before + add
    elif on_hand is not None: row.on_hand = on_hand
    if reorder_level is not None: row.reorder_level = reorder_level
    row.updated_at = now()
    if row.on_hand != before:
        db.session.add(StockMove(option_id=option.id, change=row.on_hand - before, on_hand_after=row.on_hand, reason=reason, note=note[:200],
                                 user_id=current_user.id if current_user.is_authenticated else None))
    return row


CSV_FIELDS = ['sku', 'product', 'option', 'on_hand', 'reorder_level']


def export_csv():
    out = io.StringIO(newline='')
    w = csv.writer(out); w.writerow(CSV_FIELDS)
    rows = db.session.execute(db.select(ProductOption, Inventory).outerjoin(Inventory, Inventory.option_id == ProductOption.id)
                              .filter(ProductOption.is_active.is_(True)).order_by(ProductOption.id)).all()
    for o, inv in rows:
        w.writerow([o.sku, o.product.name, o.label, inv.on_hand if inv else 0, inv.reorder_level if inv else 50])
    return out.getvalue()


def parse_csv(text, mode):
    """Validate an uploaded file. Returns (changes, errors). mode 'set' = on_hand is the new count,
    'add' = on_hand is added (received stock). Columns: sku, on_hand, optional reorder_level (others ignored)."""
    errors, changes = [], []
    reader = csv.DictReader(io.StringIO(text.lstrip('﻿')))
    header = [h.strip().lower() for h in (reader.fieldnames or [])]
    if 'sku' not in header or 'on_hand' not in header:
        return [], ['The file needs the columns sku and on_hand (download the template).']
    reader.fieldnames = header
    options = {o.sku: o for o in db.session.scalars(db.select(ProductOption).filter_by(is_active=True))}
    seen = set()
    for n, row in enumerate(reader, start=2):
        sku = (row.get('sku') or '').strip()
        if not sku and not any((v or '').strip() for v in row.values() if isinstance(v, str)): continue
        if sku not in options: errors.append(f'Row {n}: unknown SKU "{sku[:40]}"'); continue
        if sku in seen: errors.append(f'Row {n}: {sku} appears twice'); continue
        seen.add(sku)
        try:
            qty = int((row.get('on_hand') or '').strip())
            level = int(row['reorder_level'].strip()) if (row.get('reorder_level') or '').strip() else None
        except ValueError:
            errors.append(f'Row {n}: on_hand and reorder_level must be whole numbers'); continue
        limit = (-100000 if mode == 'add' else 0)
        if not limit <= qty <= 100000 or (level is not None and not 0 <= level <= 100000):
            errors.append(f'Row {n}: numbers out of range'); continue
        changes.append((options[sku], qty, level))
    if not changes and not errors: errors.append('The file has no rows.')
    return changes, errors
