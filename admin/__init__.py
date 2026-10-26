import csv
import io
import os
import re
from decimal import Decimal
from flask import Blueprint, render_template, Response, abort, request, redirect, flash, jsonify
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

FIELDS.update({  # README §39
'chatbot-questions':'question_id created_at language visitor topic question reply verdict codes action is_dummy'.split(),
'creator-visits':'date discount_code creator platform visits is_dummy'.split(),
'inbox':'message_id created_at kind topic order_id status name email_masked body reply replied_at'.split()})


def mask_email(e):
    """j***@example.com — the inbox export never carries a full address."""
    user, _, domain = (e or '').partition('@')
    return (user[:1] + '***@' + domain) if domain else ''
EXTRA_KINDS=('inventory',)  # its own columns (shop/inventory.py CSV_FIELDS), no date range


def date_range():
    """start/end (YYYY-MM-DD, inclusive) from the query string; default the last 90 days like the dashboard."""
    from datetime import datetime as _dt, timedelta, timezone as _tz
    today=_dt.now(_tz.utc).date()
    start=request.args.get('start') or (today-timedelta(days=89)).isoformat(); end=request.args.get('end') or today.isoformat()
    try:
        a=_dt.strptime(start,'%Y-%m-%d'); b=_dt.strptime(end,'%Y-%m-%d')+timedelta(days=1)
        if a>=b: raise ValueError()
    except ValueError: abort(400,description='Choose a valid date range (YYYY-MM-DD).')
    return start,end,a,b


def extra_rows(kind):
    """Rows for the exports that are not part of report(): chatbot questions and creator visits per day."""
    start,end,a,b=date_range()
    if kind=='inbox':
        q=db.select(Message).where(Message.created_at>=a,Message.created_at<b).order_by(Message.created_at.desc())
        rows=[dict(message_id=m.id,created_at=m.created_at.isoformat(timespec='seconds') if m.created_at else '',kind=m.kind,topic=m.topic,order_id=m.order_id or '',
                   status=m.status,name=m.name,email_masked=mask_email(m.email),body=m.body,reply=m.reply or '',
                   replied_at=m.replied_at.isoformat(timespec='seconds') if m.replied_at else '') for m in db.session.scalars(q)]
    elif kind=='chatbot-questions':
        from support.models import ChatQuestion
        q=db.select(ChatQuestion).where(ChatQuestion.created_at>=a,ChatQuestion.created_at<b).order_by(ChatQuestion.created_at.desc())
        rows=[dict(question_id=c.id,created_at=c.created_at.isoformat(timespec='seconds'),language=c.language,visitor=c.visitor,topic=c.topic,question=c.question,
                   reply=c.reply,verdict=c.verdict,codes=c.codes,action=c.action,is_dummy=c.is_dummy) for c in db.session.scalars(q)]
    else:
        from shop.referral import CreatorVisit
        q=db.select(CreatorVisit,ReferralLink).join(ReferralLink,CreatorVisit.link_id==ReferralLink.id).where(CreatorVisit.day>=a.date(),CreatorVisit.day<b.date()).order_by(CreatorVisit.day,ReferralLink.code,CreatorVisit.is_dummy)
        rows=[dict(date=v.day.isoformat(),discount_code=l.code,creator=l.influencer_name,platform=l.platform,visits=v.visits,is_dummy=v.is_dummy) for v,l in db.session.execute(q)]
    return rows,start,end


