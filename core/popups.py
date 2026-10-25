"""Site popups managed on the admin Homepage manager tab: text + optional image + optional button.
Visitors see the newest live popup once; "Don't show today" hides it until tomorrow (stored in their browser)."""
from datetime import datetime, timezone
from flask import Blueprint, Response, abort, request
from core.extensions import db

PLACEMENTS = {'home': 'Home page only', 'all': 'Every page'}


class Popup(db.Model):
    __tablename__ = 'core_popup'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(80), nullable=False)
    body = db.Column(db.String(600), nullable=False, default='')
    image = db.Column(db.LargeBinary)                       # WEBP, optional
    version = db.Column(db.Integer, nullable=False, default=1)  # bumps on every edit, so "hide today" resets
    button_label = db.Column(db.String(30), nullable=False, default='')
    button_link = db.Column(db.String(200), nullable=False, default='')
    placement = db.Column(db.String(10), nullable=False, default='home')
    starts_on = db.Column(db.Date)
    ends_on = db.Column(db.Date)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    @property
    def image_url(self):
        return f'/media/popups/{self.id}.webp?v={self.version}' if self.image else ''

    def is_live(self, today=None):
        today = today or datetime.now(timezone.utc).date()
        return self.is_active and (self.starts_on is None or self.starts_on <= today) and (self.ends_on is None or self.ends_on >= today)


def safe_link(value):
    """Same-site path (/products/...) or an https:// address. Anything else is dropped."""
    value = (value or '').strip()
    if value.startswith('/') and not value.startswith('//') and '\\' not in value: return value[:200]
    if value.startswith('https://') and ' ' not in value: return value[:200]
    return ''


def site_popup():
    """The popup for this page, or None. Never on admin, login or checkout pages."""
    path = request.path
    if path.startswith(('/admin', '/auth', '/shop/checkout', '/media', '/static')): return None
    try:
        rows = db.session.scalars(db.select(Popup).filter_by(is_active=True).order_by(Popup.id.desc())).all()
    except Exception:
        return None
    for p in rows:
        if p.is_live() and (p.placement == 'all' or path == '/'): return p
    return None


bp = Blueprint('popups', __name__)


@bp.record_once
def register(state):
    state.app.jinja_env.globals['site_popup'] = site_popup


@bp.get('/media/popups/<int:popup_id>.webp')
def image(popup_id):
    p = db.session.get(Popup, popup_id)
    if not p or not p.image: abort(404)
    resp = Response(p.image, mimetype='image/webp'); resp.direct_passthrough = True
    resp.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    return resp
