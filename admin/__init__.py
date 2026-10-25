import csv
import io
import os
import re
from decimal import Decimal
from flask import Blueprint, render_template, Response, abort, request, redirect, flash
from auth.decorators import admin_required
from admin.services import report, influencer_rows, PLATFORMS
from core.extensions import db
from datetime import date
from shop.models import ReferralLink, Product, ProductOption, ProductDiscount
from shop.services import sale_price, live_discounts
from rewards.models import Activity, PointEntry
from core.messages import Message
bp=Blueprint('admin',__name__,url_prefix='/admin')
FIELDS={
'product-sales':'product_slug product_name order_count units_sold box_units_sold gross_sales_usd discount_usd net_sales_usd via_link_sales_usd'.split(),
'link-sales':'link_code influencer_name platform clicks order_count conversion_rate units_sold net_sales_usd commission_usd top_product'.split(),
'orders':'order_id ordered_at status product_slug product_name option_sku option_label quantity unit_price_usd discount_usd line_total_usd link_code influencer_name ship_state is_dummy points_used'.split(),
'option-sales':'product_slug product_name product_line option_sku option_label pack_size list_price_usd order_count quantity_sold pieces_sold gross_sales_usd discount_usd net_sales_usd direct_sales_usd instagram_sales_usd tiktok_sales_usd'.split(),
'influencer-sales':'platform influencer_name discount_code link_path discount_rate commission_rate clicks order_count conversion_rate units_sold gross_sales_usd discount_usd net_sales_usd commission_usd top_product'.split(),
'influencer-orders':'order_id ordered_at status platform influencer_name discount_code link_path discount_rate product_slug product_name option_sku option_label quantity unit_price_usd gross_usd discount_usd line_total_usd commission_rate commission_usd ship_state is_dummy'.split()}
FIELDS.update({
'creator-performance':'creator discount_code platform link_url clicks order_count units_sold net_sales_usd conversion_rate_pct commission_usd'.split(),
'direct-orders':'order_id ordered_at status product_slug product_name option_sku option_label quantity unit_price_usd gross_usd discount_usd line_total_usd ship_state is_dummy'.split(),
'reviews':'review_id created_at product_slug product_name rating sentiment title body reviewer_name status is_dummy'.split(),
'review-summary':'month product_slug product_name review_count positive neutral negative positive_pct negative_pct average_rating'.split()})
SENTIMENTS=('all','positive','negative','neutral')
SOURCES={'creator-performance':'creators','direct-orders':'direct_details','product-sales':'products','link-sales':'links','orders':'details','option-sales':'options','influencer-sales':'links','influencer-orders':'influencer_details'}
INFLUENCER_KINDS=('influencer-sales','influencer-orders','creator-performance')

def safe_cell(value):
    value=f'{value:.2f}' if isinstance(value,Decimal) else str(value if value is not None else '')
    return "'"+value if value.lstrip().startswith(('=','+','-','@')) or value.startswith(('\t','\r','\n')) else value

@bp.get('/')
@admin_required
def dashboard():
    return render_template('admin/dashboard.html',title='Sales overview',data=report(),site_url=site_url(),activities=db.session.scalars(db.select(Activity).order_by(Activity.id.desc()).limit(100)).all(),point_entries=db.session.scalars(db.select(PointEntry).order_by(PointEntry.id.desc()).limit(100)).all(),messages=db.session.scalars(db.select(Message).order_by(Message.id.desc()).limit(50)).all())

