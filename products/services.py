import json
from pathlib import Path
from flask import g, has_request_context


def load_original():
    """products.json + products registered by an admin (no photo / name changes, hidden ones included)."""
    from products.custom import all_custom
    base = json.loads((Path(__file__).parent / 'data/products.json').read_text())
    return base + all_custom()


def hidden_slugs():
    """Slugs an admin hid or deleted (shop_product.is_active / is_deleted)."""
    if has_request_context() and 'hidden_slugs' in g: return g.hidden_slugs
    try:
        from core.extensions import db
        from shop.models import Product
        result = set(db.session.scalars(db.select(Product.slug).filter((Product.is_active.is_(False)) | (Product.is_deleted.is_(True)))))
    except Exception:
        result = set()
    if has_request_context(): g.hidden_slugs = result
    return result


def get_all_products(include_hidden=False):
    """Catalog for the site: admin photo / name changes applied, hidden and deleted products left out."""
    from products.media import overrides, apply, name_overrides, detail_overrides, apply_gallery
    products = apply(apply_gallery(load_original()), overrides())
    names = name_overrides()
    details = detail_overrides()
    for p in products:
        if p['slug'] in names: p['name'] = names[p['slug']]
        row = details.get(p['slug'])
        if row:  # admin-edited ingredient list (Products tab)
            d = dict(p.get('details') or {})
            d.update(ingredients=row.ingredients, sweetened_with=row.sweetened_with, confirmed=row.confirmed)
            p['details'] = d
    if not include_hidden:
        hidden = hidden_slugs()
        products = [p for p in products if p['slug'] not in hidden]
    return sorted(products, key=lambda p: p.get('order', 99))


def get_product(slug, include_hidden=False):
    return next((p for p in get_all_products(include_hidden) if p['slug'] == slug), None)


def image_url(src):
    """Same rule as the img_url template macro."""
    if not src: return ''
    return src if src.startswith('/') else ('/images/' + src if '/' in src else '/images/product_image/web/cutout/' + src)
