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
        assert order.subtotal==Decimal('25.98') and order.discount==Decimal('2.60') and order.total==Decimal('23.38')
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
            assert len(actual)==1 and actual[0]['line_total_usd']=='23.38'
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

def test_option_and_influencer_platform_csv(client,app):
    login(client,app,'admin')
    q='start=2026-01-01&end=2030-12-31&status=all'
    rows=list(csv.DictReader(io.StringIO(client.get(f'/admin/export/option-sales.csv?{q}').data.decode('utf-8-sig'))))
    from products.services import get_all_products
    skus={o['sku'] for p in get_all_products() for o in p['options']}
    assert {r['option_sku'] for r in rows}==skus
    assert all(int(r['order_count'])>=100 for r in rows)  # every sales option has 100+ dummy orders
    jelly=[r for r in rows if r['product_line']=='Jelly']
    assert len(jelly)==2  # jelly is sold per line package only, never per flavor
    for r in rows:
        assert Decimal(r['net_sales_usd'])==Decimal(r['direct_sales_usd'])+Decimal(r['instagram_sales_usd'])+Decimal(r['tiktok_sales_usd'])
    product_rows=list(csv.DictReader(io.StringIO(client.get(f'/admin/export/product-sales.csv?{q}').data.decode('utf-8-sig'))))
    assert sum(Decimal(r['net_sales_usd']) for r in rows)==sum(Decimal(r['net_sales_usd']) for r in product_rows)
    totals={}
    for platform,name in (('instagram','Instagram'),('tiktok','TikTok')):
        response=client.get(f'/admin/export/influencer-sales.csv?platform={platform}&{q}')
        assert response.status_code==200 and f'influencer_sales_{platform}_' in response.headers['Content-Disposition']
        summary=list(csv.DictReader(io.StringIO(response.data.decode('utf-8-sig'))))
        assert len(summary)==3 and {r['platform'] for r in summary}=={name}
        assert all(r['discount_code'] and r['link_path']=='/r/'+r['discount_code'] and int(r['order_count'])>=100 for r in summary)
        lines=list(csv.DictReader(io.StringIO(client.get(f'/admin/export/influencer-orders.csv?platform={platform}&{q}').data.decode('utf-8-sig'))))
        assert lines and {r['platform'] for r in lines}=={name}
        assert sum(Decimal(r['line_total_usd']) for r in lines)==sum(Decimal(r['net_sales_usd']) for r in summary)
        totals[platform]=sum(Decimal(r['instagram_sales_usd' if platform=='instagram' else 'tiktok_sales_usd']) for r in rows)
        assert totals[platform]==sum(Decimal(r['net_sales_usd']) for r in summary)
    assert client.get(f'/admin/export/influencer-sales.csv?platform=youtube&{q}').status_code==400
    page=client.get('/admin/').get_data(as_text=True)
    assert 'platform=instagram' in page and 'platform=tiktok' in page and 'option-sales' in page


# ---- Reboot Town (/game/) ----
from datetime import timedelta
from game.models import GameRun


def game_post(client, path, body):
    return client.post(path, json=body, headers={'X-CSRFToken': token(client, '/game/')})


def age_run(app, run_id, seconds):
    with app.app_context():
        run = db.session.get(GameRun, run_id)
        run.started_at = run.started_at - timedelta(seconds=seconds)
        db.session.commit()


def test_game_page_public_and_nav(client):
    page = client.get('/game/').get_data(as_text=True)
    assert 'id="game-canvas"' in page and 'href="/game/"' in page
    assert 'Log in to earn' in page and '/auth/login?next=/game/' in page
    assert client.get('/rewards/').location.endswith('/game/')
    assert client.post('/game/api/runs', json={'game': 'lasso-leap'}).status_code in (302, 400)