@bp.get('/export/<kind>.csv')
@admin_required
def export(kind):
    if kind not in FIELDS: abort(404)
    platform=request.args.get('platform','all')
    if kind in INFLUENCER_KINDS and platform not in ('all',*PLATFORMS): abort(400,description='Choose instagram, tiktok, or all.')
    sentiment=request.args.get('sentiment','all')
    if kind=='reviews' and sentiment not in SENTIMENTS: abort(400,description='Choose positive, negative, neutral, or all.')
    data=report()
    if kind=='reviews': rows=[r for r in data['reviews']['items'] if sentiment=='all' or r['sentiment']==sentiment]
    elif kind=='review-summary': rows=data['reviews']['by_month']
    else: rows=data[SOURCES[kind]]
    if kind in INFLUENCER_KINDS: rows=influencer_rows(rows,platform)
    if kind=='creator-performance': rows=[dict(r,link_url=site_url()+r['link_path']) for r in rows]
    stream=io.StringIO(newline=''); writer=csv.DictWriter(stream,fieldnames=FIELDS[kind]); writer.writeheader()
    for row in rows: writer.writerow({key:safe_cell(row[key]) for key in FIELDS[kind]})
    suffix=f'_{platform}' if kind in INFLUENCER_KINDS else f'_{sentiment}' if kind=='reviews' else ''
    filename=f"reboot_{kind.replace('-','_')}{suffix}_{data['start'].replace('-','')}_{data['end'].replace('-','')}.csv"
    return Response(stream.getvalue().encode('utf-8-sig'),mimetype='text/csv',headers={'Content-Disposition':f'attachment; filename="{filename}"','Cache-Control':'no-store'})


def site_url():
    """Public base URL used in creator share links (SITE_URL in .env, else the current host)."""
    return (os.getenv('SITE_URL') or request.url_root).rstrip('/')


@bp.post('/creators')
@admin_required
def add_creator():
    """Issue a creator's dedicated link: /r/<CODE>. The code is also the discount code applied at checkout."""
    name=request.form.get('name','').strip(); platform=request.form.get('platform','')
    code=re.sub(r'[^A-Z0-9]','',request.form.get('code','').upper())
    try: discount=int(request.form.get('discount','')); commission=int(request.form.get('commission',''))
    except ValueError: discount=commission=-1
    if not name or len(name)>80 or platform not in PLATFORMS.values() or not 0<=discount<=50 or not 0<=commission<=50:
        flash('Enter a creator name, Instagram or TikTok, and discount/commission between 0 and 50%.','error'); return redirect('/admin/manage#creators')
    landing=request.form.get('landing','')
    if landing not in landing_pages(): landing=''
    code=code or (re.sub(r'[^A-Z0-9]','',name.upper())[:10]+str(discount))
    if not 3<=len(code)<=40 or db.session.scalar(db.select(ReferralLink).filter_by(code=code)):
        flash('That discount code is already used. Enter a different code.','error'); return redirect('/admin/manage#creators')
    db.session.add(ReferralLink(code=code,influencer_name=name,platform=platform,discount_rate=Decimal(discount)/100,commission_rate=Decimal(commission)/100,clicks=0,is_active=True,landing=landing))
    db.session.commit()
    flash(f'Creator link created: /r/{code}')
    return redirect('/admin/manage#creators')


@bp.post('/creators/<int:link_id>/toggle')
@admin_required
def toggle_creator(link_id):
    link=db.session.get(ReferralLink,link_id) or abort(404)
    link.is_active=not link.is_active; db.session.commit()
    return redirect('/admin/manage#creators')


# ---------- Homepage manager: product sales + creator codes/links ----------

def landing_pages():
    """Pages a creator link may open: home or a product page."""
    pages={'':'Home'}
    for p in db.session.scalars(db.select(Product).filter_by(is_active=True).order_by(Product.id)):
        pages[f'/products/{p.slug}']=p.name
    return pages


@bp.get('/manage')
@admin_required
def manage():
    products=db.session.scalars(db.select(Product).filter_by(is_active=True).order_by(Product.id)).all()
    options=[(p,o,*sale_price(o)) for p in products for o in sorted(p.options,key=lambda o:o.id) if o.is_active]
    live={r.id for r in live_discounts()}
    discounts=db.session.scalars(db.select(ProductDiscount).order_by(ProductDiscount.id.desc())).all()
    links=db.session.scalars(db.select(ReferralLink).order_by(ReferralLink.id.desc())).all()
    return render_template('admin/manage.html',title='Homepage manager',products=products,options=options,discounts=discounts,live=live,
                           links=links,pages=landing_pages(),site_url=site_url(),today=date.today().isoformat(),
                           popups=db.session.scalars(db.select(Popup).order_by(Popup.id.desc())).all(),placements=PLACEMENTS)


