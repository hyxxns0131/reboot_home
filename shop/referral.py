from flask import Blueprint, redirect, current_app, abort
from core.extensions import db
from shop.models import ReferralLink
bp=Blueprint('referral',__name__)
@bp.get('/r/<code>')
def track(code):
    link=db.session.scalar(db.select(ReferralLink).filter_by(code=code,is_active=True))
    if not link: abort(404)
    db.session.execute(db.update(ReferralLink).where(ReferralLink.id==link.id).values(clicks=ReferralLink.clicks+1))
    db.session.commit()
    response=redirect('/')
    response.set_cookie('ref_code',code,max_age=30*86400,httponly=True,samesite='Lax',secure=current_app.config['SESSION_COOKIE_SECURE'])
    return response
