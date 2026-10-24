from decimal import Decimal, ROUND_HALF_UP
from flask import session, request
from core.extensions import db
from shop.models import ProductOption, ReferralLink, Order, OrderItem

def money(value):
    return Decimal(value).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)

def cart_lines():
    result=[]
    for sku, qty in session.get('cart',{}).items():
        option=db.session.scalar(db.select(ProductOption).filter_by(sku=sku,is_active=True))
        if option and option.product.is_active and isinstance(qty,int) and 1<=qty<=10:
            result.append((option,qty))
    return result

def referral():
    code=request.cookies.get('ref_code','')
    return db.session.scalar(db.select(ReferralLink).filter_by(code=code,is_active=True))

def totals(lines, link=None):
    subtotal=sum((o.price*q for o,q in lines),Decimal(0))
    discount=sum((money(o.price*q*link.discount_rate) for o,q in lines),Decimal(0)) if link else Decimal(0)
    return money(subtotal),money(discount),money(subtotal-discount)

def create_order(lines, link=None, **kwargs):
    subtotal,discount,total=totals(lines,link)
    order=Order(subtotal=subtotal,discount=discount,total=total,referral=link,**kwargs)
    for option,qty in lines:
        deduction=money(option.price*qty*link.discount_rate) if link else Decimal(0)
        order.items.append(OrderItem(product_id=option.product_id,option_id=option.id,quantity=qty,unit_price=option.price,line_discount=deduction,line_total=money(option.price*qty-deduction)))
    db.session.add(order)
    return order