def export_payload(kind):
    """(csv text, file name) for one export — the same file for /admin/export/<kind>.csv and the token API /api/export/<kind>.csv."""
    if kind=='inventory':
        return export_csv(),f"reboot_inventory_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    if kind not in FIELDS: abort(404)
    platform=request.args.get('platform','all')
    if kind in INFLUENCER_KINDS and platform not in ('all',*PLATFORMS): abort(400,description='Choose instagram, tiktok, or all.')
    sentiment=request.args.get('sentiment','all')
    if kind=='reviews' and sentiment not in SENTIMENTS: abort(400,description='Choose positive, negative, neutral, or all.')
    if kind in ('chatbot-questions','creator-visits','inbox'):
        rows,start,end=extra_rows(kind)
    else:
        data=report(); start,end=data['start'],data['end']
        if kind=='reviews': rows=[r for r in data['reviews']['items'] if sentiment=='all' or r['sentiment']==sentiment]
        elif kind=='review-summary': rows=data['reviews']['by_month']
        else: rows=data[SOURCES[kind]]
        if kind in INFLUENCER_KINDS: rows=influencer_rows(rows,platform)
        if kind=='creator-performance': rows=[dict(r,link_url=site_url()+r['link_path']) for r in rows]
    stream=io.StringIO(newline=''); writer=csv.DictWriter(stream,fieldnames=FIELDS[kind]); writer.writeheader()
    for row in rows: writer.writerow({key:safe_cell(row[key]) for key in FIELDS[kind]})
    suffix=f'_{platform}' if kind in INFLUENCER_KINDS else f'_{sentiment}' if kind=='reviews' else ''
    return stream.getvalue(),f"reboot_{kind.replace('-','_')}{suffix}_{start.replace('-','')}_{end.replace('-','')}.csv"


def csv_response(text, filename):
    return Response(text.encode('utf-8-sig'),mimetype='text/csv',headers={'Content-Disposition':f'attachment; filename="{filename}"','Cache-Control':'no-store'})


@bp.get('/export/<kind>.csv')
@admin_required
def export(kind):
    return csv_response(*export_payload(kind))

def site_url():
    """Public base URL used in creator share links (SITE_URL in .env, else the current host)."""
    return (os.getenv('SITE_URL') or request.url_root).rstrip('/')


@bp.post('/creators')
@admin_required
def add_creator():
    """Issue a creator's dedicated link: /r/<CODE>. The code is also the discount code applied at checkout."""
    from admin.actions import build_creator, ActionError
    try: link=build_creator(request.form)
    except ActionError as e:
        flash(str(e),'error'); return redirect('/admin/manage#creators')
    db.session.add(link)
    db.session.commit()
    code=link.code
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
    pages={'':'Creator deal page (all products, discounted)'}
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
    from support.guard import rules_info
    from admin.assistant import system_prompt as assistant_prompt
    return render_template('admin/chatbot.html',title='Chatbot',config=chat_config(),prompt=system_prompt(),rules=rules_info(),assistant_prompt=assistant_prompt(),result=None)


@bp.post('/chatbot/test')
@admin_required
def chatbot_test():
    """Send one short question to OpenAI with the live persona, so the admin sees exactly what fails."""
    from support import system_prompt, chat_config, ask_openai
    from support.guard import rules_info
    ok,detail=ask_openai([{'role':'user','content':'Hi! What flavors does Reboot Jelly Original come in?'}])
    from admin.assistant import system_prompt as assistant_prompt
    return render_template('admin/chatbot.html',title='Chatbot',config=chat_config(),prompt=system_prompt(),rules=rules_info(),assistant_prompt=assistant_prompt(),result=dict(ok=ok,detail=detail))


# ---------- Customer care: what visitors ask the chatbot (README §25) ----------
def chat_days():
    from support.insights import PERIODS
    try: days=int(request.values.get('days',30))
    except ValueError: abort(400)
    if days not in PERIODS: abort(400)
    return days


@bp.get('/chatbot/questions')
@admin_required
def chat_questions():
    from support import chat_config
    from support.insights import overview, latest_report, PERIODS, LABELS
    days=chat_days()
    return render_template('admin/chat_questions.html',title='Chatbot questions',data=overview(days),report=latest_report(days),
                           periods=PERIODS,labels=LABELS,config=chat_config())


@bp.post('/chatbot/questions/analyze')
@admin_required
def chat_questions_analyze():
    from support.insights import run_analysis
    days=chat_days()
    ok,detail=run_analysis(days)
    if ok: flash('AI analysis updated.')
    else: flash(detail,'error')
    return redirect(f'/admin/chatbot/questions?days={days}#ai-analysis')