def test_game_points_rules(client, app):
    login(client, app)
    assert 'Earned today' in client.get('/game/').get_data(as_text=True)
    assert game_post(client, '/game/api/runs', {'game': 'nope'}).status_code == 400
    run = game_post(client, '/game/api/runs', {'game': 'lasso-leap'}).get_json()
    # impossible score right after start -> rejected, 0 points
    res = game_post(client, f"/game/api/runs/{run['run_id']}/finish", {'score': 400})
    assert res.status_code == 200 and res.get_json()['run_status'] == 'rejected' and res.get_json()['points_earned'] == 0
    assert game_post(client, f"/game/api/runs/{run['run_id']}/finish", {'score': 1}).status_code == 409
    assert game_post(client, f"/game/api/runs/{run['run_id']}/finish", {'score': True}).status_code == 400
    # plausible runs pay, capped at 300 per run and 1,000 per day
    earned = []
    for _ in range(4):
        run = game_post(client, '/game/api/runs', {'game': 'lasso-leap'}).get_json()
        age_run(app, run['run_id'], 120)
        data = game_post(client, f"/game/api/runs/{run['run_id']}/finish", {'score': 50}).get_json()
        earned.append(data['points_earned'])
    assert earned == [300, 300, 300, 100]
    assert data['today_earned'] == 1000 and data['balance'] == 1000 and data['best']['lasso-leap'] == 50
    with app.app_context():
        user = db.session.scalar(db.select(User).filter_by(email='customer@example.test'))
        from rewards.models import PointEntry
        assert sum(e.amount for e in db.session.scalars(db.select(PointEntry).filter_by(user_id=user.id, reason='game_reward'))) == 1000
    # bottle pop needs the full 30 seconds
    run = game_post(client, '/game/api/runs', {'game': 'bottle-pop'}).get_json()
    age_run(app, run['run_id'], 10)
    assert game_post(client, f"/game/api/runs/{run['run_id']}/finish", {'score': 5}).get_json()['run_status'] == 'rejected'


def test_game_admin_cannot_earn(client, app):
    login(client, app, 'admin')
    assert client.get('/game/').status_code == 200
    assert game_post(client, '/game/api/runs', {'game': 'jelly-drop'}).status_code == 403

def rows_of(response):
    assert response.status_code==200 and response.data.startswith(b'\xef\xbb\xbf')
    return list(csv.DictReader(io.StringIO(response.data.decode('utf-8-sig'))))

def test_product_reviews(client,app):
    from products.models import Review
    page=client.get('/products/jelly-original').get_data(as_text=True)
    assert 'id="reviews"' in page and 'Login to write a review' in page
    assert client.post('/products/jelly-original/reviews',data={'rating':5,'body':'Great taste and cute shapes.'}).status_code in (302,400)
    login(client,app)
    csrf=token(client,'/products/jelly-original')
    bad=client.post('/products/jelly-original/reviews',data={'csrf_token':csrf,'rating':9,'body':'Great taste and cute shapes.'})
    assert bad.status_code==302
    client.post('/products/jelly-original/reviews',data={'csrf_token':csrf,'rating':5,'title':'So fun','body':'Great taste and cute <b>shapes</b>.'})
    page=client.get('/products/jelly-original').get_data(as_text=True)
    assert 'So fun' in page and '&lt;b&gt;shapes' in page and 'You reviewed this product' in page
    client.post('/products/jelly-original/reviews',data={'csrf_token':csrf,'rating':1,'body':'Second review should be rejected.'})
    client.post('/products/drink-original/reviews',data={'csrf_token':csrf,'rating':2,'title':'Hangover cure','body':'It cured my hangover fast.'})
    assert 'Hangover cure' not in client.get('/products/drink-original').get_data(as_text=True)
    with app.app_context():
        mine=db.session.scalars(db.select(Review).filter_by(is_dummy=False).order_by(Review.id)).all()
        assert [(r.rating,r.sentiment,r.status) for r in mine]==[(5,'positive','published'),(2,'negative','held')]
        from collections import Counter
        per_product=Counter(r.product_id for r in db.session.scalars(db.select(Review).filter_by(is_dummy=True)))
        assert len(per_product)==4 and min(per_product.values())>=100
    client.post('/auth/logout',data={'csrf_token':token(client,'/auth/logout')})
    login(client,app,'admin')
    assert client.post('/products/jelly-balance/reviews',data={'csrf_token':token(client,'/products/jelly-balance'),'rating':5,'body':'Admins cannot review.'}).status_code==403
    q='start=2026-01-01&end=2030-12-31'
    positive=rows_of(client.get(f'/admin/export/reviews.csv?sentiment=positive&{q}'))
    negative=rows_of(client.get(f'/admin/export/reviews.csv?sentiment=negative&{q}'))
    everything=rows_of(client.get(f'/admin/export/reviews.csv?sentiment=all&{q}'))
    assert positive and {r['sentiment'] for r in positive}=={'positive'} and all(int(r['rating'])>=4 for r in positive)
    assert negative and {r['sentiment'] for r in negative}=={'negative'} and all(int(r['rating'])<=2 for r in negative)
    assert any(r['status']=='held' and r['is_dummy']=='False' for r in everything)
    summary=rows_of(client.get(f'/admin/export/review-summary.csv?{q}'))
    assert sum(int(r['review_count']) for r in summary)==len(everything)
    assert sum(int(r['positive']) for r in summary)==len(positive)
    march=rows_of(client.get('/admin/export/reviews.csv?sentiment=all&start=2026-03-01&end=2026-03-31'))
    assert march and all(r['created_at'].startswith('2026-03') for r in march)
    assert client.get(f'/admin/export/reviews.csv?sentiment=angry&{q}').status_code==400

