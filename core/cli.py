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
    for data in get_all_products():
        product=db.session.scalar(db.select(Product).filter_by(slug=data['slug']))
        if not product:
            product=Product(slug=data['slug'],name=data['name']); db.session.add(product); db.session.flush()
        product.name=data['name']
        for item in data['options']:
            option=db.session.scalar(db.select(ProductOption).filter_by(sku=item['sku']))
            if not option: option=ProductOption(sku=item['sku'],product_id=product.id); db.session.add(option)
            option.label=item['label']; option.unit_count=item['unit_count']; option.price=Decimal(str(item['price_usd'])); option.is_active=True
        # Options dropped from products.json stop selling but stay in the DB for past orders.
        db.session.flush()
        for option in db.session.scalars(db.select(ProductOption).filter(ProductOption.product_id==product.id,ProductOption.sku.not_in([o['sku'] for o in data['options']]))):
            option.is_active=False
    seeds=[('NEONNIGHTS','Neon Nights','TikTok',10,15),('KPARTYLA','K-Party LA','Instagram',10,12),('MORNINGRESET','Morning Reset','YouTube',15,15),('SEOULSIPNYC','Seoul Sip NYC','TikTok',10,10),('BRUNCHCLUB','Brunch Club','Instagram',5,10),('RESTARTCREW','Restart Crew','TikTok',20,20)]
    for code,name,platform,discount,commission in seeds:
        if not db.session.scalar(db.select(ReferralLink).filter_by(code=code)):
            db.session.add(ReferralLink(code=code,influencer_name=name+' (Fictional)',platform=platform,discount_rate=Decimal(discount)/100,commission_rate=Decimal(commission)/100,clicks=1200))
    db.session.flush()
    if os.getenv('SEED_DUMMY_DATA','1')=='1' and not db.session.scalar(db.select(Order).filter_by(is_dummy=True).limit(1)):
        rng=random.Random(42); products=db.session.scalars(db.select(Product).order_by(Product.id)).all(); links=db.session.scalars(db.select(ReferralLink).order_by(ReferralLink.id)).all()
        counts={p.id:0 for p in products}; link_counts={l.id:0 for l in links}
        dates=[datetime(2026,1,1)+timedelta(days=i) for i in range(295)]
        for i in range(1000):
            selected=[products[i%4]]+rng.sample([p for p in products if p.id!=products[i%4].id],rng.randint(0,2))
            lines=[(rng.choice([o for o in p.options if o.is_active]),rng.randint(1,3)) for p in selected]
            link=links[i//120] if i<720 else None
            if link: link_counts[link.id]+=1
            for p in selected: counts[p.id]+=1
            day=rng.choices(dates,weights=[3 if d.weekday() in (4,5) else 1 for d in dates])[0]
            create_order(lines,link,is_dummy=True,status=rng.choices(['paid','refunded','cancelled'],weights=[95,3,2])[0],ship_name='Sample Customer',ship_city='Demo City',ship_state=rng.choice(['CA','CA','NY','TX','WA','NJ','IL']),ordered_at=day+timedelta(hours=rng.choice([19,20,21,22,23])))
        assert all(n>=100 for n in counts.values()) and all(n>=100 for n in link_counts.values())
    db.session.commit()
    click.echo('Database ready. Accounts, catalog, and sample data initialized (existing records preserved).')

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
