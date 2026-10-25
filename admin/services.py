from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from flask import request, abort
from sqlalchemy.orm import selectinload
from core.extensions import db
from shop.models import Order, OrderItem, Product, ProductOption, ReferralLink
from products.models import Review
from shop.services import money

# Influencer platforms that get their own CSV exports. Keys are URL values, values are DB values.
PLATFORMS = {'instagram': 'Instagram', 'tiktok': 'TikTok'}


def platform_key(link):
    """'direct' for orders without an influencer link, otherwise the lowercase platform key."""
    return (link.platform or '').strip().lower() if link else 'direct'


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

    # Every sellable option gets a row, even with zero sales in the period.
    options={}
    catalog=db.session.execute(db.select(ProductOption,Product).join(Product,ProductOption.product_id==Product.id).order_by(Product.id,ProductOption.id)).all()
    for option,product in catalog:
        if option.is_active and product.is_active:
            options[option.sku]=dict(product_slug=product.slug,product_name=product.name,product_line='Jelly' if product.slug.startswith('jelly') else 'Drink',option_sku=option.sku,option_label=option.label,pack_size=option.unit_count,list_price_usd=option.price,order_count=0,quantity_sold=0,pieces_sold=0,gross_sales_usd=Decimal(0),discount_usd=Decimal(0),net_sales_usd=Decimal(0),direct_sales_usd=Decimal(0),instagram_sales_usd=Decimal(0),tiktok_sales_usd=Decimal(0),other_link_sales_usd=Decimal(0))
    option_orders=defaultdict(set)

    products={}; links={}; details=[]; influencer_details=[]; direct_details=[]; product_orders=defaultdict(set); top=defaultdict(lambda:defaultdict(int))
    platforms={key:dict(platform=name,link_count=0,order_count=0,units_sold=0,gross_sales_usd=Decimal(0),discount_usd=Decimal(0),net_sales_usd=Decimal(0),commission_usd=Decimal(0)) for key,name in PLATFORMS.items()}
    platform_links=defaultdict(set)
    for order in orders:
        link=order.referral; code=link.code if link else 'DIRECT'; pkey=platform_key(link)
        if code not in links:
            links[code]=dict(link_code=code,discount_code=link.code if link else '',link_path=f'/r/{link.code}' if link else '',influencer_name=link.influencer_name if link else '',platform=link.platform if link else '',platform_key=pkey,discount_rate=f'{link.discount_rate:.4f}' if link else '',commission_rate=f'{link.commission_rate:.4f}' if link else '',clicks=link.clicks if link else 0,order_count=0,conversion_rate='',units_sold=0,gross_sales_usd=Decimal(0),discount_usd=Decimal(0),net_sales_usd=Decimal(0),commission_usd=Decimal(0),top_product='')
        lr=links[code]; lr['order_count']+=1; lr['net_sales_usd']+=order.total
        lr['gross_sales_usd']+=order.subtotal; lr['discount_usd']+=order.discount
        order_commission=money(order.total*link.commission_rate) if link else Decimal(0)
        lr['commission_usd']+=order_commission
        pr=platforms.get(pkey)
        if pr:
            platform_links[pkey].add(code)
            pr['order_count']+=1; pr['gross_sales_usd']+=order.subtotal; pr['discount_usd']+=order.discount; pr['net_sales_usd']+=order.total; pr['commission_usd']+=order_commission
        for item in order.items:
            slug=item.product.slug
            if slug not in products:
                products[slug]=dict(product_slug=slug,product_name=item.product.name,order_count=0,units_sold=0,box_units_sold=0,gross_sales_usd=Decimal(0),discount_usd=Decimal(0),net_sales_usd=Decimal(0),via_link_sales_usd=Decimal(0))
            gross=item.unit_price*item.quantity
            p=products[slug]; product_orders[slug].add(order.id)
            p['units_sold']+=item.quantity
            p['box_units_sold']+=item.quantity if item.option.unit_count==3 else 0
            p['gross_sales_usd']+=gross
            p['discount_usd']+=item.line_discount; p['net_sales_usd']+=item.line_total
            p['via_link_sales_usd']+=item.line_total if link else Decimal(0)
            lr['units_sold']+=item.quantity; top[code][slug]+=item.quantity
            if pr: pr['units_sold']+=item.quantity
            o=options.get(item.option.sku)
            if o is None:  # option retired after the order was placed: keep its history visible
                o=options[item.option.sku]=dict(product_slug=slug,product_name=item.product.name,product_line='Jelly' if slug.startswith('jelly') else 'Drink',option_sku=item.option.sku,option_label=item.option.label,pack_size=item.option.unit_count,list_price_usd=item.option.price,order_count=0,quantity_sold=0,pieces_sold=0,gross_sales_usd=Decimal(0),discount_usd=Decimal(0),net_sales_usd=Decimal(0),direct_sales_usd=Decimal(0),instagram_sales_usd=Decimal(0),tiktok_sales_usd=Decimal(0),other_link_sales_usd=Decimal(0))
            option_orders[item.option.sku].add(order.id)
            o['quantity_sold']+=item.quantity; o['pieces_sold']+=item.quantity*item.option.unit_count
            o['gross_sales_usd']+=gross; o['discount_usd']+=item.line_discount; o['net_sales_usd']+=item.line_total
            o[{'direct':'direct_sales_usd','instagram':'instagram_sales_usd','tiktok':'tiktok_sales_usd'}.get(pkey,'other_link_sales_usd')]+=item.line_total
            details.append(dict(order_id=order.id,ordered_at=order.ordered_at.isoformat(),status=order.status,product_slug=slug,product_name=item.product.name,option_sku=item.option.sku,option_label=item.option.label,quantity=item.quantity,unit_price_usd=item.unit_price,discount_usd=item.line_discount,line_total_usd=item.line_total,link_code=code,influencer_name=link.influencer_name if link else '',ship_state=order.ship_state,is_dummy=order.is_dummy,points_used=item.points_used))
            if not link:
                direct_details.append(dict(order_id=order.id,ordered_at=order.ordered_at.isoformat(),status=order.status,product_slug=slug,product_name=item.product.name,option_sku=item.option.sku,option_label=item.option.label,quantity=item.quantity,unit_price_usd=item.unit_price,gross_usd=gross,discount_usd=item.line_discount,line_total_usd=item.line_total,ship_state=order.ship_state,is_dummy=order.is_dummy))
            if link:
                influencer_details.append(dict(order_id=order.id,ordered_at=order.ordered_at.isoformat(),status=order.status,platform=link.platform,platform_key=pkey,influencer_name=link.influencer_name,discount_code=link.code,link_path=f'/r/{link.code}',discount_rate=f'{link.discount_rate:.4f}',product_slug=slug,product_name=item.product.name,option_sku=item.option.sku,option_label=item.option.label,quantity=item.quantity,unit_price_usd=item.unit_price,gross_usd=gross,discount_usd=item.line_discount,line_total_usd=item.line_total,commission_rate=f'{link.commission_rate:.4f}',commission_usd=money(item.line_total*link.commission_rate),ship_state=order.ship_state,is_dummy=order.is_dummy))
    for slug,p in products.items(): p['order_count']=len(product_orders[slug])
    for sku,o in options.items(): o['order_count']=len(option_orders[sku])
    for code,lr in links.items():
        lr['conversion_rate']=f"{Decimal(lr['order_count'])/lr['clicks']:.4f}" if lr['clicks'] else ''
        lr['top_product']=max(top[code],key=top[code].get) if top[code] else ''
    for key,pr in platforms.items(): pr['link_count']=len(platform_links[key])
    # Creator performance (screenshot layout): every active creator link, even with no orders in the period.
    creators=[]
    for link in db.session.scalars(db.select(ReferralLink).order_by(ReferralLink.id)).all():
        lr=links.get(link.code)
        orders_n=lr['order_count'] if lr else 0
        creators.append(dict(id=link.id,creator=link.influencer_name,discount_code=link.code,platform=link.platform,platform_key=platform_key(link),link_path=f'/r/{link.code}',discount_rate=link.discount_rate,commission_rate=link.commission_rate,is_active=link.is_active,clicks=link.clicks or 0,order_count=orders_n,units_sold=lr['units_sold'] if lr else 0,net_sales_usd=lr['net_sales_usd'] if lr else Decimal(0),commission_usd=lr['commission_usd'] if lr else Decimal(0),conversion_rate_pct=f"{Decimal(orders_n)*100/link.clicks:.2f}" if link.clicks else '0.00'))
    creators.sort(key=lambda c:c['net_sales_usd'],reverse=True)
    direct=links.get('DIRECT') or dict(order_count=0,units_sold=0,gross_sales_usd=Decimal(0),discount_usd=Decimal(0),net_sales_usd=Decimal(0))
    net=sum((o.total for o in orders),Decimal(0))
    via=sum((o.total for o in orders if o.referral_link_id),Decimal(0))
    return dict(start=start,end=end,status=status,orders=orders,products=sorted(products.values(),key=lambda p:p['net_sales_usd'],reverse=True),options=list(options.values()),links=sorted(links.values(),key=lambda p:p['net_sales_usd'],reverse=True),platforms=list(platforms.values()),details=details,influencer_details=influencer_details,direct_details=direct_details,creators=creators,direct=direct,reviews=review_report(begin,finish),net=net,units=sum(p['units_sold'] for p in products.values()),share=money(via/net*100) if net else 0)