CHAT_FIELDS='question_id asked_at topic topic_label question language visitor guard_verdict guard_codes guard_action is_dummy'.split()


@bp.get('/chatbot/questions.csv')
@admin_required
def chat_questions_csv():
    """Question log for the marketing dashboard (insights / VOC). Admin test chats are left out."""
    from support.insights import period_query, LABELS
    from support.models import ChatQuestion
    days=chat_days()
    stream=io.StringIO(newline=''); writer=csv.DictWriter(stream,fieldnames=CHAT_FIELDS); writer.writeheader()
    for r in db.session.scalars(period_query(days).order_by(ChatQuestion.created_at)):
        row=dict(question_id=r.id,asked_at=r.created_at.strftime('%Y-%m-%d %H:%M'),topic=r.topic,topic_label=LABELS[r.topic][0] if r.topic in LABELS else r.topic,
                 question=r.question,language=r.language,visitor=r.visitor,guard_verdict=r.verdict,guard_codes=r.codes,guard_action=r.action,is_dummy=r.is_dummy)
        writer.writerow({k:safe_cell(v) for k,v in row.items()})
    filename=f"reboot_chat_questions_{days}d_{date.today().strftime('%Y%m%d')}.csv"
    return Response(stream.getvalue().encode('utf-8-sig'),mimetype='text/csv',headers={'Content-Disposition':f'attachment; filename="{filename}"','Cache-Control':'no-store'})


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
        flash('This file is not UTF-8. In Excel choose File › Save As › “CSV UTF-8 (Comma delimited)” and upload again.','error'); return redirect('/admin/inventory#upload')
    changes,errors=parse_csv(text,mode)
    if mode=='add' and not errors:
        cur={i.option_id:i.on_hand for i in db.session.scalars(db.select(Inventory))}
        errors=[f'{o.sku}: stock would go below 0 ({cur.get(o.id,0)} on hand {q:+d})' for o,q,_ in changes if cur.get(o.id,0)+q<0]
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
from products.media import ProductImage, ProductText, ProductDetail, to_webp, image_slots, url_for_image, name_overrides
from products.services import get_all_products as _gap
_catalog_all=lambda: _gap(include_hidden=True)


@bp.get('/products')
@admin_required
def product_photos():
    current={i.original:i for i in db.session.scalars(db.select(ProductImage))}
    names=name_overrides()
    rows={r.slug:r for r in db.session.scalars(db.select(Product))}
    merged={p['slug']:p.get('details') or {} for p in _catalog_all()}
    catalog=[dict(p=p,gallery=_gallery_rows(p,current),details=merged.get(p['slug'],{}),row=rows.get(p['slug']),name=names.get(p['slug'],p['name']),renamed=p['slug'] in names,slots=[dict(s,url=url_for_image(current[s['src']]) if s['src'] in current else image_url(s['src']),
                                  original_url=image_url(s['src']),replaced=s['src'] in current) for s in image_slots(p)]) for p in load_original()]
    from products.autopage import AutoPage
    pages={a.slug:a for a in db.session.scalars(db.select(AutoPage))}
    return render_template('admin/products.html',title='Products',catalog=catalog,autopages=pages,autopage=_autopage_info())


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



# ---------- Products: add / remove gallery photos (README §34) ----------
def _gallery_rows(p, current):
    """Gallery of a product for the admin: original photos (with on/off) + added ones."""
    from products.media import gallery_changes
    c = gallery_changes().get(p['slug'], {'hidden': set(), 'added': []})
    rows = [dict(kind='original', src=g['src'], label=g.get('label', ''), url=url_for_image(current[g['src']]) if g['src'] in current else image_url(g['src']),
                 hidden=g['src'] in c['hidden']) for g in p['images'].get('gallery', [])]
    rows += [dict(kind='added', id=a['added_id'], label=a['label'], url=a['src'], hidden=False) for a in c['added']]
    return rows


def _wants_json(): return request.accept_mimetypes.best == 'application/json'