def parse_day(value):
    try: return date.fromisoformat(value) if value else None
    except ValueError: raise ValueError('bad date')


@bp.post('/discounts')
@admin_required
def add_discount():
    """target = 'p:<product id>' (every option) or 'o:<option id>'; kind percent/amount."""
    back=redirect('/admin/manage#discounts')
    target=request.form.get('target',''); kind=request.form.get('kind'); label=request.form.get('label','').strip()[:60]
    try:
        value=Decimal(request.form.get('value','')).quantize(Decimal('.01'))
        starts,ends=parse_day(request.form.get('starts_on')),parse_day(request.form.get('ends_on'))
    except Exception:
        flash('Enter a valid discount and dates.','error'); return back
    product=option=None
    if target.startswith('p:') and target[2:].isdigit(): product=db.session.get(Product,int(target[2:]))
    elif target.startswith('o:') and target[2:].isdigit():
        option=db.session.get(ProductOption,int(target[2:])); product=option.product if option else None
    if not product or kind not in ('percent','amount'):
        flash('Choose a product or option and a discount type.','error'); return back
    prices=[option.price] if option else [o.price for o in product.options if o.is_active]
    if kind=='percent' and not Decimal(1)<=value<=Decimal(90):
        flash('Percent discounts must be between 1 and 90%.','error'); return back
    if kind=='amount' and not (Decimal('0.01')<=value<min(prices)):
        flash(f'Dollar discounts must be at least $0.01 and less than the lowest price (${min(prices):.2f}).','error'); return back
    if starts and ends and ends<starts:
        flash('The end date must be on or after the start date.','error'); return back
    db.session.add(ProductDiscount(product_id=product.id,option_id=option.id if option else None,kind=kind,value=value,label=label,starts_on=starts,ends_on=ends,is_active=True))
    from rewards.services import record
    record('discount_created',{'product':product.slug,'option':option.sku if option else 'all','kind':kind,'value':str(value)})
    db.session.commit()
    flash('Discount saved. It shows on the product pages and is applied in the bag.')
    return back


@bp.post('/discounts/<int:discount_id>/toggle')
@admin_required
def toggle_discount(discount_id):
    d=db.session.get(ProductDiscount,discount_id) or abort(404)
    d.is_active=not d.is_active; db.session.commit()
    return redirect('/admin/manage#discounts')


@bp.post('/discounts/<int:discount_id>/delete')
@admin_required
def delete_discount(discount_id):
    d=db.session.get(ProductDiscount,discount_id) or abort(404)
    db.session.delete(d); db.session.commit()
    flash('Discount deleted.')
    return redirect('/admin/manage#discounts')


@bp.post('/creators/<int:link_id>/edit')
@admin_required
def edit_creator(link_id):
    link=db.session.get(ReferralLink,link_id) or abort(404)
    try: discount=int(request.form.get('discount','')); commission=int(request.form.get('commission',''))
    except ValueError: discount=commission=-1
    landing=request.form.get('landing','')
    if not 0<=discount<=50 or not 0<=commission<=50 or landing not in landing_pages():
        flash('Discount and commission must be between 0 and 50%.','error'); return redirect('/admin/manage#creators')
    link.discount_rate=Decimal(discount)/100; link.commission_rate=Decimal(commission)/100; link.landing=landing
    db.session.commit()
    flash(f'Updated {link.code}.')
    return redirect('/admin/manage#creators')


# ---------- Customer care: inbox (contact inquiries + creator applications) ----------
from core.messages import Message as InboxMessage
from datetime import datetime, timezone


