import re
from flask import Blueprint, session, request, redirect, abort
from flask_login import current_user
from core.extensions import db
from core.translations import KO
from rewards.services import record

bp=Blueprint('language',__name__)

def language():
    return session.get('lang') or (current_user.language if current_user.is_authenticated else 'en')

def tr(text):
    value=str(text)
    return KO.get(value,value) if language()=='ko' else value

@bp.post('/language')
def change():
    locale=request.form.get('language')
    if locale not in ('en','ko'): abort(400)
    session['lang']=locale
    session['lang_picked']=True  # chosen with the switch this session (the admin AI assistant stays Korean otherwise — README §27)
    if current_user.is_authenticated:
        current_user.language=locale
        record('language_changed',{'language':locale})
        db.session.commit()
    from auth import safe_next
    return redirect(safe_next(request.form.get('next')) or '/')

def init_i18n(app):
    app.jinja_env.globals.update(tr=tr)
    app.jinja_env.filters['tr']=tr
    @app.context_processor
    def context():
        from rewards.models import CartItem
        count=0
        if current_user.is_authenticated and current_user.role=='customer':
            count=db.session.scalar(db.select(db.func.coalesce(db.func.sum(CartItem.quantity),0)).filter_by(user_id=current_user.id))
        return {'locale':language(),'cart_count':count}


# ── Rebu-face arrows ──────────────────────────────────────────────────────
# Every "↗" in page text is rendered as Rebu's face (core/static/core/img/rebu-face.png).
# Only text between tags is touched; attributes, <title>, <option>, <textarea>, <script>, <style> keep the glyph.
REBU_ARROW = ('<img class="rebu-arrow" src="/static/core/img/rebu-face.png" '
              'srcset="/static/core/img/rebu-face.png 1x, /static/core/img/rebu-face@2x.png 2x" '
              'alt="" aria-hidden="true" width="20" height="20" decoding="async">')
_TAG = re.compile(r'(<[^>]+>)')
_NAME = re.compile(r'<(/?)([a-zA-Z][a-zA-Z0-9]*)')
_SKIP = {'script', 'style', 'title', 'textarea', 'option'}


def rebu_arrows(html):
    if '↗' not in html:
        return html
    out, skip = [], None
    for part in _TAG.split(html):
        if part.startswith('<'):
            m = _NAME.match(part)
            if m:
                name = m.group(2).lower()
                if not m.group(1) and skip is None and name in _SKIP:
                    skip = name
                elif m.group(1) and name == skip:
                    skip = None
            out.append(part)
        else:
            out.append(part if skip else part.replace('↗', REBU_ARROW))
    return ''.join(out)


@bp.after_app_request
def rebu_arrow_filter(response):
    if response.mimetype == 'text/html' and not response.direct_passthrough and not response.is_streamed:
        html = response.get_data(as_text=True)
        if '↗' in html:
            response.set_data(rebu_arrows(html))
    return response