def test_creator_links_and_direct_sales(client,app):
    login(client,app,'admin')
    q='start=2026-01-01&end=2030-12-31&status=all'
    creators=rows_of(client.get(f'/admin/export/creator-performance.csv?{q}'))
    assert len(creators)==6 and list(creators[0])==['creator','discount_code','platform','link_url','clicks','order_count','units_sold','net_sales_usd','conversion_rate_pct','commission_usd']
    assert all(r['link_url'].endswith('/r/'+r['discount_code']) and int(r['clicks'])>int(r['order_count'])>=100 for r in creators)
    assert [Decimal(r['net_sales_usd']) for r in creators]==sorted((Decimal(r['net_sales_usd']) for r in creators),reverse=True)
    assert {r['platform'] for r in rows_of(client.get(f'/admin/export/creator-performance.csv?platform=tiktok&{q}'))}=={'TikTok'}
    direct=rows_of(client.get(f'/admin/export/direct-orders.csv?{q}'))
    orders=rows_of(client.get(f'/admin/export/orders.csv?{q}'))
    assert len(direct)==sum(r['link_code']=='DIRECT' for r in orders)
    total=sum(Decimal(r['line_total_usd']) for r in orders)
    assert sum(Decimal(r['line_total_usd']) for r in direct)+sum(Decimal(r['net_sales_usd']) for r in creators)==total
    # issue a new creator link from the admin page
    csrf=token(client,'/admin/')
    client.post('/admin/creators',data={'csrf_token':csrf,'name':'Test Creator','platform':'Instagram','discount':'15','commission':'10'})
    client.post('/admin/creators',data={'csrf_token':csrf,'name':'Dup','platform':'Instagram','discount':'15','commission':'10','code':'testcreato15'})
    client.post('/admin/creators',data={'csrf_token':csrf,'name':'Bad','platform':'YouTube','discount':'15','commission':'10'})
    with app.app_context():
        new=db.session.scalars(db.select(ReferralLink).filter(ReferralLink.code.in_(['TESTCREATO15','DUP15','BAD15']))).all()
        assert [l.code for l in new]==['TESTCREATO15'] and new[0].discount_rate==Decimal('0.15')
        link_id=new[0].id
    assert 'TESTCREATO15' in client.get('/admin/').get_data(as_text=True)
    client.post('/auth/logout',data={'csrf_token':token(client,'/auth/logout')})
    response=client.get('/r/testcreato15?to=/products/drink-original')
    assert response.location=='/products/drink-original' and 'ref_code=TESTCREATO15' in response.headers['Set-Cookie']
    assert client.get('/r/TESTCREATO15?to=//evil.example').location=='/'
    login(client,app)
    client.post('/shop/cart',data={'csrf_token':token(client,'/products/drink-original'),'sku':'drink-original-box3','quantity':1})
    cart=client.get('/shop/cart').get_data(as_text=True)
    assert 'TESTCREATO15 (15%)' in cart and '−$1.95' in cart
    client.post('/auth/logout',data={'csrf_token':token(client,'/auth/logout')})
    login(client,app,'admin')
    client.post(f'/admin/creators/{link_id}/toggle',data={'csrf_token':token(client,'/admin/')})
    assert client.get('/r/TESTCREATO15').status_code==404