@bp.record_once
def register_counts(state):
    def admin_inbox_count():
        try: return db.session.scalar(db.select(db.func.count(InboxMessage.id)).filter_by(status='new')) or 0
        except Exception: return 0
    state.app.jinja_env.globals['admin_inbox_count']=admin_inbox_count


@bp.get('/inbox')
@admin_required
def inbox():
    view=request.args.get('view','open')
    q=db.select(InboxMessage).order_by(InboxMessage.id.desc())
    if view=='open': q=q.filter(InboxMessage.status!='answered')
    elif view=='answered': q=q.filter_by(status='answered')
    elif view!='all': abort(400)
    items=db.session.scalars(q.limit(200)).all()
    return render_template('admin/inbox.html',title='Inbox',items=items,view=view)


@bp.post('/inbox/<int:message_id>')
@admin_required
def answer(message_id):
    m=db.session.get(InboxMessage,message_id) or abort(404)
    action=request.form.get('action')
    if action=='read': m.status='read' if m.status=='new' else m.status
    elif action=='reopen': m.status='read'
    elif action=='reply':
        text=request.form.get('reply','').strip()
        if not 1<=len(text)<=4000:
            flash('Write a reply (up to 4,000 characters).','error'); return redirect(f'/admin/inbox#m{m.id}')
        m.reply=text; m.status='answered'; m.replied_at=datetime.now(timezone.utc)
        flash('Reply saved. The member sees it on their Contact page.' if m.kind=='contact' else 'Marked as answered. Reply to this creator by email.')
    else: abort(400)
    db.session.commit()
    return redirect(f"/admin/inbox?view={request.form.get('view','open')}#m{m.id}")


# ---------- Customer care: chatbot status ----------
@bp.get('/chatbot')
@admin_required
def chatbot():
    from support import system_prompt, chat_config
    return render_template('admin/chatbot.html',title='Chatbot',config=chat_config(),prompt=system_prompt(),result=None)


@bp.post('/chatbot/test')
@admin_required
def chatbot_test():
    """Send one short question to OpenAI with the live persona, so the admin sees exactly what fails."""
    from support import system_prompt, chat_config, ask_openai
    ok,detail=ask_openai([{'role':'user','content':'Hi! What flavors does Reboot Jelly Original come in?'}])
    return render_template('admin/chatbot.html',title='Chatbot',config=chat_config(),prompt=system_prompt(),result=dict(ok=ok,detail=detail))


# ---------- Inventory ----------
from shop.inventory import Inventory, StockMove, set_stock, export_csv, parse_csv


@bp.get('/inventory')
@admin_required
def inventory():
    rows=db.session.execute(db.select(ProductOption,Inventory).outerjoin(Inventory,Inventory.option_id==ProductOption.id)
                            .filter(ProductOption.is_active.is_(True)).order_by(ProductOption.product_id,ProductOption.id)).all()
    moves=db.session.scalars(db.select(StockMove).order_by(StockMove.id.desc()).limit(60)).all()
    stats=dict(skus=len(rows),units=sum(i.on_hand for _,i in rows if i),low=sum(1 for _,i in rows if i and 0<i.on_hand<=i.reorder_level),
               out=sum(1 for _,i in rows if not i or i.on_hand<=0))
    return render_template('admin/inventory.html',title='Inventory',rows=rows,moves=moves,stats=stats)


