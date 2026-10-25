"""Product photos replaced by an admin (Products tab). Stored in the DB because Render's disk is reset on every deploy.
An override is keyed by the original image path from products.json, so every place that shows that photo updates at once."""
import io
from datetime import datetime, timezone
from flask import g, has_request_context
from core.extensions import db

MAX_SIDE = 1600
ALLOWED = {'JPEG', 'PNG', 'WEBP'}


class ProductImage(db.Model):
    __tablename__ = 'products_image'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), nullable=False)
    original = db.Column(db.String(200), nullable=False, unique=True)  # path in products.json
    data = db.Column(db.LargeBinary, nullable=False)                  # WEBP bytes
    version = db.Column(db.Integer, nullable=False, default=1)
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class ProductText(db.Model):
    """Product name changed by an admin (Products tab). Applied on top of products.json everywhere."""
    __tablename__ = 'products_text'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), nullable=False, unique=True)
    name = db.Column(db.String(80), nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


def name_overrides():
    if has_request_context() and 'name_overrides' in g: return g.name_overrides
    try: result = dict(db.session.execute(db.select(ProductText.slug, ProductText.name)).all())
    except Exception: result = {}
    if has_request_context(): g.name_overrides = result
    return result


def url_for_image(img):
    return f'/media/products/{img.id}.webp?v={img.version}'


def overrides():
    """{original path: new url}, cached for the request."""
    if has_request_context() and 'image_overrides' in g: return g.image_overrides
    try:
        rows = db.session.execute(db.select(ProductImage.id, ProductImage.original, ProductImage.version)).all()
        result = {o: f'/media/products/{i}.webp?v={v}' for i, o, v in rows}
    except Exception:
        result = {}
    if has_request_context(): g.image_overrides = result
    return result


def apply(value, table):
    if not table: return value
    if isinstance(value, dict): return {k: apply(v, table) for k, v in value.items()}
    if isinstance(value, list): return [apply(v, table) for v in value]
    if isinstance(value, str): return table.get(value, value)
    return value


def to_webp(raw):
    """Check the upload really is a JPEG/PNG/WEBP image, shrink to 1600 px, keep transparency, save as WEBP."""
    from PIL import Image, ImageOps
    img = Image.open(io.BytesIO(raw))
    if img.format not in ALLOWED: raise ValueError('Upload a JPG, PNG or WEBP image.')
    img.load()
    img = ImageOps.exif_transpose(img)
    if img.width * img.height > 40_000_000: raise ValueError('That image is too large.')
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    img = img.convert('RGBA') if img.mode in ('P', 'LA', 'RGBA', 'PA') or 'transparency' in img.info else img.convert('RGB')
    out = io.BytesIO(); img.save(out, 'WEBP', quality=86, method=4)
    return out.getvalue()


def image_slots(product):
    """Every distinct photo of a product with where it is used. Uses the ORIGINAL products.json data."""
    slots = {}
    def add(src, where):
        if src: slots.setdefault(src, []).append(where)
    add(product['images'].get('main'), 'Main (product list & cart)')
    add(product['images'].get('card'), 'Product card')
    for o in product['options']: add(o.get('image'), f"Option: {o['label']}")
    for item in product['images'].get('gallery', []): add(item.get('src'), f"Gallery: {item.get('label', '')}")
    return [dict(src=s, used=w) for s, w in slots.items()]


from flask import Blueprint, Response, abort  # noqa: E402

bp = Blueprint('media', __name__)


@bp.get('/media/products/<int:image_id>.webp')
def serve(image_id):
    img = db.session.get(ProductImage, image_id) or abort(404)
    resp = Response(img.data, mimetype='image/webp')
    resp.direct_passthrough = True  # keep the long cache header below (app sets no-store otherwise)
    resp.headers['Cache-Control'] = 'public, max-age=31536000, immutable'  # URL carries ?v=version
    return resp