def influencer_rows(rows, platform):
    """Keep only rows from influencer links on one platform ('all' = every influencer link)."""
    if platform=='all': return [r for r in rows if r.get('platform_key','direct')!='direct']
    return [r for r in rows if r.get('platform_key')==platform]


def review_report(begin, finish):
    """Reviews written in [begin, finish), any status. Sentiment comes from the star rating."""
    rows=db.session.scalars(db.select(Review).where(Review.created_at>=begin,Review.created_at<finish).options(selectinload(Review.product)).order_by(Review.created_at.desc(),Review.id.desc())).all()
    items=[dict(review_id=r.id,created_at=r.created_at.isoformat(timespec='seconds'),month=r.created_at.strftime('%Y-%m'),product_slug=r.product.slug,product_name=r.product.name,rating=r.rating,sentiment=r.sentiment,title=r.title,body=r.body,reviewer_name=r.reviewer_name,status=r.status,is_dummy=r.is_dummy) for r in rows]
    by_product={}; by_month={}
    for r in items:
        for key,bucket in ((r['product_slug'],by_product),((r['month'],r['product_slug']),by_month)):
            if key not in bucket: bucket[key]=dict(month=r['month'],product_slug=r['product_slug'],product_name=r['product_name'],review_count=0,positive=0,neutral=0,negative=0,rating_sum=0)
            b=bucket[key]; b['review_count']+=1; b[r['sentiment']]+=1; b['rating_sum']+=r['rating']
    for bucket in (by_product,by_month):
        for b in bucket.values():
            b['average_rating']=f"{b['rating_sum']/b['review_count']:.2f}"; b['positive_pct']=f"{b['positive']*100/b['review_count']:.1f}"; b['negative_pct']=f"{b['negative']*100/b['review_count']:.1f}"
    totals=dict(count=len(items),positive=sum(r['sentiment']=='positive' for r in items),neutral=sum(r['sentiment']=='neutral' for r in items),negative=sum(r['sentiment']=='negative' for r in items),held=sum(r['status']=='held' for r in items))
    totals['average']=f"{sum(r['rating'] for r in items)/len(items):.2f}" if items else '—'
    return dict(items=items,by_product=sorted(by_product.values(),key=lambda b:b['product_slug']),by_month=sorted(by_month.values(),key=lambda b:(b['month'],b['product_slug'])),totals=totals)
