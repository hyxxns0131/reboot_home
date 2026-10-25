from decimal import Decimal, ROUND_HALF_UP
from flask import request
from flask_login import current_user
from rewards.models import CartItem
from core.extensions import db
from datetime import datetime, timezone
from flask import g, has_request_context
from shop.models import ProductOption, ReferralLink, Order, OrderItem, ProductDiscount

def money(value):
    return Decimal(value).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)

def cart_lines():
    if not current_user.is_authenticated:
        return []
    rows=db.session.scalars(db.select(CartItem).filter_by(user_id=current_user.id).order_by(CartItem.id)).all()
    return [(row.option,row.quantity) for row in rows if row.option.is_active and row.option.product.is_active]

def referral():
    code=request.cookies.get('ref_code','')
    return db.session.scalar(db.select(ReferralLink).filter_by(code=code,is_active=True))

def live_discounts():
    """Active sales whose dates include today (UTC). Cached for the request."""
    if has_request_context() and 'live_discounts' in g: return g.live_discounts
    today=datetime.now(timezone.utc).date()
    rows=db.session.scalars(db.select(ProductDiscount).filter_by(is_active=True)).all()
    rows=[r for r in rows if (r.starts_on is None or r.starts_on<=today) and (r.ends_on is None or r.ends_on>=today)]
    if has_request_context(): g.live_discounts=rows
    return rows

def unit_off(option, rules=None):
    """Best sale discount (USD per unit) for an option and the rule that gives it."""
    best=(Decimal(0),None)
    for r in (live_discounts() if rules is None else rules):
        if r.product_id!=option.product_id or (r.option_id and r.option_id!=option.id): continue
        off=money(option.price*r.value/100) if r.kind=='percent' else money(r.value)
        off=min(off,option.price-Decimal('0.01'))
        if off>best[0]: best=(off,r)
    return best

def sale_price(option):
    off,rule=unit_off(option)
    return money(option.price-off),rule

def line_parts(option, qty, link=None):
    """(gross, sale discount, code discount, net) for one cart line. Code % applies to the sale price."""
    gross=money(option.price*qty); sale=money(unit_off(option)[0]*qty)
    code=money((gross-sale)*link.discount_rate) if link else Decimal(0)
    return gross,sale,code,gross-sale-code

def breakdown(lines, link=None):
    parts=[line_parts(o,q,link) for o,q in lines]
    subtotal=sum((p[0] for p in parts),Decimal(0)); sale=sum((p[1] for p in parts),Decimal(0)); code=sum((p[2] for p in parts),Decimal(0))
    return dict(subtotal=money(subtotal),sale=money(sale),code=money(code),total=money(subtotal-sale-code))

def totals(lines, link=None):
    b=breakdown(lines,link)
    return b['subtotal'],money(b['sale']+b['code']),b['total']

def create_order(lines, link=None, points_used=0, **kwargs):
    subtotal,discount,total=totals(lines,link)
    if type(points_used) is not int or points_used<0 or points_used>int(total*100):
        raise ValueError('Invalid points amount')
    order=Order(subtotal=subtotal,discount=discount+Decimal(points_used)/100,total=total-Decimal(points_used)/100,points_used=points_used,referral=link,**kwargs)
    remaining_points=points_used
    remaining_cents=int(total*100)
    for option,qty in lines:
        gross,sale,code,net=line_parts(option,qty,link)
        line_cents=int(net*100)
        allocated=(remaining_points*line_cents//remaining_cents) if remaining_cents else 0
        remaining_points-=allocated
        remaining_cents-=line_cents
        deduction=sale+code+Decimal(allocated)/100
        order.items.append(OrderItem(product_id=option.product_id,option_id=option.id,quantity=qty,unit_price=option.price,line_discount=deduction,line_total=money(gross-deduction),points_used=allocated))
    db.session.add(order)
    return order
