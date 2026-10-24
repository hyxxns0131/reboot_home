import csv
import io
import re
from collections import Counter
from decimal import Decimal
import secrets
import pytest
from app import create_app
from core.extensions import db
from shop.models import Order, OrderItem, ReferralLink
from auth.models import User

@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setenv('ADMIN_EMAIL','admin@example.test')
    monkeypatch.setenv('CUSTOMER_EMAIL','customer@example.test')
    password=secrets.token_urlsafe(18)
    monkeypatch.setenv('ADMIN_PASSWORD',password)
    monkeypatch.setenv('CUSTOMER_PASSWORD',password)
    monkeypatch.setenv('SEED_DUMMY_DATA','1')
    app=create_app({'TESTING':True,'SECRET_KEY':secrets.token_hex(32),'SQLALCHEMY_DATABASE_URI':'sqlite:///:memory:'})
    app.config['TEST_PASSWORD']=password
    result=app.test_cli_runner().invoke(args=['setup-db'])
    assert result.exit_code==0,result.output
    yield app
    with app.app_context(): db.session.remove(); db.drop_all()

@pytest.fixture()
def client(app): return app.test_client()

def token(client,path='/auth/login'):
    response=client.get(path)
    match=re.search(r'name="csrf_token" value="([^"]+)"',response.get_data(as_text=True))
    assert match,response.status_code
    return match[1]

def login(client,app,role='customer',suffix=''):
    return client.post('/auth/login'+suffix,data={'csrf_token':token(client),'email':role+'@example.test','password':app.config['TEST_PASSWORD']})

@pytest.mark.parametrize('path',['/','/about/story','/products/','/products/jelly-original','/products/jelly-balance','/products/drink-original','/products/drink-balance','/shop/','/feed/','/feed/the-art-of-the-restart','/where-to-buy/','/vibe-test/','/creators/','/contact/','/legal/','/auth/login','/auth/register','/auth/logout'])
def test_public(client,path): assert client.get(path,follow_redirects=True).status_code==200

def test_roles_and_logout(client,app):
    for path in ['/admin/','/admin/export/orders.csv','/shop/cart','/shop/orders']:
        assert client.get(path).status_code==302
    assert login(client,app).status_code==302
    assert client.get('/admin/').status_code==403
    assert client.get('/admin/export/orders.csv').status_code==403
    assert client.get('/shop/cart').status_code==200
    assert client.get('/auth/logout').status_code==200
    assert client.get('/shop/cart').status_code==200 # GET logout does not mutate session
    assert client.post('/auth/logout').status_code==400
    assert client.post('/auth/logout',data={'csrf_token':token(client,'/auth/logout')}).status_code==200
    assert client.get('/shop/cart').status_code==302
    assert login(client,app,'admin').location=='/admin/'
    assert client.get('/shop/cart').status_code==403
    assert client.get('/admin/').status_code==200

def test_csrf_and_redirect(client,app):
    assert client.post('/auth/login',data={'email':'customer@example.test','password':app.config['TEST_PASSWORD']}).status_code==400
    assert login(client,app,suffix='?next=//evil.example').location=='/'
    assert client.get('/nothing').status_code==404
    assert client.get('/r/UNKNOWN').status_code==404