@bp.post('/products/gallery/add')
@admin_required
def product_gallery_add():
    from products.media import GalleryPhoto
    slug=request.form.get('slug','')
    if not any(p['slug']==slug for p in load_original()): abort(400)
    files=[f for f in request.files.getlist('photo') if f and f.filename][:12]
    label=' '.join(request.form.get('label','').split())[:60]
    def answer(msg, ok=True, code=200):
        if _wants_json(): return jsonify(ok=ok, message=msg) if ok else jsonify(error=msg), code
        flash(msg, None if ok else 'error'); return redirect(f'/admin/products#p-{slug}')
    if not files: return answer('Choose a photo to add.', False, 400)
    last=db.session.scalar(db.select(db.func.max(GalleryPhoto.position)).filter_by(slug=slug)) or 0
    for i,f in enumerate(files,1):
        try: data=to_webp(f.read())
        except ValueError as e: db.session.rollback(); return answer(str(e), False, 400)
        except Exception: db.session.rollback(); return answer('That file is not a readable image (JPG, PNG or WEBP).', False, 400)
        db.session.add(GalleryPhoto(slug=slug,label=label or 'Photo',data=data,position=last+i))
    from rewards.services import record
    record('product_gallery_added',{'product':slug,'count':len(files)})
    db.session.commit()
    return answer(f'{len(files)} photo(s) added to the product page.')


@bp.post('/products/gallery/<int:photo_id>/delete')
@admin_required
def product_gallery_delete(photo_id):
    from products.media import GalleryPhoto
    photo=db.session.get(GalleryPhoto,photo_id) or abort(404)
    slug=photo.slug; db.session.delete(photo); db.session.commit()
    flash('Photo removed from the product page.')
    return redirect(f'/admin/products#p-{slug}')


@bp.post('/products/gallery/toggle')
@admin_required
def product_gallery_toggle():
    """Take an original gallery photo off the product page, or put it back."""
    from products.media import GalleryHidden
    slug=request.form.get('slug',''); src=request.form.get('src','')
    p=next((p for p in load_original() if p['slug']==slug),None)
    if not p or not any(g['src']==src for g in p['images'].get('gallery',[])): abort(400)
    row=db.session.scalar(db.select(GalleryHidden).filter_by(slug=slug,src=src))
    if row: db.session.delete(row); flash('Photo is back on the product page.')
    else: db.session.add(GalleryHidden(slug=slug,src=src)); flash('Photo removed from the product page (you can put it back).')
    db.session.commit()
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
    from admin.actions import build_popup, ActionError
    try: build_popup(p,request.form)
    except ActionError as e:
        flash(str(e),'error'); return back
    f=request.files.get('image')
    if f and f.filename:
        try: p.image=to_webp(f.read())
        except Exception as e:
            flash(str(e) if isinstance(e,ValueError) else 'That file is not a readable image (JPG, PNG or WEBP).','error'); return back
    elif request.form.get('remove_image'): p.image=None
    if popup_id: p.version=(p.version or 1)+1
    else: p.is_active=True; db.session.add(p)
    from rewards.services import record
    record('popup_saved',{'title':p.title})
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


def _autopage_info():
    from products import autopage
    ai=autopage.ai_images_ready(); total,per=autopage.estimate() if ai else (0,0)
    return dict(ai=ai,total=f'{total:g}',per=f'{per:g}')


@bp.get('/products/new')
@admin_required
def product_new():
    return render_template('admin/product_new.html',title='Add product',form=request.args,autopage=_autopage_info())


@bp.post('/products/new')
@admin_required
def product_create():
    f=request.form
    def fail(msg):
        flash(msg,'error'); return render_template('admin/product_new.html',title='Add product',form=f,autopage=_autopage_info()),400
    from admin.actions import build_product, create_product, ActionError
    photo=request.files.get('photo')
    try: plan=build_product(f,bool(photo and photo.filename))
    except ActionError as e: return fail(str(e))
    try: image=to_webp(photo.read())
    except Exception as e: return fail(str(e) if isinstance(e,ValueError) else 'That file is not a readable image.')
    create_product(plan,image); name=plan['name']; slug=plan['slug']
    from products import autopage
    if f.get('auto_page'): autopage.queue(slug, use_ai_images=bool(f.get('auto_page_ai')))
    db.session.commit()
    if f.get('auto_page'): autopage.kick()
    flash(f'{name} was added' + (' as hidden. Press Show when it is ready.' if f.get('hidden') else ' and is live on the Products page.')
          + (' Its long detail page is being made automatically.' if f.get('auto_page') else ''))
    return redirect(f'/admin/products#p-{slug}')