@bp.post('/inventory')
@admin_required
def inventory_save():
    """Save the table: new on-hand counts and reorder levels (only changed rows are logged)."""
    note=request.form.get('note','').strip()[:200]
    changed=0
    for o in db.session.scalars(db.select(ProductOption).filter_by(is_active=True)):
        raw,lvl=request.form.get(f'on_hand_{o.id}'),request.form.get(f'reorder_{o.id}')
        if raw is None: continue
        try: qty,level=int(raw),int(lvl)
        except (TypeError,ValueError):
            flash(f'{o.sku}: enter whole numbers.','error'); return redirect('/admin/inventory')
        if not 0<=qty<=100000 or not 0<=level<=100000:
            flash(f'{o.sku}: numbers must be between 0 and 100,000.','error'); return redirect('/admin/inventory')
        inv=db.session.scalar(db.select(Inventory).filter_by(option_id=o.id))
        if inv is None or inv.on_hand!=qty or inv.reorder_level!=level:
            set_stock(o,on_hand=qty,reorder_level=level,reason='manual',note=note); changed+=1
    db.session.commit()
    flash(f'Inventory saved ({changed} option{"s" if changed!=1 else ""} changed).')
    return redirect('/admin/inventory')


@bp.get('/inventory.csv')
@admin_required
def inventory_csv():
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d')
    return Response(export_csv().encode('utf-8-sig'),mimetype='text/csv',headers={'Content-Disposition':f'attachment; filename="reboot_inventory_{stamp}.csv"','Cache-Control':'no-store'})


@bp.post('/inventory/upload')
@admin_required
def inventory_upload():
    """CSV upload. mode=set: on_hand becomes the new count. mode=add: on_hand is added (a delivery). All rows or nothing."""
    f=request.files.get('file'); mode=request.form.get('mode','set')
    if mode not in ('set','add') or not f or not f.filename.lower().endswith('.csv'):
        flash('Choose a .csv file.','error'); return redirect('/admin/inventory#upload')
    try: text=f.read(2*1024*1024).decode('utf-8-sig')
    except UnicodeDecodeError:
        flash('Save the file as CSV UTF-8 and try again.','error'); return redirect('/admin/inventory#upload')
    changes,errors=parse_csv(text,mode)
    if mode=='add' and not errors:
        cur={i.option_id:i.on_hand for i in db.session.scalars(db.select(Inventory))}
        errors=[f'{o.sku}: stock would go below 0' for o,q,_ in changes if cur.get(o.id,0)+q<0]
    if errors:
        flash('Nothing was changed. Fix these rows and upload again: '+' · '.join(errors[:8])+(' …' if len(errors)>8 else ''),'error')
        return redirect('/admin/inventory#upload')
    note=f'CSV {f.filename[:80]}'
    for o,q,level in changes:
        set_stock(o,on_hand=q if mode=='set' else None,add=q if mode=='add' else None,reorder_level=level,reason='csv_'+mode,note=note)
    db.session.commit()
    flash(f'CSV applied to {len(changes)} option{"s" if len(changes)!=1 else ""} ({"set counts" if mode=="set" else "added to stock"}).')
    return redirect('/admin/inventory')


# ---------- Products: photos ----------
from products.services import load_original, image_url
from products.media import ProductImage, ProductText, to_webp, image_slots, url_for_image, name_overrides


@bp.get('/products')
@admin_required
def product_photos():
    current={i.original:i for i in db.session.scalars(db.select(ProductImage))}
    names=name_overrides()
    rows={r.slug:r for r in db.session.scalars(db.select(Product))}
    catalog=[dict(p=p,row=rows.get(p['slug']),name=names.get(p['slug'],p['name']),renamed=p['slug'] in names,slots=[dict(s,url=url_for_image(current[s['src']]) if s['src'] in current else image_url(s['src']),
                                  original_url=image_url(s['src']),replaced=s['src'] in current) for s in image_slots(p)]) for p in load_original()]
    return render_template('admin/products.html',title='Products',catalog=catalog)


def _known_src(slug,src):
    p=next((p for p in load_original() if p['slug']==slug),None)
    return p and any(s['src']==src for s in image_slots(p))


