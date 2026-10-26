from flask import Blueprint, redirect, current_app, abort, request, render_template
from core.extensions import db
from shop.models import ReferralLink
bp=Blueprint('referral',__name__)


def remember(response, link):
    response.set_cookie('ref_code',link.code,max_age=30*86400,httponly=True,samesite='Lax',secure=current_app.config['SESSION_COOKIE_SECURE'])
    return response


@bp.get('/r/<code>')
def track(code):
    """Creator's dedicated link. Counts a visit, stores the discount code for 30 days, then opens the creator's deal page —
    every product with the creator's discount already taken off (README §35). A link set to one product opens that product page
    (also at the discounted price). Orders placed with the code are credited to the creator in the sales reports."""
    link=db.session.scalar(db.select(ReferralLink).filter_by(code=code.upper(),is_active=True))
    if not link: abort(404)
    db.session.execute(db.update(ReferralLink).where(ReferralLink.id==link.id).values(clicks=ReferralLink.clicks+1))
    db.session.commit()
    from auth import safe_next
    target=safe_next(request.args.get('to')) or (safe_next(link.landing) if link.landing not in ('', '/') else '') or f'/deal/{link.code}'
    return remember(redirect(target), link)


@bp.get('/deal/<code>')
def deal(code):
    """Creator deal page: all products at the creator's price, ready to add to the bag."""
    from products.services import get_all_products
    from rewards.services import record
    link=db.session.scalar(db.select(ReferralLink).filter_by(code=code.upper(),is_active=True))
    if not link: abort(404)
    from flask import g
    g.creator_link=link  # show this code's prices even on the first visit (cookie is set with this response)
    record('creator_deal_viewed',{'code':link.code}); db.session.commit()
    resp=current_app.make_response(render_template('shop/deal.html',title=f'{link.code} · Creator deal',link=link,products=get_all_products()))
    return remember(resp, link)


@bp.get('/deal/exit')
def deal_exit():
    """Leave the creator deal: the code is removed and the visitor goes to the regular site (regular prices)."""
    response=redirect('/')
    response.delete_cookie('ref_code')
    return response