def test_order_referral_csv(client,app):
    assert client.get('/r/NEONNIGHTS').status_code==302
    login(client,app)
    response=client.post('/shop/cart',data={'csrf_token':token(client,'/products/drink-original'),'sku':'drink-original-box3','quantity':2,'price':'.01'})
    assert response.status_code==302
    page=client.get('/shop/checkout').get_data(as_text=True)
    csrf=re.search(r'name="csrf_token" value="([^"]+)"',page)[1]
    nonce=re.search(r'name="nonce" value="([^"]+)"',page)[1]
    data={'csrf_token':csrf,'nonce':nonce,'name':'Demo','state':'CA','city':'Demo City'}
    response=client.post('/shop/checkout',data=data)
    assert response.location=='/shop/orders'
    client.post('/shop/checkout',data=data) # repeated submission must not duplicate
    with app.app_context():
        orders=db.session.scalars(db.select(Order).filter_by(is_dummy=False)).all()
        assert len(orders)==1
        order=orders[0]
        assert order.subtotal==Decimal('38.00') and order.discount==Decimal('3.80') and order.total==Decimal('34.20')
        assert order.referral.code=='NEONNIGHTS' and order.items[0].quantity==2
    assert client.get('/shop/orders').status_code==200
    client.post('/auth/logout',data={'csrf_token':token(client,'/auth/logout')})
    login(client,app,'admin')
    for kind in ('product-sales','link-sales','orders'):
        response=client.get(f'/admin/export/{kind}.csv?start=2026-01-01&end=2030-12-31&status=all')
        assert response.status_code==200 and response.data.startswith(b'\xef\xbb\xbf')
        rows=list(csv.DictReader(io.StringIO(response.data.decode('utf-8-sig'))))
        assert rows
        if kind=='orders':
            actual=[r for r in rows if r['is_dummy']=='False']
            assert len(actual)==1 and actual[0]['line_total_usd']=='34.20'
        if kind=='product-sales':
            product_total=sum(Decimal(r['net_sales_usd']) for r in rows)
        if kind=='link-sales': assert sum(Decimal(r['net_sales_usd']) for r in rows)==product_total
    assert client.get('/admin/?start=bad').status_code==400
    assert client.get('/admin/export/orders.csv?start=2030-12-31&end=2020-01-01').status_code==400

def test_seed_idempotence(app):
    assert app.test_cli_runner().invoke(args=['setup-db']).exit_code==0
    with app.app_context():
        orders=db.session.scalars(db.select(Order)).all()
        assert len(orders)==1000
        product_counts=Counter(item.product_id for order in orders for item in order.items)
        link_counts=Counter(order.referral_link_id for order in orders if order.referral_link_id)
        assert len(product_counts)==4 and min(product_counts.values())>=100
        assert len(link_counts)==6 and min(link_counts.values())>=100
        assert db.session.query(User).count()==2
        assert all(u.password_hash!=app.config['TEST_PASSWORD'] for u in db.session.scalars(db.select(User)))

def test_register_always_customer(client,app):
    response=client.post('/auth/register',data={'csrf_token':token(client,'/auth/register'),'email':'new@example.test','name':'New','password':app.config['TEST_PASSWORD'],'confirm':app.config['TEST_PASSWORD'],'adult':'on','role':'admin'})
    assert response.status_code==302
    assert client.get('/admin/').status_code==403
    with app.app_context(): assert db.session.scalar(db.select(User).filter_by(email='new@example.test')).role=='customer'

def test_csv_formula():
    from admin import safe_cell
    for v in ['=SUM(A1:A2)','+cmd','-cmd','@SUM(A1)','\t=cmd','  =cmd']:
        assert safe_cell(v).startswith("'")
    assert safe_cell('NORMAL')=='NORMAL'

def test_remember_cookie_cleared_on_logout(client,app):
    client.post('/auth/login',data={'csrf_token':token(client),'email':'customer@example.test','password':app.config['TEST_PASSWORD'],'remember':'on'})
    assert client.get_cookie('remember_token') is not None
    client.post('/auth/logout',data={'csrf_token':token(client,'/auth/logout')})
    assert client.get_cookie('remember_token') is None
    assert client.get('/shop/orders').status_code==302

def test_empty_export_and_input_validation(client,app):
    login(client,app,'admin')
    response=client.get('/admin/export/orders.csv?start=2000-01-01&end=2000-01-02')
    assert response.status_code==200
    rows=list(csv.reader(io.StringIO(response.data.decode('utf-8-sig'))))
    assert len(rows)==1 and rows[0][0]=='order_id'
    assert client.get('/admin/?status=bogus').status_code==400

def test_retailer_links(client):
    html=client.get('/where-to-buy/').get_data(as_text=True)
    for url in ['https://www.yamibuy.com/','https://www.amazon.com/','https://global.oliveyoung.com/','https://www.sayweee.com/']:
        assert f'href="{url}" target="_blank" rel="noopener noreferrer"' in html

def test_reels_embed_only_instagram(client,monkeypatch):
    monkeypatch.setattr('feed.REELS',[]) # Isolate empty-state test from editorial content.
    assert 'reel-grid' not in client.get('/').get_data(as_text=True)
    monkeypatch.setattr('feed.REELS',['https://www.instagram.com/reel/AbC_12-x/?igsh=abc','https://evil.example/reel/zzz/','javascript:alert(1)'])
    for path in ['/','/feed/']:
        html=client.get(path).get_data(as_text=True)
        assert html.count('<iframe')==1 and 'src="https://www.instagram.com/reel/AbC_12-x/embed/"' in html
    monkeypatch.setattr('feed.REELS',['https://www.instagram.com/p/Po5t_1/?utm_source=ig_web_copy_link'])
    assert 'src="https://www.instagram.com/p/Po5t_1/embed/"' in client.get('/feed/').get_data(as_text=True)