@bp.post('/products/photo')
@admin_required
def product_photo_upload():
    slug=request.form.get('slug',''); src=request.form.get('src',''); f=request.files.get('photo')
    back=redirect(f'/admin/products#p-{slug}')
    if not _known_src(slug,src): abort(400)
    if not f or not f.filename:
        flash('Choose a photo to upload.','error'); return back
    try: data=to_webp(f.read())
    except Exception as e:
        flash(str(e) if isinstance(e,ValueError) else 'That file is not a readable image (JPG, PNG or WEBP).','error'); return back
    img=db.session.scalar(db.select(ProductImage).filter_by(original=src))
    if img: img.data=data; img.version+=1; img.updated_at=datetime.now(timezone.utc)
    else: db.session.add(ProductImage(slug=slug,original=src,data=data))
    from rewards.services import record
    record('product_photo_changed',{'product':slug,'image':src})
    db.session.commit()
    flash('Photo updated. It now shows everywhere this image is used.')
    return back


@bp.post('/products/photo/reset')
@admin_required
def product_photo_reset():
    slug=request.form.get('slug',''); src=request.form.get('src','')
    if not _known_src(slug,src): abort(400)
    img=db.session.scalar(db.select(ProductImage).filter_by(original=src))
    if img: db.session.delete(img); db.session.commit(); flash('Original photo restored.')
    return redirect(f'/admin/products#p-{slug}')



@bp.post('/products/name')
@admin_required
def product_name():
    """Rename a product on the whole site (pages, bag, orders, admin reports). Empty = back to the products.json name."""
    slug=request.form.get('slug',''); name='' if request.form.get('reset') else ' '.join(request.form.get('name','').split())
    original=next((p for p in load_original() if p['slug']==slug),None)
    if not original: abort(400)
    back=redirect(f'/admin/products#p-{slug}')
    if name and not 3<=len(name)<=80:
        flash('Product names need 3–80 characters.','error'); return back
    row=db.session.scalar(db.select(ProductText).filter_by(slug=slug))
    final=name or original['name']
    if final==original['name']:
        if row: db.session.delete(row)
    elif row: row.name=final; row.updated_at=datetime.now(timezone.utc)
    else: db.session.add(ProductText(slug=slug,name=final))
    product=db.session.scalar(db.select(Product).filter_by(slug=slug))
    if product: product.name=final
    from rewards.services import record
    record('product_renamed',{'product':slug,'name':final})
    db.session.commit()
    flash(f'Product name saved: {final}')
    return back


# ---------- Homepage manager: site popups ----------
from core.popups import Popup, PLACEMENTS, safe_link


@bp.post('/popups')
@bp.post('/popups/<int:popup_id>')
@admin_required
def save_popup(popup_id=None):
    """Create (no id) or update a popup. Image is optional; 'remove_image' drops it."""
    back=redirect('/admin/manage#popups')
    p=db.session.get(Popup,popup_id) if popup_id else Popup()
    if popup_id and not p: abort(404)
    title=request.form.get('title','').strip(); body=request.form.get('body','').strip()
    label=request.form.get('button_label','').strip(); raw_link=request.form.get('button_link','').strip(); link=safe_link(raw_link)
    placement=request.form.get('placement','home')
    try: starts,ends=parse_day(request.form.get('starts_on')),parse_day(request.form.get('ends_on'))
    except ValueError: flash('Enter valid dates.','error'); return back
    if not 1<=len(title)<=80 or len(body)>600 or len(label)>30 or placement not in PLACEMENTS:
        flash('Popups need a title (up to 80 characters); text up to 600; button label up to 30.','error'); return back
    if raw_link and not link:
        flash('Button links must be a page on this site (/products/...) or an https:// address.','error'); return back
    if bool(label)!=bool(link):
        flash('Fill in both the button label and the link, or leave both empty.','error'); return back
    if starts and ends and ends<starts:
        flash('The end date must be on or after the start date.','error'); return back
    f=request.files.get('image')
    if f and f.filename:
        try: p.image=to_webp(f.read())
        except Exception as e:
            flash(str(e) if isinstance(e,ValueError) else 'That file is not a readable image (JPG, PNG or WEBP).','error'); return back
    elif request.form.get('remove_image'): p.image=None
    p.title,p.body,p.button_label,p.button_link,p.placement,p.starts_on,p.ends_on=title,body,label,link,placement,starts,ends
    if popup_id: p.version=(p.version or 1)+1
    else: p.is_active=True; db.session.add(p)
    from rewards.services import record
    record('popup_saved',{'title':title})
    db.session.commit()
    flash('Popup saved. Visitors see it on their next page view.' if p.is_live() else 'Popup saved (not live right now — check the dates or Resume).')
    return back


