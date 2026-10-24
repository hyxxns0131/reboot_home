from decimal import Decimal, ROUND_HALF_UP
from flask import request
from flask_login import current_user
from rewards.models import CartItem
from core.extensions import db
from shop.models import ProductOption, ReferralLink, Order, OrderItem

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

def totals(lines, link=None):
    subtotal=sum((o.price*q for o,q in lines),Decimal(0))
    discount=sum((money(o.price*q*link.discount_rate) for o,q in lines),Decimal(0)) if link else Decimal(0)
    return money(subtotal),money(discount),money(subtotal-discount)

def create_order(lines, link=None, points_used=0, **kwargs):
    subtotal,discount,total=totals(lines,link)
    if type(points_used) is not int or points_used<0 or points_used>int(total*100):
        raise ValueError('Invalid points amount')
    order=Order(subtotal=subtotal,discount=discount+Decimal(points_used)/100,total=total-Decimal(points_used)/100,points_used=points_used,referral=link,**kwargs)
    remaining_points=points_used
    remaining_cents=int(total*100)
    for option,qty in lines:
        referral_discount=money(option.price*qty*link.discount_rate) if link else Decimal(0)
        line_cents=int(money(option.price*qty-referral_discount)*100)
        allocated=(remaining_points*line_cents//remaining_cents) if remaining_cents else 0
        remaining_points-=allocated
        remaining_cents-=line_cents
        deduction=referral_discount+Decimal(allocated)/100
        order.items.append(OrderItem(product_id=option.product_id,option_id=option.id,quantity=qty,unit_price=option.price,line_discount=deduction,line_total=money(option.price*qty-deduction),points_used=allocated))
    db.session.add(order)
    return order