def test_support_chat(client,monkeypatch):
    import json
    headers={'X-CSRFToken':token(client,'/')}
    ask=lambda messages: client.post('/support/chat',json={'messages':messages},headers=headers)
    hello=[{'role':'user','content':'Where can I buy Reboot?'}]
    assert client.post('/support/chat',json={'messages':hello}).status_code==400 # CSRF
    assert ask([{'role':'assistant','content':'Hi'}]).status_code==400
    assert ask([{'role':'user','content':'x'*1001}]).status_code==400
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    assert ask(hello).status_code==503
    monkeypatch.setenv('OPENAI_API_KEY','test-key')
    sent={}
    def urlopen(request,timeout):
        sent.update(body=json.loads(request.data),auth=request.get_header('Authorization'))
        return io.BytesIO(json.dumps({'choices':[{'message':{'content':'Try Amazon or Weee!'}}]}).encode())
    monkeypatch.setattr('support.urllib.request.urlopen',urlopen)
    assert ask(hello).get_json()=={'reply':'Try Amazon or Weee!'}
    assert sent['auth']=='Bearer test-key'
    system=sent['body']['messages'][0]
    assert system['role']=='system' and 'Reboot Jelly Original' in system['content'] and 'Olive Young Global' in system['content']
    for _ in range(19): assert ask(hello).status_code==200
    assert ask(hello).status_code==429

def test_catalog_options_and_images(client,app):
    import json
    from pathlib import Path
    from shop.models import Product, ProductOption
    html=client.get('/products/drink-original').get_data(as_text=True)
    assert all(f'value="drink-original-{s}"' in html for s in ('box3','lemon','lime','cherry')) and 'drink-original-single' not in html
    html=client.get('/products/jelly-balance').get_data(as_text=True)
    # product pages use the studio photos derived from images/product_image
    assert '/images/product_image/web/jelly-balance-package.webp' in html and all(f'/images/product_image/web/jelly-balance-{f}.webp' in html for f in ('lime','lemon','cherry'))
    for p in json.loads(Path('products/data/products.json').read_text()):
        for src in [p['images']['main'],p['images'].get('card','')]+[g['src'] for g in p['images']['gallery']]+[o['image'] for o in p['options']]:
            if not src: continue
            assert src.startswith('product_image/') and (Path('images')/src).exists(),src
    login(client,app)
    assert client.post('/shop/cart',data={'csrf_token':token(client,'/products/drink-balance'),'sku':'drink-balance-lime','quantity':1}).status_code==302
    with app.app_context(): # options removed from products.json stop selling on the next setup-db
        product=db.session.scalar(db.select(Product).filter_by(slug='drink-original'))
        db.session.add(ProductOption(product_id=product.id,sku='drink-original-single',label='1 Bottle',price=7)); db.session.commit()
    assert app.test_cli_runner().invoke(args=['setup-db']).exit_code==0
    with app.app_context(): assert not db.session.scalar(db.select(ProductOption).filter_by(sku='drink-original-single')).is_active

@pytest.mark.parametrize('line',['original','balance'])
@pytest.mark.parametrize('flavor',['lime','lemon','cherry'])
def test_showcase_purchase_link_selects_flavor(client,line,flavor):
    sku=f'drink-{line}-{flavor}'
    html=client.get(f'/products/drink-{line}?sku={sku}').get_data(as_text=True)
    assert re.search(r'value="'+sku+r'"[^>]* checked',html)
    assert re.search(r'class="[^"]*detail-shot[^>]+src="[^"]*'+sku+r'\.webp',html) or re.search(r'src="[^"]*'+sku+r'\.webp[^>]+class="[^"]*detail-shot',html)

def test_unknown_product_option_falls_back(client):
    html=client.get('/products/drink-original?sku=unknown').get_data(as_text=True)
    assert re.search(r'value="drink-original-box3"[^>]* checked',html)
