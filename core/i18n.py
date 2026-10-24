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