# ---- Admin: Homepage manager (product discounts, creator codes) ----
from shop.models import Product, ProductOption, ProductDiscount


def test_manage_tab_access(client, app):
    assert client.get('/admin/manage').status_code == 302
    login(client, app)
    assert client.get('/admin/manage').status_code == 403
    client.post('/auth/logout', data={'csrf_token': token(client, '/auth/logout')})
    login(client, app, 'admin')
    page = client.get('/admin/manage').get_data(as_text=True)
    assert 'HOMEPAGE MANAGER.' in page and 'PRODUCT DISCOUNTS' in page and 'CREATOR CODES' in page
    sales = client.get('/admin/').get_data(as_text=True)
    for link in ('/admin/#product-performance', '/admin/#sales-by-option', '/admin/#influencer-sales', '/admin/manage#discounts',
                 '/admin/inventory', '/admin/products', '/admin/inbox', '/admin/chatbot'):
        assert f'href="{link}"' in sales
    for anchor in ('product-performance', 'sales-by-option', 'influencer-sales'):
        assert f'id="{anchor}"' in sales


def test_product_discounts_apply_everywhere(client, app):
    login(client, app, 'admin')
    with app.app_context():
        jelly = db.session.scalar(db.select(Product).filter_by(slug='jelly-original')).id
        box = db.session.scalar(db.select(ProductOption).filter_by(sku='drink-original-box3')).id
    csrf = token(client, '/admin/manage')
    client.post('/admin/discounts', data={'csrf_token': csrf, 'target': f'p:{jelly}', 'kind': 'percent', 'value': '20', 'label': 'Fall sale'})
    client.post('/admin/discounts', data={'csrf_token': csrf, 'target': f'o:{box}', 'kind': 'amount', 'value': '2'})
    # rejected: too big, bad range
    client.post('/admin/discounts', data={'csrf_token': csrf, 'target': f'o:{box}', 'kind': 'amount', 'value': '20'})
    client.post('/admin/discounts', data={'csrf_token': csrf, 'target': f'p:{jelly}', 'kind': 'percent', 'value': '95'})
    client.post('/admin/discounts', data={'csrf_token': csrf, 'target': f'p:{jelly}', 'kind': 'percent', 'value': '10', 'starts_on': '2026-12-01', 'ends_on': '2026-11-01'})
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(ProductDiscount.id))) == 2
    assert '$14.39' in client.get('/products/jelly-original').get_data(as_text=True)  # 17.99 - 20%
    assert '$10.99' in client.get('/products/drink-original').get_data(as_text=True)  # 12.99 - $2
    assert '20% OFF' in client.get('/products/').get_data(as_text=True)
    client.post('/auth/logout', data={'csrf_token': token(client, '/auth/logout')})
    login(client, app)
    for sku in ('jelly-original-pouch', 'drink-original-box3'):
        client.post('/shop/cart', data={'csrf_token': token(client, '/products/jelly-original'), 'sku': sku, 'quantity': 1})
    cart = client.get('/shop/cart').get_data(as_text=True)
    assert 'Sale discount' in cart and '−$5.60' in cart and '$25.38' in cart  # 30.98 - 3.60 - 2.00
    # creator code typed in the bag applies on top of the sale price (10% of 25.38)
    client.post('/shop/code', data={'csrf_token': token(client, '/shop/cart'), 'code': 'neonnights'})
    cart = client.get('/shop/cart').get_data(as_text=True)
    assert 'NEONNIGHTS (10%)' in cart and '−$2.54' in cart
    client.post('/shop/code', data={'csrf_token': token(client, '/shop/cart'), 'code': 'NOPE'})
    checkout = client.get('/shop/checkout').get_data(as_text=True)
    nonce = re.search(r'name="nonce" value="([^"]+)"', checkout)[1]
    csrf_c = re.search(r'name="csrf_token" value="([^"]+)"', checkout)[1]
    client.post('/shop/checkout', data={'csrf_token': csrf_c, 'nonce': nonce, 'name': 'A', 'city': 'LA', 'state': 'CA', 'points': '0'})
    with app.app_context():
        order = db.session.scalar(db.select(Order).filter_by(is_dummy=False).order_by(Order.id.desc()))
        assert order.subtotal == Decimal('30.98') and order.total == Decimal('22.84') and order.referral.code == 'NEONNIGHTS'
        assert sum(i.line_total for i in order.items) == order.total


