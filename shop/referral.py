from flask import Blueprint, redirect, current_app, abort, request, render_template
from core.extensions import db
from shop.models import ReferralLink
bp=Blueprint('referral',__name__)


class CreatorVisit(db.Model):
    """Visits to a creator link per day (README §39), so dashboards can chart them. ReferralLink.clicks stays the all-time total."""
    __tablename__ = 'shop_creator_visit'
    id = db.Column(db.Integer, primary_key=True)
    link_id = db.Column(db.Integer, db.ForeignKey('shop_referral_link.id'), nullable=False, index=True)
    day = db.Column(db.Date, nullable=False, index=True)
    visits = db.Column(db.Integer, nullable=False, default=0)
    is_dummy = db.Column(db.Boolean, nullable=False, default=False)
    __table_args__ = (db.UniqueConstraint('link_id', 'day', 'is_dummy', name='uq_creator_visit_day'),)


def count_visit(link):
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).date()
    row = db.session.scalar(db.select(CreatorVisit).filter_by(link_id=link.id, day=today, is_dummy=False))
    if row: row.visits += 1
    else: db.session.add(CreatorVisit(link_id=link.id, day=today, visits=1))


def seed_dummy_visits():
    """Spread each sample creator's all-time clicks over the days of its sample orders (busier order days get more visits),
    once per link. Deterministic, marked is_dummy."""
    from collections import Counter
    from datetime import timedelta
    from shop.models import Order
    real = dict(db.session.execute(db.select(CreatorVisit.link_id, db.func.sum(CreatorVisit.visits)).where(CreatorVisit.is_dummy.is_(False)).group_by(CreatorVisit.link_id)).all())
    done = set(db.session.scalars(db.select(CreatorVisit.link_id).where(CreatorVisit.is_dummy.is_(True)).distinct()))
    for link in db.session.scalars(db.select(ReferralLink)):
        if link.id in done: continue
        total = (link.clicks or 0) - (real.get(link.id) or 0)
        days = Counter(o.date() for o in db.session.scalars(db.select(Order.ordered_at).filter_by(referral_link_id=link.id, is_dummy=True)))
        if total <= 0 or not days: continue
        first, last = min(days), max(days)
        span = [first + timedelta(days=i) for i in range((last - first).days + 1)]
        weights = [1 + 3 * days.get(d, 0) for d in span]
        share = [total * w / sum(weights) for w in weights]
        counts = [int(x) for x in share]
        for i in sorted(range(len(span)), key=lambda i: share[i] - counts[i], reverse=True)[:total - sum(counts)]: counts[i] += 1
        for d, n in zip(span, counts):
            if n: db.session.add(CreatorVisit(link_id=link.id, day=d, visits=n, is_dummy=True))


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
    count_visit(link)
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


@bp.get('/deal/<code>/<slug>')
def deal_product(code, slug):
    """Product page inside a creator deal (README §40): the same detail page and long detail story, but every option shows the
    creator price and Add to bag charges it (the code is kept in the 30-day cookie, so checkout credits the creator)."""
    link=db.session.scalar(db.select(ReferralLink).filter_by(code=code.upper(),is_active=True))
    if not link: abort(404)
    from flask import g
    from products import detail
    from rewards.services import record
    g.creator_link=link
    html=detail(slug)  # 404s for unknown or hidden products, like the main site
    record('creator_deal_product_viewed',{'code':link.code,'product':slug}); db.session.commit()
    return remember(current_app.make_response(html), link)


@bp.get('/deal/exit')
def deal_exit():
    """Leave the creator deal: the code is removed and the visitor goes to the regular site (regular prices)."""
    response=redirect('/')
    response.delete_cookie('ref_code')
    return response
