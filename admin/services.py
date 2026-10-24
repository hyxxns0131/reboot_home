from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from flask import request, abort
from sqlalchemy.orm import selectinload
from core.extensions import db
from shop.models import Order, OrderItem, ReferralLink
from shop.services import money

def report():
    today=datetime.now(timezone.utc).date()
    start=request.args.get('start') or (today-timedelta(days=89)).isoformat()
    end=request.args.get('end') or today.isoformat()
    status=request.args.get('status','paid')
    try:
        begin=datetime.strptime(start,'%Y-%m-%d'); finish=datetime.strptime(end,'%Y-%m-%d')+timedelta(days=1)
        if begin>=finish or status not in ('all','paid','refunded','cancelled'): raise ValueError()
    except ValueError: abort(400,description='Choose a valid date range and order status.')
    query=db.select(Order).where(Order.ordered_at>=begin,Order.ordered_at<finish).options(selectinload(Order.items).joinedload(OrderItem.product),selectinload(Order.items).joinedload(OrderItem.option),selectinload(Order.referral)).order_by(Order.ordered_at.desc())
    if status!='all': query=query.where(Order.status==status)
    orders=db.session.scalars(query).all()
    products={}; links={}; details=[]; product_orders=defaultdict(set); top=defaultdict(lambda:defaultdict(int))
    for order in orders:
        link=order.referral; code=link.code if link else 'DIRECT'
        if code not in links:
            links[code]=dict(link_code=code,influencer_name=link.influencer_name if link else '',platform=link.platform if link else '',clicks=link.clicks if link else 0,order_count=0,conversion_rate='',units_sold=0,net_sales_usd=Decimal(0),commission_usd=Decimal(0),top_product='')
        lr=links[code]; lr['order_count']+=1; lr['net_sales_usd']+=order.total
        lr['commission_usd']+=money(order.total*link.commission_rate) if link else Decimal(0)
        for item in order.items:
            slug=item.product.slug
            if slug not in products:
                products[slug]=dict(product_slug=slug,product_name=item.product.name,order_count=0,units_sold=0,box_units_sold=0,gross_sales_usd=Decimal(0),discount_usd=Decimal(0),net_sales_usd=Decimal(0),via_link_sales_usd=Decimal(0))
            p=products[slug]; product_orders[slug].add(order.id)
            p['units_sold']+=item.quantity
            p['box_units_sold']+=item.quantity if item.option.unit_count==3 else 0
            p['gross_sales_usd']+=item.unit_price*item.quantity
            p['discount_usd']+=item.line_discount; p['net_sales_usd']+=item.line_total
            p['via_link_sales_usd']+=item.line_total if link else Decimal(0)
            lr['units_sold']+=item.quantity; top[code][slug]+=item.quantity
            details.append(dict(order_id=order.id,ordered_at=order.ordered_at.isoformat(),status=order.status,product_slug=slug,product_name=item.product.name,option_sku=item.option.sku,option_label=item.option.label,quantity=item.quantity,unit_price_usd=item.unit_price,discount_usd=item.line_discount,line_total_usd=item.line_total,link_code=code,influencer_name=link.influencer_name if link else '',ship_state=order.ship_state,is_dummy=order.is_dummy))
    for slug,p in products.items(): p['order_count']=len(product_orders[slug])
    for code,lr in links.items():
        lr['conversion_rate']=f"{Decimal(lr['order_count'])/lr['clicks']:.4f}" if lr['clicks'] else ''
        lr['top_product']=max(top[code],key=top[code].get) if top[code] else ''
    net=sum((o.total for o in orders),Decimal(0))
    via=sum((o.total for o in orders if o.referral_link_id),Decimal(0))
    return dict(start=start,end=end,status=status,orders=orders,products=sorted(products.values(),key=lambda p:p['net_sales_usd'],reverse=True),links=sorted(links.values(),key=lambda p:p['net_sales_usd'],reverse=True),details=details,net=net,units=sum(p['units_sold'] for p in products.values()),share=money(via/net*100) if net else 0)