def test_creator_link_landing_and_edit(client, app):
    login(client, app, 'admin')
    csrf = token(client, '/admin/manage')
    client.post('/admin/creators', data={'csrf_token': csrf, 'name': 'Lime Lover', 'platform': 'TikTok', 'discount': '12', 'commission': '8', 'code': 'limelover', 'landing': '/products/jelly-balance'})
    with app.app_context():
        link = db.session.scalar(db.select(ReferralLink).filter_by(code='LIMELOVER'))
        assert link.landing == '/products/jelly-balance' and link.discount_rate == Decimal('0.12')
        link_id = link.id
    assert client.get('/r/LIMELOVER').location == '/products/jelly-balance'
    client.post(f'/admin/creators/{link_id}/edit', data={'csrf_token': csrf, 'discount': '25', 'commission': '10', 'landing': ''})
    client.post(f'/admin/creators/{link_id}/edit', data={'csrf_token': csrf, 'discount': '80', 'commission': '10', 'landing': '//evil'})
    with app.app_context():
        link = db.session.get(ReferralLink, link_id)
        assert link.discount_rate == Decimal('0.25') and link.landing == ''
    assert client.get('/r/LIMELOVER').location == '/'



# ---- Sample wording, reviews, contact inbox, chatbot, inventory, product photos ----
import io as _io


def test_no_sample_price_wording(client):
    for path in ('/products/', '/products/drink-original', '/'):
        assert 'Sample price' not in client.get(path).get_data(as_text=True)


def test_delete_own_review(client, app):
    login(client, app)
    csrf = token(client, '/products/jelly-balance')
    client.post('/products/jelly-balance/reviews', data={'csrf_token': csrf, 'rating': 5, 'title': 'Love the boots', 'body': 'The lime boot is my favorite shape.'})
    assert 'Delete my review' in client.get('/products/jelly-balance').get_data(as_text=True)
    client.post('/products/jelly-balance/reviews/delete', data={'csrf_token': token(client, '/products/jelly-balance')})
    page = client.get('/products/jelly-balance').get_data(as_text=True)
    assert 'Love the boots' not in page and 'Delete my review' not in page


def test_contact_goes_to_admin_inbox(client, app):
    page = client.get('/contact/').get_data(as_text=True)
    assert 'Log in to send an inquiry' in page and 'name="email"' not in page
    login(client, app)
    page = client.get('/contact/').get_data(as_text=True)
    assert 'name="email"' not in page and 'customer@example.test' in page
    client.post('/contact/', data={'csrf_token': token(client, '/contact/'), 'topic': 'Product', 'message': 'How many jellies are in one pouch?'})
    client.post('/auth/logout', data={'csrf_token': token(client, '/auth/logout')})
    login(client, app, 'admin')
    inbox = client.get('/admin/inbox').get_data(as_text=True)
    assert 'How many jellies are in one pouch?' in inbox and 'customer@example.test' in inbox
    from core.messages import Message
    with app.app_context():
        mid = db.session.scalar(db.select(Message.id).filter_by(kind='contact'))
    client.post(f'/admin/inbox/{mid}', data={'csrf_token': token(client, '/admin/inbox'), 'action': 'reply', 'reply': 'Each pouch has all three shapes.'})
    client.post('/auth/logout', data={'csrf_token': token(client, '/auth/logout')})
    login(client, app)
    page = client.get('/contact/').get_data(as_text=True)
    assert 'Each pouch has all three shapes.' in page and 'Answered' in page