@bp.post('/popups/<int:popup_id>/toggle')
@admin_required
def toggle_popup(popup_id):
    p=db.session.get(Popup,popup_id) or abort(404)
    p.is_active=not p.is_active; db.session.commit()
    return redirect('/admin/manage#popups')


@bp.post('/popups/<int:popup_id>/delete')
@admin_required
def delete_popup(popup_id):
    p=db.session.get(Popup,popup_id) or abort(404)
    db.session.delete(p); db.session.commit(); flash('Popup deleted.')
    return redirect('/admin/manage#popups')


# ---------- Products: register new (seasonal) products, hide / show, delete ----------
from products.custom import CustomProduct, INGREDIENTS, slugify
from products.services import get_all_products as _catalog
from shop.models import OrderItem


@bp.get('/products/new')
@admin_required
def product_new():
    return render_template('admin/product_new.html',title='Add product',form=request.args)


@bp.post('/products/new')
@admin_required
def product_create():
    f=request.form
    def fail(msg):
        flash(msg,'error'); return render_template('admin/product_new.html',title='Add product',form=f),400
    name=' '.join(f.get('name','').split()); line=f.get('line'); badge=' '.join(f.get('badge','').split())[:30]
    fmt=f.get('format','').strip()[:120]; pack=f.get('pack','').strip()[:120]; volume=f.get('volume','').strip()[:20]
    tagline=f.get('tagline','').strip()[:120]
    flavors=[x.strip().title() for x in f.get('flavors','').split(',') if x.strip()][:6]
    if not 3<=len(name)<=80: return fail('Enter a product name (3–80 characters).')
    if line not in ('Jelly','Drink'): return fail('Choose Jelly or Drink.')
    if not fmt or not pack: return fail('Describe the format and the pack.')
    if not flavors: return fail('Enter at least one flavor (comma separated).')
    options=[]
    for i in range(4):
        label=' '.join(f.get(f'opt_label_{i}','').split())[:60]; price=f.get(f'opt_price_{i}','').strip()
        if not label and not price: continue
        try:
            price=Decimal(price).quantize(Decimal('.01')); count=int(f.get(f'opt_count_{i}') or 1); stock=int(f.get(f'opt_stock_{i}') or 0)
        except Exception: return fail(f'Option {i+1}: check the price, pieces and stock.')
        if not label or not Decimal('0.50')<=price<=Decimal('999') or not 1<=count<=48 or not 0<=stock<=100000:
            return fail(f'Option {i+1}: label, price $0.50–$999, pieces 1–48, stock 0–100,000.')
        options.append((label,price,count,stock))
    if not options: return fail('Add at least one sales option with a price.')
    photo=request.files.get('photo')
    if not photo or not photo.filename: return fail('Add a product photo.')
    try: image=to_webp(photo.read())
    except Exception as e: return fail(str(e) if isinstance(e,ValueError) else 'That file is not a readable image.')
    taken={p['slug'] for p in load_original()}|set(db.session.scalars(db.select(Product.slug)))
    base=slugify(name); slug=base; n=2
    while slug in taken: slug=f'{base}-{n}'; n+=1
    key=f'custom/{slug}/main.webp'
    used_skus=set(db.session.scalars(db.select(ProductOption.sku)))
    opts=[]
    for label,price,count,stock in options:
        sku=f'{slug}-{slugify(label)}'[:90]; k=2
        while sku in used_skus: sku=f'{slug}-{slugify(label)}-{k}'[:90]; k+=1
        used_skus.add(sku); opts.append(dict(sku=sku,label=label,unit_count=count,price_usd=float(price),image=key,stock=stock))
    order=100+db.session.scalar(db.select(db.func.count(CustomProduct.id)))
    data=dict(slug=slug,name=name,line=line,format=fmt,pack=pack,ingredients=INGREDIENTS,flavors=flavors,
              options=[{k:v for k,v in o.items() if k!='stock'} for o in opts],images=dict(main=key,card=key,gallery=[]),
              is_balance=f.get('version')=='balance',badge=badge,tagline=tagline or 'TBD',buy_links={},order=order,
              image_dir='custom',variant=slug,color='#b1ff3b',price_is_sample=False,custom=True)
    if volume: data['volume']=volume
    db.session.add(CustomProduct(slug=slug,data=data))
    db.session.add(ProductImage(slug=slug,original=key,data=image))
    product=Product(slug=slug,name=name,is_active=not f.get('hidden')); db.session.add(product); db.session.flush()
    from shop.inventory import set_stock
    for o in opts:
        option=ProductOption(product_id=product.id,sku=o['sku'],label=o['label'],unit_count=o['unit_count'],price=Decimal(str(o['price_usd'])),is_active=True)
        db.session.add(option); db.session.flush()
        set_stock(option,on_hand=o['stock'],reorder_level=20,reason='manual',note='New product')
    from rewards.services import record
    record('product_created',{'product':slug})
    db.session.commit()
    flash(f'{name} was added' + (' as hidden. Press Show when it is ready.' if f.get('hidden') else ' and is live on the Products page.'))
    return redirect(f'/admin/products#p-{slug}')


