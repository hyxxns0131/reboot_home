from flask import Blueprint, redirect, current_app, abort, request
from core.extensions import db
from shop.models import ReferralLink
bp=Blueprint('referral',__name__)


@bp.get('/r/<code>')
def track(code):
    """Creator's dedicated link. Counts a visit, stores the discount code for 30 days, then lands on the site.
    Optional ?to=/products/<slug> sends the visitor straight to a product page (same-site paths only)."""
    link=db.session.scalar(db.select(ReferralLink).filter_by(code=code.upper(),is_active=True))
    if not link: abort(404)
    db.session.execute(db.update(ReferralLink).where(ReferralLink.id==link.id).values(clicks=ReferralLink.clicks+1))
    db.session.commit()
    from auth import safe_next
    response=redirect(safe_next(request.args.get('to')) or safe_next(link.landing) or '/')
    response.set_cookie('ref_code',link.code,max_age=30*86400,httponly=True,samesite='Lax',secure=current_app.config['SESSION_COOKIE_SECURE'])
    return response