def test_chatbot_admin_status_and_persona(client, app, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    login(client, app, 'admin')
    page = client.get('/admin/chatbot').get_data(as_text=True)
    assert 'Missing' in page and 'You are Rebu' in page and 'line package' in page
    monkeypatch.setenv('OPENAI_API_KEY', '  "sk-test-1234567890"  ')
    import urllib.error
    def fail(request, timeout):
        assert request.get_header('Authorization') == 'Bearer sk-test-1234567890'
        raise urllib.error.HTTPError(request.full_url, 401, 'Unauthorized', {}, _io.BytesIO(b'{"error":{"message":"Incorrect API key provided"}}'))
    monkeypatch.setattr('support.urllib.request.urlopen', fail)
    page = client.post('/admin/chatbot/test', data={'csrf_token': token(client, '/admin/chatbot')}).get_data(as_text=True)
    assert 'HTTP 401' in page and 'Incorrect API key provided' in page


def test_inventory_seed_edit_csv_and_orders(client, app):
    from shop.inventory import Inventory, StockMove
    with app.app_context():
        box = db.session.scalar(db.select(ProductOption).filter_by(sku='drink-original-box3'))
        cherry = db.session.scalar(db.select(ProductOption).filter_by(sku='drink-balance-cherry'))
        assert db.session.scalar(db.select(db.func.count(Inventory.id))) == 10
        assert db.session.scalar(db.select(Inventory.on_hand).filter_by(option_id=cherry.id)) == 18
        box_id, cherry_id = box.id, cherry.id
    login(client, app, 'admin')
    page = client.get('/admin/inventory').get_data(as_text=True)
    assert 'INVENTORY.' in page and 'drink-balance-cherry' in page
    csv_text = client.get('/admin/inventory.csv').get_data(as_text=True)
    assert csv_text.lstrip('\ufeff').startswith('sku,product,option,on_hand,reorder_level')
    form = {'csrf_token': token(client, '/admin/inventory'), 'note': 'count'}
    with app.app_context():
        for inv in db.session.scalars(db.select(Inventory)):
            form[f'on_hand_{inv.option_id}'] = inv.on_hand; form[f'reorder_{inv.option_id}'] = inv.reorder_level
    form[f'on_hand_{box_id}'] = 2
    client.post('/admin/inventory', data=form)
    up = lambda text, mode: client.post('/admin/inventory/upload', data={'csrf_token': token(client, '/admin/inventory'), 'mode': mode,
                                                                       'file': (_io.BytesIO(text.encode()), 'stock.csv')}, content_type='multipart/form-data')
    up('sku,on_hand\ndrink-balance-cherry,5\nnope,3\n', 'set')          # bad row -> nothing changes
    up('sku,on_hand,reorder_level\ndrink-balance-cherry,100,30\n', 'add')  # delivery
    with app.app_context():
        assert db.session.scalar(db.select(Inventory.on_hand).filter_by(option_id=box_id)) == 2
        inv = db.session.scalar(db.select(Inventory).filter_by(option_id=cherry_id))
        assert inv.on_hand == 118 and inv.reorder_level == 30
    client.post('/auth/logout', data={'csrf_token': token(client, '/auth/logout')})
    login(client, app)
    csrf = token(client, '/products/drink-original')
    client.post('/shop/cart', data={'csrf_token': csrf, 'sku': 'drink-original-box3', 'quantity': 3})
    assert 'drink-original-box3' not in client.get('/shop/cart').get_data(as_text=True)  # only 2 left
    client.post('/shop/cart', data={'csrf_token': csrf, 'sku': 'drink-original-box3', 'quantity': 2})
    checkout = client.get('/shop/checkout').get_data(as_text=True)
    client.post('/shop/checkout', data={'csrf_token': re.search(r'name="csrf_token" value="([^"]+)"', checkout)[1],
                                        'nonce': re.search(r'name="nonce" value="([^"]+)"', checkout)[1], 'name': 'A', 'city': 'LA', 'state': 'CA', 'points': '0'})
    with app.app_context():
        assert db.session.scalar(db.select(Inventory.on_hand).filter_by(option_id=box_id)) == 0
        assert db.session.scalar(db.select(StockMove).filter_by(option_id=box_id, reason='order')).change == -2
    assert 'Sold out' in client.get('/products/drink-original').get_data(as_text=True)


def test_admin_product_photo_upload(client, app):
    from PIL import Image
    login(client, app, 'admin')
    assert 'PRODUCTS.' in client.get('/admin/products').get_data(as_text=True)
    buf = _io.BytesIO(); Image.new('RGBA', (2400, 1200), (177, 255, 59, 255)).save(buf, 'PNG'); buf.seek(0)
    src = 'product_image/web/jelly-original-card.webp'
    client.post('/admin/products/photo', data={'csrf_token': token(client, '/admin/products'), 'slug': 'jelly-original', 'src': src,
                                               'photo': (buf, 'new.png')}, content_type='multipart/form-data')
    from products.media import ProductImage
    with app.app_context():
        img = db.session.scalar(db.select(ProductImage).filter_by(original=src))
        assert img and Image.open(_io.BytesIO(img.data)).size == (1600, 800)
        url = f'/media/products/{img.id}.webp'
    assert url in client.get('/products/').get_data(as_text=True)
    assert client.get(url).mimetype == 'image/webp'
    bad = client.post('/admin/products/photo', data={'csrf_token': token(client, '/admin/products'), 'slug': 'jelly-original', 'src': src,
                                                     'photo': (_io.BytesIO(b'not an image'), 'x.png')}, content_type='multipart/form-data', follow_redirects=True)
    assert 'not a readable image' in bad.get_data(as_text=True)
    assert client.post('/admin/products/photo', data={'csrf_token': token(client, '/admin/products'), 'slug': 'jelly-original', 'src': '../../app.py'}).status_code == 400
    client.post('/admin/products/photo/reset', data={'csrf_token': token(client, '/admin/products'), 'slug': 'jelly-original', 'src': src})
    assert url not in client.get('/products/').get_data(as_text=True)


def test_admin_rename_product(client, app):
    login(client, app, 'admin')
    client.post('/admin/products/name', data={'csrf_token': token(client, '/admin/products'), 'slug': 'drink-balance', 'name': 'Reboot Drink Zero'})
    assert 'Reboot Drink Zero' in client.get('/products/drink-balance').get_data(as_text=True)
    assert 'Drink Zero' in client.get('/products/').get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(db.select(Product.name).filter_by(slug='drink-balance')) == 'Reboot Drink Zero'
    client.post('/admin/products/name', data={'csrf_token': token(client, '/admin/products'), 'slug': 'drink-balance', 'name': 'x'})
    client.post('/admin/products/name', data={'csrf_token': token(client, '/admin/products'), 'slug': 'drink-balance', 'name': 'ignored', 'reset': '1'})
    with app.app_context():
        assert db.session.scalar(db.select(Product.name).filter_by(slug='drink-balance')) == 'Reboot Drink Balance'


def test_site_popup(client, app):
    from PIL import Image
    login(client, app, 'admin')
    buf = _io.BytesIO(); Image.new('RGB', (800, 1000), (249, 49, 110)).save(buf, 'JPEG'); buf.seek(0)
    csrf = token(client, '/admin/manage')
    client.post('/admin/popups', data={'csrf_token': csrf, 'title': 'Bad link', 'button_label': 'Go', 'button_link': 'javascript:alert(1)', 'placement': 'all'})
    client.post('/admin/popups', data={'csrf_token': csrf, 'title': 'Halloween sale', 'body': '20% off jelly', 'button_label': 'Shop jelly',
                                       'button_link': '/products/jelly-original', 'placement': 'home', 'image': (buf, 'p.jpg')}, content_type='multipart/form-data')
    from core.popups import Popup
    with app.app_context():
        assert [p.title for p in db.session.scalars(db.select(Popup))] == ['Halloween sale']
        pid = db.session.scalar(db.select(Popup.id))
    assert 'id="site-popup"' not in client.get('/admin/manage').get_data(as_text=True)  # never on admin pages
    client.post('/auth/logout', data={'csrf_token': token(client, '/auth/logout')})
    home = client.get('/').get_data(as_text=True)
    assert 'id="site-popup"' in home and 'Halloween sale' in home and f'/media/popups/{pid}.webp' in home
    assert 'id="site-popup"' not in client.get('/products/').get_data(as_text=True)  # home only
    assert client.get(f'/media/popups/{pid}.webp').mimetype == 'image/webp'
    login(client, app, 'admin')
    client.post(f'/admin/popups/{pid}/toggle', data={'csrf_token': token(client, '/admin/manage')})
    assert 'id="site-popup"' not in client.get('/').get_data(as_text=True)


def _png(size=(600, 600), color=(255, 140, 0, 255)):
    from PIL import Image
    buf = _io.BytesIO(); Image.new('RGBA', size, color).save(buf, 'PNG'); buf.seek(0); return buf


def test_register_hide_delete_product(client, app):
    login(client, app, 'admin')
    assert 'ADD PRODUCT.' in client.get('/admin/products/new').get_data(as_text=True)
    form = {'csrf_token': token(client, '/admin/products/new'), 'name': 'Reboot Jelly Pumpkin', 'line': 'Jelly', 'version': 'original',
            'badge': 'HALLOWEEN LIMITED', 'format': 'Shaped jelly', 'pack': 'One pouch', 'flavors': 'pumpkin, apple',
            'opt_label_0': '1 Package', 'opt_price_0': '18.99', 'opt_count_0': '1', 'opt_stock_0': '50'}
    assert client.post('/admin/products/new', data=dict(form)).status_code == 400  # photo required
    client.post('/admin/products/new', data=dict(form, photo=(_png(), 'p.png')), content_type='multipart/form-data')
    page = client.get('/products/').get_data(as_text=True)
    assert 'HALLOWEEN LIMITED' in page and '/products/reboot-jelly-pumpkin' in page
    detail = client.get('/products/reboot-jelly-pumpkin').get_data(as_text=True)
    assert 'Pumpkin' in detail and '$18.99' in detail and 'reboot-jelly-pumpkin-1-package' in detail
    from shop.inventory import Inventory
    with app.app_context():
        opt = db.session.scalar(db.select(ProductOption).filter_by(sku='reboot-jelly-pumpkin-1-package'))
        assert db.session.scalar(db.select(Inventory.on_hand).filter_by(option_id=opt.id)) == 50
    st = lambda slug, action: client.post(f'/admin/products/{slug}/status', data={'csrf_token': token(client, '/admin/products'), 'action': action})
    st('reboot-jelly-pumpkin', 'hide')
    assert client.get('/products/reboot-jelly-pumpkin').status_code == 404 and 'Pumpkin' not in client.get('/products/').get_data(as_text=True)
    st('reboot-jelly-pumpkin', 'show')
    assert client.get('/products/reboot-jelly-pumpkin').status_code == 200
    st('reboot-jelly-pumpkin', 'delete')  # never ordered -> removed completely
    from products.custom import CustomProduct
    with app.app_context():
        assert not db.session.scalar(db.select(CustomProduct).filter_by(slug='reboot-jelly-pumpkin'))
        assert not db.session.scalar(db.select(Product).filter_by(slug='reboot-jelly-pumpkin'))
    # an original product with orders is archived, not removed, and can be restored
    st('drink-balance', 'delete')
    assert client.get('/products/drink-balance').status_code == 404
    with app.app_context():
        assert db.session.scalar(db.select(Product.is_deleted).filter_by(slug='drink-balance')) is True
    assert 'ARCHIVED' in client.get('/admin/products').get_data(as_text=True)
    st('drink-balance', 'restore'); st('drink-balance', 'show')
    assert client.get('/products/drink-balance').status_code == 200