@bp.post('/products/<slug>/status')
@admin_required
def product_status(slug):
    """hide / show / delete / restore. Delete removes a never-ordered new product completely;
    anything with orders (and every original product) is archived instead so reports stay correct."""
    action=request.form.get('action')
    product=db.session.scalar(db.select(Product).filter_by(slug=slug)) or abort(404)
    back=redirect('/admin/products#archived' if action=='delete' else f'/admin/products#p-{slug}')
    if action=='hide': product.is_active=False; msg='Hidden from the site.'
    elif action=='show': product.is_active=True; product.is_deleted=False; msg='Visible on the site again.'
    elif action=='restore':
        product.is_deleted=False; product.is_active=False
        for o in product.options: o.is_active=True
        msg='Restored as hidden. Press Show to put it back on the site.'
    elif action=='delete':
        custom=db.session.scalar(db.select(CustomProduct).filter_by(slug=slug))
        has_orders=db.session.scalar(db.select(db.func.count(OrderItem.id)).filter_by(product_id=product.id))
        if custom and not has_orders:
            from shop.inventory import Inventory, StockMove
            from rewards.models import CartItem
            from products.models import Review
            ids=[o.id for o in product.options]
            for model,col in ((CartItem,CartItem.option_id),(Inventory,Inventory.option_id),(StockMove,StockMove.option_id),(ProductDiscount,ProductDiscount.option_id)):
                db.session.execute(db.delete(model).where(col.in_(ids)))
            db.session.execute(db.delete(ProductDiscount).where(ProductDiscount.product_id==product.id))
            db.session.execute(db.delete(Review).where(Review.product_id==product.id))
            db.session.execute(db.delete(ProductImage).where(ProductImage.slug==slug))
            db.session.execute(db.delete(ProductText).where(ProductText.slug==slug))
            for o in product.options: db.session.delete(o)
            db.session.delete(custom); db.session.delete(product)
            msg='Product deleted.'; back=redirect('/admin/products')
        else:
            product.is_deleted=True; product.is_active=False
            for o in product.options: o.is_active=False
            msg='Product deleted from the site. It is kept in the archive because past orders use it.'
    else: abort(400)
    from rewards.services import record
    record('product_'+action,{'product':slug})
    db.session.commit()
    flash(msg)
    return back
