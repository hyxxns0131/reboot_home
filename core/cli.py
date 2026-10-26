import os
import random
from datetime import datetime, timedelta
from decimal import Decimal
import click
from werkzeug.security import generate_password_hash
from core.extensions import db
from auth.models import User
from shop.models import Product, ProductOption, ReferralLink, Order
from shop.services import create_order
from products.services import get_all_products

def setup():
    credentials={key:os.getenv(key,'').strip() for key in ('ADMIN_EMAIL','ADMIN_PASSWORD','CUSTOMER_EMAIL','CUSTOMER_PASSWORD')}
    if not all(credentials.values()): raise click.ClickException('Set ADMIN_EMAIL, ADMIN_PASSWORD, CUSTOMER_EMAIL, CUSTOMER_PASSWORD in .env first.')
    if credentials['ADMIN_EMAIL'].lower()==credentials['CUSTOMER_EMAIL'].lower(): raise click.ClickException('Admin and customer emails must differ.')
    if any(len(credentials[key])<8 for key in ('ADMIN_PASSWORD','CUSTOMER_PASSWORD')): raise click.ClickException('Use passwords with at least 8 characters.')
    from core.migrations import upgrade_database
    upgrade_database()
    for role in ('admin','customer'):
        email=credentials[role.upper()+'_EMAIL'].lower()
        if not db.session.scalar(db.select(User).filter_by(email=email)):
            db.session.add(User(email=email,password_hash=generate_password_hash(credentials[role.upper()+'_PASSWORD'], method='pbkdf2:sha256:1000000'),role=role,name='Administrator' if role=='admin' else 'Reboot Member'))
    for data in get_all_products(include_hidden=True):
        product=db.session.scalar(db.select(Product).filter_by(slug=data['slug']))
        if not product:
            product=Product(slug=data['slug'],name=data['name']); db.session.add(product); db.session.flush()
        product.name=data['name']
        for item in data['options']:
            option=db.session.scalar(db.select(ProductOption).filter_by(sku=item['sku']))
            if not option: option=ProductOption(sku=item['sku'],product_id=product.id); db.session.add(option)
            option.label=item['label']; option.unit_count=item['unit_count']; option.price=Decimal(str(item['price_usd'])); option.is_active=not product.is_deleted
        # Options dropped from products.json stop selling but stay in the DB for past orders.
        db.session.flush()
        for option in db.session.scalars(db.select(ProductOption).filter(ProductOption.product_id==product.id,ProductOption.sku.not_in([o['sku'] for o in data['options']]))):
            option.is_active=False
    # Dummy creators (all fictional): Instagram 10 + TikTok 12. No YouTube.
    seeds=[('NEONNIGHTS','Neon Nights','TikTok',10,15),('KPARTYLA','K-Party LA','Instagram',10,12),('MORNINGRESET','Morning Reset','Instagram',15,15),('SEOULSIPNYC','Seoul Sip NYC','TikTok',10,10),('BRUNCHCLUB','Brunch Club','Instagram',5,10),('RESTARTCREW','Restart Crew','TikTok',20,20),
           ('GLOWHOURLA','Glow Hour LA','Instagram',10,12),('SUNSETSIPS','Sunset Sips','Instagram',10,10),('PASTELPANTRY','Pastel Pantry','Instagram',5,8),('CITYBITESSF','City Bites SF','Instagram',10,10),('NIGHTOWLNYC','Night Owl NYC','Instagram',15,12),('SEOULSTYLE','Seoul Style Diary','Instagram',10,15),('WKNDWANDER','Weekend Wanderer','Instagram',5,10),
           ('PARTYPREP','Party Prep Pro','TikTok',15,15),('SNACKCHECK','Snack Check Daily','TikTok',10,12),('LATENIGHTBITES','Late Night Bites','TikTok',10,10),('KSNACKREVIEW','K-Snack Review','TikTok',10,15),('ROOFTOPHOURS','Rooftop Hours','TikTok',15,10),('ROADTRIPDUO','Road Trip Duo','TikTok',10,12),('GAMEDAYCREW','Game Day Crew','TikTok',20,15),('TASTETINA','Taste Test Tina','TikTok',10,10),('FESTIVALFAM','Festival Fam','TikTok',15,12)]
    assert sum(p=='Instagram' for _c,_n,p,_d,_m in seeds)==10 and sum(p=='TikTok' for _c,_n,p,_d,_m in seeds)==12
    # Orders per creator link: 100–240, skewed so a few creators lead (like a real roster). Visits = orders × 30–60.
    quota={code:100+int(140*random.Random('orders-'+code).random()**2) for code,*_ in seeds}
    for code,name,platform,discount,commission in seeds:
        existing=db.session.scalar(db.select(ReferralLink).filter_by(code=code))
        if existing: existing.platform=platform  # influencer links are split into Instagram / TikTok only
        else:
            db.session.add(ReferralLink(code=code,influencer_name=name+' (Fictional)',platform=platform,discount_rate=Decimal(discount)/100,commission_rate=Decimal(commission)/100,clicks=quota[code]*random.Random(code).randint(30,60)))  # ~1.7–3.3% conversion
    db.session.flush()
    if os.getenv('SEED_DUMMY_DATA','1')=='1':
        # An older dummy set (e.g. the 6-creator one with a YouTube link) doesn't cover every creator above.
        # Rebuild only the dummy orders; accounts, real orders and admin-made links stay as they are.
        roster=[db.session.scalar(db.select(ReferralLink).filter_by(code=code)) for code,*_ in seeds]
        used=set(db.session.scalars(db.select(Order.referral_link_id).filter_by(is_dummy=True).distinct()))
        if used and not {l.id for l in roster}<=used:
            from rewards.models import PointEntry, CheckoutReceipt
            dummy_ids=db.session.scalars(db.select(Order.id).filter_by(is_dummy=True)).all()
            linked=set(db.session.scalars(db.select(PointEntry.order_id).where(PointEntry.order_id.in_(dummy_ids))))|set(db.session.scalars(db.select(CheckoutReceipt.order_id).where(CheckoutReceipt.order_id.in_(dummy_ids))))
            for order in db.session.scalars(db.select(Order).filter_by(is_dummy=True)):
                if order.id not in linked: db.session.delete(order)
            for link in roster: link.clicks=quota[link.code]*random.Random(link.code).randint(30,60)
            db.session.flush()
            click.echo('Old dummy orders replaced with the current creator roster (Instagram 10 · TikTok 12).')
    if os.getenv('SEED_DUMMY_DATA','1')=='1' and not db.session.scalar(db.select(Order).filter_by(is_dummy=True).limit(1)):
        rng=random.Random(42); products=db.session.scalars(db.select(Product).order_by(Product.id)).all()
        links=[db.session.scalar(db.select(ReferralLink).filter_by(code=code)) for code,*_ in seeds]
        # one entry per dummy order: each creator's quota, then 700 direct-store orders (no link)
        assign=[link for link in links for _ in range(quota[link.code])]+[None]*700
        counts={p.id:0 for p in products}; link_counts={l.id:0 for l in links}; option_counts={}; platform_counts={'Instagram':0,'TikTok':0}
        dates=[datetime(2026,1,1)+timedelta(days=i) for i in range(295)]
        for i in range(len(assign)):
            selected=[products[i%4]]+rng.sample([p for p in products if p.id!=products[i%4].id],rng.randint(0,2))
            lines=[]
            for j,p in enumerate(selected):
                opts=sorted((o for o in p.options if o.is_active),key=lambda o:o.id)
                # The lead product rotates through every sales option so each option gets 100+ orders.
                option=opts[(i//4)%len(opts)] if j==0 else rng.choice(opts)
                lines.append((option,rng.randint(1,3))); option_counts[option.sku]=option_counts.get(option.sku,0)+1
            link=assign[i]
            if link: link_counts[link.id]+=1; platform_counts[link.platform]=platform_counts.get(link.platform,0)+1
            for p in selected: counts[p.id]+=1
            day=rng.choices(dates,weights=[3 if d.weekday() in (4,5) else 1 for d in dates])[0]
            create_order(lines,link,is_dummy=True,status=rng.choices(['paid','refunded','cancelled'],weights=[95,3,2])[0],ship_name='Sample Customer',ship_city='Demo City',ship_state=rng.choice(['CA','CA','NY','TX','WA','NJ','IL']),ordered_at=day+timedelta(hours=rng.choice([19,20,21,22,23])))
        active_skus={o.sku for p in products for o in p.options if o.is_active}
        assert all(n>=100 for n in counts.values()) and all(n>=100 for n in link_counts.values())
        assert all(option_counts.get(sku,0)>=100 for sku in active_skus) and all(platform_counts[name]>=100 for name in ('Instagram','TikTok'))
    from products.models import Review
    from shop.inventory import seed_inventory
    db.session.flush(); seed_inventory()
    from shop.referral import seed_dummy_visits
    if os.getenv('SEED_DUMMY_DATA','1')=='1': db.session.flush(); seed_dummy_visits()  # creator visits per day (README §39)
    from products.sample_reviews import seed_sample_reviews
    if os.getenv('SEED_DUMMY_DATA','1')=='1': seed_sample_reviews()  # 11–12 product-specific sample reviews each (README §34)
    from products.story import seed_stories
    seed_stories()  # detail pages for the launch products, once (README §28)
    if os.getenv('SEED_DUMMY_DATA','1')=='1':
        from support.seed import seed_dummy_chats
        seed_dummy_chats()  # sample chatbot questions, once (README §25)
    db.session.commit()
    click.echo('Database ready. Accounts, catalog, and sample data initialized (existing records preserved).')

def setup_if_outdated():
    """Run setup() at server start when the sample data is older than the code (README §34) — so the creator roster, sample
    reviews and catalog are current however the server was started (start.command, flask run, an IDE). Cheap check first."""
    from shop.models import ReferralLink
    from products.models import Review
    from products.sample_reviews import SAMPLES
    first = SAMPLES['jelly-original'][0]['title']
    creators = db.session.scalar(db.select(db.func.count(ReferralLink.id)).filter(ReferralLink.influencer_name.like('%(Fictional)'))) or 0
    samples = db.session.scalar(db.select(db.func.count(Review.id)).where(Review.is_dummy.is_(True), Review.title==first)) or 0
    dummies = db.session.scalar(db.select(db.func.count(Review.id)).where(Review.is_dummy.is_(True))) or 0
    from shop.referral import CreatorVisit
    visits = db.session.scalar(db.select(CreatorVisit.id).where(CreatorVisit.is_dummy.is_(True)).limit(1))
    if creators >= 22 and samples and visits and dummies == sum(len(v) for v in SAMPLES.values()): return False
    setup()
    return True


def register_cli(app):
    @app.cli.command('upgrade-db')
    def upgrade_db():
        from core.migrations import upgrade_database
        upgrade_database()
        click.echo('Database upgraded. Existing records preserved.')
    @app.cli.command('setup-db')
    def setup_db(): setup()
    @app.cli.command('reset-db')
    @click.confirmation_option(prompt='Delete all local accounts and orders?')
    def reset_db():
        if not app.debug or not app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite:'): raise click.ClickException('Reset is allowed only with local SQLite and debug enabled.')
        db.drop_all(); setup()