@bp.post('/products/<slug>/autopage')
@admin_required
def product_autopage(slug):
    """Make (or remake) the automatic long detail page of a product (README §34)."""
    from products import autopage
    if not any(p['slug']==slug for p in load_original()): abort(404)
    if request.form.get('ai'):  # new backgrounds: keep the old ones in Rebu Studio but stop reusing them
        from products.story import StoryImage
        for im in db.session.scalars(db.select(StoryImage).filter(StoryImage.slug==slug,StoryImage.slot.like('auto-bg-%'))): im.slot='old-'+im.slot[5:]
    autopage.queue(slug, use_ai_images=bool(request.form.get('ai')))
    db.session.commit(); autopage.kick()
    flash('The long detail page is being made. Refresh in a minute or two.')
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


# ---------- Admin AI assistant (README §27) ----------
from admin import assistant  # noqa: E402,F401  (routes + admin_assistant_* tables)



@bp.post('/products/ingredients')
@admin_required
def product_ingredients():
    """Edit the ingredient list (one per line, most to least by weight) and confirm it for the public product page."""
    slug=request.form.get('slug','')
    if not any(p['slug']==slug for p in load_original()): abort(400)
    items=[' '.join(x.split())[:160] for x in request.form.get('ingredients','').splitlines() if x.strip()][:40]
    sweet=' '.join(request.form.get('sweetened_with','').split())[:120]
    confirmed=bool(request.form.get('confirmed'))
    back=redirect(f'/admin/products#ing-{slug}')
    if confirmed and not items:
        flash('Add the ingredient list before confirming it.','error'); return back
    row=db.session.scalar(db.select(ProductDetail).filter_by(slug=slug))
    if not row: row=ProductDetail(slug=slug); db.session.add(row)
    row.ingredients=items; row.sweetened_with=sweet; row.confirmed=confirmed; row.updated_at=datetime.now(timezone.utc)
    from rewards.services import record
    record('ingredients_saved',{'product':slug,'confirmed':confirmed})
    db.session.commit()
    flash('Ingredients saved and shown on the product page.' if confirmed else 'Ingredients saved as a draft (shoppers see the key ingredients only).')
    return back


# ---------- Product detail pages with AI (README §28) ----------
from admin import story as _story_tab  # noqa: E402,F401


# ---------- Settings: API connections (README §29) ----------
@bp.get('/settings/connections')
@admin_required
def connections():
    from support import chat_config
    from support import higgsfield
    from products.story import image_config
    return render_template('admin/connections.html', title='API connections', openai=chat_config(), openai_image=image_config(),
                           hf=higgsfield.config(), results={})


@bp.post('/settings/connections/test')
@admin_required
def connections_test():
    from support import chat_config, openai_request
    from support import higgsfield
    from products.story import image_config
    which=request.form.get('service')
    results={}
    if which in ('openai','all'):
        ok,detail=openai_request({'messages':[{'role':'user','content':'Reply with OK.'}],'max_completion_tokens':5})
        results['openai']=dict(ok=ok,detail='Connected.' if ok else detail)
    if which in ('higgsfield','all'):
        ok,detail=higgsfield.test() if higgsfield.credentials() else (False,'Higgsfield API key is not set.')
        results['higgsfield']=dict(ok=ok,detail=detail)
    return render_template('admin/connections.html', title='API connections', openai=chat_config(), openai_image=image_config(),
                           hf=higgsfield.config(), results=results)


# ---------- Per-tab AI workspaces (README §30) ----------
from admin import workspace  # noqa: E402,F401
