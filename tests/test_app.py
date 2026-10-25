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
        links=db.session.scalars(db.select(ReferralLink)).all()
        assert len(orders)==sum(1 for o in orders if o.referral_link_id)+700 and len(orders)>=2900
        assert Counter(l.platform for l in links)=={'Instagram':10,'TikTok':12}
        product_counts=Counter(item.product_id for order in orders for item in order.items)
        link_counts=Counter(order.referral_link_id for order in orders if order.referral_link_id)
        assert len(product_counts)==4 and min(product_counts.values())>=100
        assert len(link_counts)==22 and min(link_counts.values())>=100 and max(link_counts.values())<=240
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
        assert len(summary)=={'instagram':10,'tiktok':12}[platform] and {r['platform'] for r in summary}=={name}
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
        samples=db.session.scalars(db.select(Review).filter_by(is_dummy=True)).all()
        per_product=Counter(r.product_id for r in samples)
        assert len(per_product)==4 and all(11<=n<=12 for n in per_product.values())  # README §34
        for pid in per_product:
            rated=[r.rating for r in samples if r.product_id==pid]
            assert sum(rated)/len(rated)>4.8 and sum(x>=4 for x in rated)/len(rated)>=0.9
        assert len({r.body for r in samples})==len(samples)  # every product has its own copy
        from support.guard import review, STOP
        assert not [r.body for r in samples if review(r.title+'. '+r.body)['verdict'] in STOP]
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
    september=rows_of(client.get('/admin/export/reviews.csv?sentiment=all&start=2026-09-01&end=2026-09-30'))
    assert september and all(r['created_at'].startswith('2026-09') for r in september)
    assert client.get(f'/admin/export/reviews.csv?sentiment=angry&{q}').status_code==400

def test_creator_links_and_direct_sales(client,app):
    login(client,app,'admin')
    q='start=2026-01-01&end=2030-12-31&status=all'
    creators=rows_of(client.get(f'/admin/export/creator-performance.csv?{q}'))
    assert len(creators)==22 and list(creators[0])==['creator','discount_code','platform','link_url','clicks','order_count','units_sold','net_sales_usd','conversion_rate_pct','commission_usd']
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


# ---------- Ask Reboot compliance guard + question log (README §25) ----------
def test_guard_uses_dashboard_rules():
    from support.guard import review, rules_info, SAFE_REPLY
    assert rules_info()['count'] >= 10
    assert review('Reboot cures your hangover fast!')['verdict'] == 'BLOCK'
    assert review('We cannot make claims about hangovers.')['verdict'] == 'BLOCK'  # even saying "not" is stopped
    assert review('숙취에 좋아요')['verdict'] == 'BLOCK'
    assert review('Jelly Original comes in Lime, Lemon and Cherry.')['verdict'] == 'PASS'
    assert all(review(t)['verdict'] == 'PASS' for t in SAFE_REPLY.values())


def test_chat_guard_rewrites_blocks_and_logs(client, app, monkeypatch):
    import json
    from support.models import ChatQuestion
    from support.guard import SAFE_REPLY
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    answers, systems = [], []
    def urlopen(request, timeout):
        systems.append(json.loads(request.data)['messages'][0]['content'])
        return io.BytesIO(json.dumps({'choices': [{'message': {'content': answers.pop(0)}}]}).encode())
    monkeypatch.setattr('support.urllib.request.urlopen', urlopen)
    headers = {'X-CSRFToken': token(client, '/')}
    ask = lambda q: client.post('/support/chat', json={'messages': [{'role': 'user', 'content': q}]}, headers=headers).get_json()['reply']
    # 1) blocked draft -> rewritten once -> passes
    answers[:] = ['Reboot helps prevent a hangover!', 'I can’t speak to health effects. Reboot is a jelly and drink line for adults 21+.']
    assert ask('Does it work for hangovers? mail me at jo@example.com') == 'I can’t speak to health effects. Reboot is a jelly and drink line for adults 21+.'
    assert '# Compliance check' not in systems[0] and '# Compliance check' in systems[1] and 'hangover' in systems[1]
    # 2) rewrite still fails -> safe fixed answer
    answers[:] = ['It cures hangovers.', 'It relieves your hangover.']
    assert ask('Is it a hangover cure?') == SAFE_REPLY['en']
    # 3) clean answer passes untouched
    answers[:] = ['Lime is the boot, lemon the lasso, cherry the hat.']
    assert ask('Which shape is lemon?') == 'Lime is the boot, lemon the lasso, cherry the hat.'
    with app.app_context():
        rows = db.session.scalars(db.select(ChatQuestion).filter_by(is_dummy=False).order_by(ChatQuestion.id)).all()
        assert [r.action for r in rows] == ['rewritten', 'blocked', 'passed']
        assert rows[0].topic == 'health' and '[email]' in rows[0].question and 'jo@example.com' not in rows[0].question
        assert rows[0].flagged_reply == 'Reboot helps prevent a hangover!' and 'R2' in rows[1].codes
        assert rows[2].topic == 'flavors' and rows[2].visitor == 'guest'


def test_chat_question_topics():
    from support.insights import topic_of
    assert topic_of('Can I buy only the lime jelly?') == 'package'
    assert topic_of('What is the best way to reboot my day?') == 'other'  # "boot" inside "reboot" is not a flavor
    assert topic_of('Is it on Amazon?') == 'where' and topic_of('숙취에 효과 있어요?') == 'health'


def test_admin_chat_questions_page_csv_and_ai(client, app, monkeypatch):
    import json
    from support.models import ChatQuestion, ChatInsight
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(ChatQuestion.id)).filter_by(is_dummy=True)) >= 100
    assert client.get('/admin/chatbot/questions').status_code in (302, 403)
    login(client, app, 'admin')
    page = client.get('/admin/chatbot/questions?days=90').get_data(as_text=True)
    assert 'WHAT VISITORS ASK MOST' in page and 'Flavors, taste &amp; shapes' in page and 'INCLUDES SAMPLE DATA' in page
    assert client.get('/admin/chatbot/questions?days=5').status_code == 400
    assert 'COMPLIANCE GUARD' in client.get('/admin/chatbot').get_data(as_text=True)
    csv_text = client.get('/admin/chatbot/questions.csv?days=90').get_data(as_text=True)
    head = csv_text.lstrip('\ufeff').splitlines()[0]
    assert head.startswith('question_id,asked_at,topic') and len(csv_text.splitlines()) > 100
    # no key -> readable error, nothing stored
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    csrf = token(client, '/admin/chatbot/questions')
    page = client.post('/admin/chatbot/questions/analyze', data={'csrf_token': csrf, 'days': 90}, follow_redirects=True).get_data(as_text=True)
    assert 'OPENAI_API_KEY is not set.' in page
    # with key: JSON report is cleaned and shown
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    sent = {}
    result = {'summary': '맛과 구성 질문이 가장 많습니다.', 'topics': [{'key': 'flavors', 'insight': '체리 맛을 궁금해함', 'examples': ['What does cherry taste like?'], 'action': '맛 설명 추가'},
                                                     {'key': 'nope', 'insight': 'x'}], 'gaps': [{'need': '배송 기간', 'action': 'FAQ 추가'}], 'risk': '건강 질문은 안전 답변 유지'}
    def urlopen(request, timeout):
        sent.update(json.loads(request.data))
        return io.BytesIO(json.dumps({'choices': [{'message': {'content': json.dumps(result, ensure_ascii=False)}}]}).encode())
    monkeypatch.setattr('support.urllib.request.urlopen', urlopen)
    page = client.post('/admin/chatbot/questions/analyze', data={'csrf_token': csrf, 'days': 90}, follow_redirects=True).get_data(as_text=True)
    assert sent['response_format'] == {'type': 'json_object'} and 'Topic counts' in sent['messages'][1]['content']
    assert '맛과 구성 질문이 가장 많습니다.' in page and '맛 설명 추가' in page and '배송 기간' in page
    with app.app_context():
        report = json.loads(db.session.scalar(db.select(ChatInsight.result)))
        assert [t['key'] for t in report['topics']] == ['flavors']  # unknown keys dropped


def test_product_detail_ingredients(client, app):
    page = client.get('/products/jelly-balance').get_data(as_text=True)
    assert 'id="inside"' in page and 'A-HAT' in page and 'cowboy boot' in page and 'Product of Korea' in page
    assert 'Allulose' in page and 'Admin preview' not in page  # confirmed list (README §33) is shown to shoppers
    login(client, app, 'admin')
    page = client.get('/products/jelly-balance').get_data(as_text=True)
    assert 'Admin preview' not in page and 'Allulose' in page
    client.post('/admin/products/ingredients', data={'csrf_token': token(client, '/admin/products'), 'slug': 'jelly-balance', 'ingredients': '', 'confirmed': '1'})
    client.post('/admin/products/ingredients', data={'csrf_token': token(client, '/admin/products'), 'slug': 'jelly-balance',
                                                     'ingredients': 'Allulose\nWater\nPectin', 'sweetened_with': 'Allulose and stevia (Reb M)', 'confirmed': '1'})
    client.post('/auth/logout', data={'csrf_token': token(client, '/auth/logout')})
    page = client.get('/products/jelly-balance').get_data(as_text=True)
    assert 'Allulose, Water, Pectin.' in page and 'Allulose and stevia (Reb M)' in page and 'Admin preview' not in page


# ---------- Admin AI assistant (README §27) ----------
def _png_bytes():
    from PIL import Image
    buf = _io.BytesIO(); Image.new('RGB', (40, 30), (177, 255, 59)).save(buf, 'PNG'); return buf.getvalue()


def test_openai_key_aliases(monkeypatch):
    from support import key
    for name in ('OPENAI_API_KEY', 'OPEN_API_KEY', 'open_api_key'): monkeypatch.delenv(name, raising=False)
    assert key() == ''
    monkeypatch.setenv('open_api_key', ' "sk-lower" ')
    assert key() == 'sk-lower'
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-main')
    assert key() == 'sk-main'


def test_floating_assistant_is_a_guide(client, app, monkeypatch):
    import json
    login(client, app, 'admin')
    page = client.get('/admin/').get_data(as_text=True)
    assert 'data-admin-ai' in page and 'data-chat ' not in page and '/admin/ai/popup' in page
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    sent = []
    def urlopen(request, timeout):
        sent.append(json.loads(request.data))
        return _io.BytesIO(json.dumps({'choices': [{'message': {'role': 'assistant', 'content': '팝업은 /admin/ai/popup 에서 만들어요.'}}]}).encode())
    monkeypatch.setattr('support.urllib.request.urlopen', urlopen)
    body = client.post('/admin/assistant/chat', json={'messages': [{'role': 'user', 'content': '팝업 만들어줘'}]}, headers={'X-CSRFToken': token(client, '/admin/')}).get_json()
    assert body['reply'].startswith('팝업은') and 'tools' not in sent[0] and '/admin/ai/popup' in sent[0]['messages'][0]['content']


def _ws_mock(monkeypatch, replies, sent):
    import json
    def urlopen(request, timeout):
        sent.append(json.loads(request.data))
        return _io.BytesIO(json.dumps({'choices': [{'message': replies.pop(0)}]}).encode())
    monkeypatch.setattr('support.urllib.request.urlopen', urlopen)


def _upd(fields):
    import json
    return {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'u', 'type': 'function', 'function': {'name': 'update_draft', 'arguments': json.dumps({'fields': fields})}}]}


def test_ai_workspace_popup_live_draft_and_save(client, app, monkeypatch):
    from core.popups import Popup
    login(client, app, 'admin')
    assert '/admin/ai/popup' in client.get('/admin/manage').get_data(as_text=True) and '/admin/ai/product' in client.get('/admin/products/new').get_data(as_text=True)
    page = client.get('/admin/ai/popup').get_data(as_text=True)
    assert 'data-ws' in page and '리부 프로모터' in page and '실시간 초안' in page
    assert client.get('/admin/ai/nope').status_code == 404
    headers = {'X-CSRFToken': token(client, '/admin/ai/popup')}
    up = client.post('/admin/assistant/upload', data={'image': (_io.BytesIO(_png_bytes()), 'fall.png')}, headers=headers, content_type='multipart/form-data').get_json()
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    sent = []
    _ws_mock(monkeypatch, [_upd({'starts_on': '2026-10-22', 'ends_on': '2026-10-30', 'image_id': up['id']}),
                           {'role': 'assistant', 'content': '기간과 사진을 넣었어요. 제목은 1) Fall Restart Week 2) Party Season 중 어떤 게 좋을까요?'}], sent)
    chat = lambda text, images=None: client.post('/admin/ai/popup/chat', json={'messages': [{'role': 'user', 'content': text, 'images': images or []}]}, headers=headers).get_json()
    body = chat('이 사진을 10월 22일부터 30일까지 팝업으로', [up['id']])
    system = sent[0]['messages'][0]['content']
    assert '리부 프로모터' in system and '공통 규칙' in system and '빠진 필수 항목' in system
    st = body['state']
    assert st['fields']['starts_on'] == '2026-10-22' and st['image'] and st['missing'] == ['제목'] and not st['ready']
    assert client.post('/admin/ai/popup/save', headers=headers).status_code == 400  # not ready
    # a hangover title is a live problem, not saved
    _ws_mock(monkeypatch, [_upd({'title': 'Beat the hangover'}), {'role': 'assistant', 'content': '그 표현은 쓸 수 없어요.'}], sent)
    st = chat('제목 Beat the hangover')['state']
    assert st['problems'] and not st['ready']
    _ws_mock(monkeypatch, [_upd({'title': 'Fall Restart Week', 'placement': 'home'}), {'role': 'assistant', 'content': '오른쪽 [저장]을 누르면 반영돼요.'}], sent)
    st = chat('1번으로')['state']
    assert st['ready'] and st['rows'] and not st['problems']
    with app.app_context(): assert db.session.scalar(db.select(db.func.count(Popup.id))) == 0
    saved = client.post('/admin/ai/popup/save', headers=headers).get_json()
    assert saved['ok'] and saved['link'] == '/admin/manage#popups'
    with app.app_context():
        p = db.session.scalar(db.select(Popup))
        assert p.title == 'Fall Restart Week' and p.image and str(p.ends_on) == '2026-10-30'
    assert client.get('/admin/ai/popup/state').get_json()['state']['fields'] == {}  # draft cleared after saving


def test_ai_workspace_creator_and_product(client, app, monkeypatch):
    from shop.models import ReferralLink, Product
    from decimal import Decimal
    login(client, app, 'admin')
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    sent = []
    h = {'X-CSRFToken': token(client, '/admin/ai/creator')}
    _ws_mock(monkeypatch, [_upd({'name': 'Lime Lucy', 'platform': 'TikTok', 'discount': 15, 'commission': 12, 'code': 'NEONNIGHTS'}),
                           {'role': 'assistant', 'content': '이미 있는 코드예요. LIMELUCY15는 어때요?'}], sent)
    st = client.post('/admin/ai/creator/chat', json={'messages': [{'role': 'user', 'content': 'Lime Lucy 틱톡 15/12'}]}, headers=h).get_json()['state']
    assert not st['ready'] and st['problems']           # duplicate code caught live
    _ws_mock(monkeypatch, [_upd({'code': 'LIMELUCY15', 'landing': '/products/jelly-original', 'bogus': 1}), {'role': 'assistant', 'content': '좋아요.'}], sent)
    st = client.post('/admin/ai/creator/chat', json={'messages': [{'role': 'user', 'content': '그걸로'}]}, headers=h).get_json()['state']
    assert st['ready'] and 'bogus' not in st['fields']
    assert client.post('/admin/ai/creator/save', headers=h).get_json()['message'] == '크리에이터 링크를 만들었어요: /r/LIMELUCY15'
    with app.app_context(): assert db.session.scalar(db.select(ReferralLink).filter_by(code='LIMELUCY15')).platform == 'TikTok'
    # product: options agreed step by step; photo required; hidden by default
    h = {'X-CSRFToken': token(client, '/admin/ai/product')}
    up = client.post('/admin/assistant/upload', data={'image': (_io.BytesIO(_png_bytes()), 'p.png')}, headers=h, content_type='multipart/form-data').get_json()
    _ws_mock(monkeypatch, [_upd({'name': 'Reboot Jelly Pumpkin Spice', 'line': 'Jelly', 'version': 'original', 'flavors': ['Pumpkin', 'Cinnamon', 'Apple'],
                                 'format': 'Individually wrapped shaped jellies', 'pack': 'One pouch, all three shapes', 'image_id': up['id']}),
                           {'role': 'assistant', 'content': '옵션과 공개 여부를 정해요.'}], sent)
    st = client.post('/admin/ai/product/chat', json={'messages': [{'role': 'user', 'content': '펌킨 젤리', 'images': [up['id']]}]}, headers=h).get_json()['state']
    assert st['missing'] == ['판매 옵션', '공개 여부'] and st['image']
    _ws_mock(monkeypatch, [_upd({'options': [{'label': 'Line package', 'price': 18.99, 'pieces': 1, 'stock': 200}], 'publish': False}), {'role': 'assistant', 'content': '저장 가능해요.'}], sent)
    st = client.post('/admin/ai/product/chat', json={'messages': [{'role': 'user', 'content': '18.99 숨김'}]}, headers=h).get_json()['state']
    assert st['ready']
    saved = client.post('/admin/ai/product/save', headers=h).get_json()
    assert '숨김으로 등록' in saved['message'] and '상세페이지를 자동으로' in saved['message'] and saved['link'].startswith('/admin/products#p-')
    with app.app_context():
        p = db.session.scalar(db.select(Product).filter_by(slug=saved['link'].split('#p-')[1]))
        assert p and not p.is_active and p.options[0].price == Decimal('18.99')
    assert 'ADMIN AI ASSISTANT · PERSONA' in client.get('/admin/chatbot').get_data(as_text=True)


# ---------- Language of the chatbots (README §27) ----------
def test_chatbots_follow_language(client, app, monkeypatch):
    import json
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    systems = []
    def urlopen(request, timeout):
        systems.append(json.loads(request.data)['messages'][0]['content'])
        return _io.BytesIO(json.dumps({'choices': [{'message': {'role': 'assistant', 'content': 'ok'}}]}).encode())
    monkeypatch.setattr('support.urllib.request.urlopen', urlopen)
    client.post('/support/chat', json={'messages': [{'role': 'user', 'content': 'hi'}]}, headers={'X-CSRFToken': token(client, '/')})
    assert 'Reply in English' in systems[-1]
    client.post('/language', data={'language': 'ko', 'csrf_token': token(client, '/')})
    assert '리부트에 물어보기' in client.get('/').get_data(as_text=True)
    client.post('/support/chat', json={'messages': [{'role': 'user', 'content': '안녕'}]}, headers={'X-CSRFToken': token(client, '/')})
    assert 'Reply in Korean' in systems[-1]
    # admin assistant: Korean unless English is picked
    login(client, app, 'admin')
    client.post('/language', data={'language': 'ko', 'csrf_token': token(client, '/admin/')})
    client.post('/admin/assistant/chat', json={'messages': [{'role': 'user', 'content': '안녕'}]}, headers={'X-CSRFToken': token(client, '/admin/')})
    assert '# 응답 언어' in systems[-1]
    client.post('/language', data={'language': 'en', 'csrf_token': token(client, '/admin/')})
    assert 'New chat' in client.get('/admin/').get_data(as_text=True)
    client.post('/admin/assistant/chat', json={'messages': [{'role': 'user', 'content': 'hi'}]}, headers={'X-CSRFToken': token(client, '/admin/')})
    assert '# Reply language' in systems[-1]


# ---------- Detail pages (README §28) ----------
def _walk(o):
    if isinstance(o, str): yield o
    elif isinstance(o, dict):
        for v in o.values(): yield from _walk(v)
    elif isinstance(o, list):
        for v in o: yield from _walk(v)


def test_launch_long_pages_pass_compliance_and_show(client, app):
    from products.story_seed import SEED
    from support.guard import review, STOP
    for slug, c in SEED.items():
        for lang in ('en', 'ko'):
            verdicts = {t: review(t)['verdict'] for t in _walk(c[lang])}
            assert not [t for t, v in verdicts.items() if v in STOP], (slug, lang)
            # only the ingredient intro (names A-HAT / Hovenia) may need REVIEW
            assert all(t == c[lang]['ingredients']['intro'] for t, v in verdicts.items() if v != 'PASS'), (slug, lang)
    html = client.get('/products/jelly-balance').get_data(as_text=True)
    assert 'class="pd-long"' in html and 'THE PARTY ESSENTIAL' in html and 'lp-reveal' in html and 'THE LINEUP' in html
    assert 'Hovenia dulcis (Oriental raisin tree) fruit extract' in html  # confirmed list: every ingredient with its role
    assert 'A fruit-derived gelling agent' in html
    client.post('/language', data={'language': 'ko', 'csrf_token': token(client, '/')})
    assert '모양은 그대로, 설탕은 제로. 파티 준비 끝.' in client.get('/products/jelly-balance').get_data(as_text=True)
    login(client, app, 'admin')
    html = client.get('/products/jelly-balance').get_data(as_text=True)
    assert 'is-preview' not in html and '과일에서 온 겔화제' in html  # confirmed: no preview marker


def test_admin_nav_sidebar_and_connections(client, app, monkeypatch):
    from core.nav import NAV_ITEMS
    labels = [l for l, _ in NAV_ITEMS]
    assert labels.index('Game') == labels.index('Products') + 1
    login(client, app, 'admin')
    page = client.get('/admin/products/story').get_data(as_text=True)
    order = [page.index(f'data-group="{g}"') for g in ('sales', 'store', 'marketing', 'care', 'settings')]
    assert order == sorted(order) and 'data-group="store" open' in page and 'data-group="sales" open' not in page
    for name in ('HIGGSFIELD_API_KEY_ID', 'HIGGSFIELD_API_KEY_SECRET', 'HIGGSFIELD_API_KEY', 'HF_KEY'): monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    page = client.get('/admin/settings/connections').get_data(as_text=True)
    assert page.count('Missing') == 2 and 'HIGGSFIELD_API_KEY_ID' in page
    monkeypatch.setenv('HIGGSFIELD_API_KEY', 'kid-1234567890:secret')
    calls = []
    def urlopen(request, timeout):
        calls.append((request.full_url, request.get_header('Authorization')))
        return _io.BytesIO(b'{"time_series": []}')
    monkeypatch.setattr('support.higgsfield.urllib.request.urlopen', urlopen)
    page = client.post('/admin/settings/connections/test', data={'csrf_token': token(client, '/admin/settings/connections'), 'service': 'higgsfield'}).get_data(as_text=True)
    assert 'Connected.' in page and calls[0] == ('https://api.higgsfield.ai/models/usage?timeframe=day', 'Key kid-1234567890:secret')


def test_rebu_studio_chat_draft_and_image_permission(client, app, monkeypatch):
    import json, base64
    from products.story import ProductStory, StoryImage
    from products.story_seed import SEED
    login(client, app, 'admin')
    page = client.get('/admin/products/story/drink-balance').get_data(as_text=True)
    assert 'data-studio' in page and '리부 스튜디오' in page and 'preview?lang=ko&frame=1' in page
    assert 'Fall' not in client.get('/admin/products/story/drink-balance/preview?lang=en').get_data(as_text=True)
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    for name in ('HIGGSFIELD_API_KEY_ID', 'HIGGSFIELD_API_KEY_SECRET', 'HF_KEY'): monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('HIGGSFIELD_API_KEY', 'kid:secret')
    draft = json.loads(json.dumps(SEED['drink-balance']))
    W = 'src:product_image/web/'
    draft['images'] = {'hero': W + 'drink-balance-box3.webp', 'occasions': '', 'closing': 'src:/etc/passwd', 'sections': [W + 'drink-balance-box3.webp']}
    draft['en']['hero']['headline'] = 'Fall birthday? Bring the bottle.'
    bad = json.loads(json.dumps(draft)); bad['en']['hero']['headline'] = 'Beat the hangover'
    plan = dict(slot='hero', source_ref=W + 'drink-balance-box3.webp', provider='higgsfield', size='portrait', plan_ko='병은 그대로, 네온 생일 테이블 배경.', plan_en='Bottle unchanged, neon birthday table.', prompt='Product bottles on a neon birthday table, confetti, no text', label='Birthday hero')
    def call(name, args): return {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'c', 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}]}
    replies = [call('save_draft', {'content': bad}), call('save_draft', {'content': draft}), call('propose_image', plan), {'role': 'assistant', 'content': '저장했고 히어로 이미지 수정안을 만들었어요.'}]
    sent, hf = [], []
    def openai(request, timeout):
        sent.append(json.loads(request.data))
        return _io.BytesIO(json.dumps({'choices': [{'message': replies.pop(0)}]}).encode())
    def higgs(request, timeout):
        u = request.full_url
        if u.startswith('https://api.openai.com'): return openai(request, timeout)
        hf.append((request.get_method(), u))
        if '/estimate/' in u: return _io.BytesIO(b'{"usd": "0.084"}')
        if 'generate-upload-url' in u: return _io.BytesIO(json.dumps({'public_url': 'https://cdn.example/ref.png', 'upload_url': 'https://s3.example/put', 'upload_headers': {'Content-Type': 'image/png'}}).encode())
        if u == 'https://s3.example/put': return _io.BytesIO(b'')
        if u.endswith('/higgsfield/ads-studio/v1.0'):
            body = json.loads(request.data); assert body['image_urls'] == ['https://cdn.example/ref.png'] and body['aspect_ratio'] == '2:3'
            return _io.BytesIO(b'{"status": "queued", "request_id": "r1", "status_url": "https://api.higgsfield.ai/requests/r1/status"}')
        if u.endswith('/requests/r1/status'): return _io.BytesIO(b'{"status": "completed", "images": [{"url": "https://cdn.example/out.png"}]}')
        if u == 'https://cdn.example/out.png': return _io.BytesIO(_png_bytes())
        raise AssertionError(u)
    monkeypatch.setattr('urllib.request.urlopen', higgs)  # one shared urllib: route by host
    headers = {'X-CSRFToken': token(client, '/admin/products/story/drink-balance')}
    body = client.post('/admin/products/story/drink-balance/chat', json={'messages': [{'role': 'user', 'content': '생일파티 메인으로 알아서 해줘'}]}, headers=headers).get_json()
    system = sent[0]['messages'][0]['content']
    assert '리부 스튜디오' in system and '파티·술자리 필수품' in system and 'Higgsfield 연결됨' in system and 'Sucralose' in system
    assert json.loads(sent[1]['messages'][-1]['content'])['status'] == 'saved_with_problems'   # the hangover headline must be fixed
    assert [e['type'] for e in body['events']] == ['draft', 'draft', 'image'] and body['events'][2]['cost'].startswith('~$0.084')
    assert 'https://api.higgsfield.ai/higgsfield/ads-studio/v1.0' not in [u for _, u in hf]                 # proposal only, nothing generated
    with app.app_context():
        s = db.session.scalar(db.select(ProductStory).filter_by(slug='drink-balance'))
        assert s.draft['en']['hero']['headline'] == 'Fall birthday? Bring the bottle.' and s.draft['images']['closing'] == ''
        assert s.content['en']['hero']['headline'] == 'Same small bottle. Zero Sugar.'          # live page unchanged
        im_id = db.session.scalar(db.select(StoryImage.id).filter_by(slug='drink-balance', status='proposed'))
    assert 'Fall birthday? Bring the bottle.' in client.get('/admin/products/story/drink-balance/preview?lang=en').get_data(as_text=True)
    r = client.post(f'/admin/products/story/drink-balance/images/{im_id}/allow', headers=dict(headers, Accept='application/json')).get_json()
    assert r['status'] == 'running'
    client.get('/admin/products/story/drink-balance')                                           # the editor checks running jobs
    with app.app_context():
        im = db.session.get(StoryImage, im_id); assert im.status == 'ready' and im.data and im.provider == 'higgsfield'


def test_story_form_save_and_openai_image(client, app, monkeypatch):
    import json, base64
    from products.story import ProductStory, StoryImage
    login(client, app, 'admin')
    csrf = token(client, '/admin/products/story/jelly-balance')
    client.post('/admin/products/story/jelly-balance/notes', data={'csrf_token': csrf, 'notes': '체리 강조', 'photos': (_io.BytesIO(_png_bytes()), 'pic.png')}, content_type='multipart/form-data')
    with app.app_context(): up_id = db.session.scalar(db.select(StoryImage.id).filter_by(slug='jelly-balance', kind='upload'))
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    urls = []
    def openai(request, timeout):
        urls.append(request.full_url)
        if '/images/' in request.full_url: return _io.BytesIO(json.dumps({'data': [{'b64_json': base64.b64encode(_png_bytes()).decode()}]}).encode())
        content = json.dumps({'ko': '파우치는 그대로, 컨페티 배경.', 'en': 'Pouch unchanged, confetti.', 'prompt': 'Pouch on a party table, confetti, no text', 'size': 'portrait', 'label': 'Party'})
        return _io.BytesIO(json.dumps({'choices': [{'message': {'role': 'assistant', 'content': content}}]}).encode())
    monkeypatch.setattr('support.urllib.request.urlopen', openai)
    monkeypatch.setattr('products.story.urllib.request.urlopen', openai)
    client.post('/admin/products/story/jelly-balance/images/propose', data={'csrf_token': csrf, 'provider': 'openai', 'slot': 'hero', 'source': f'story:{up_id}', 'request': '파티 테이블'})
    assert not any('/images/' in u for u in urls)
    with app.app_context(): im_id = db.session.scalar(db.select(StoryImage.id).filter_by(slug='jelly-balance', kind='ai'))
    client.post(f'/admin/products/story/jelly-balance/images/{im_id}/allow', data={'csrf_token': csrf})
    assert urls[-1] == 'https://api.openai.com/v1/images/edits'
    form = {'csrf_token': csrf, 'publish': '1', 'image_hero': f'story:{im_id}'}
    for l, h in (('en', 'Cherry first. Party ready.'), ('ko', '체리 먼저. 파티 준비 끝.')):
        form.update({f'headline_{l}': h, f'title_{l}_0': 'One', f'body_{l}_0': 'Body.', f'faq_{l}': 'Q? || A.', f'roles_{l}': 'Pectin || Makes the chew.'})
    client.post('/admin/products/story/jelly-balance/save', data=dict(form, headline_en='Cures your hangover'))
    with app.app_context(): assert db.session.scalar(db.select(ProductStory).filter_by(slug='jelly-balance')).content['en']['hero']['headline'] != 'Cures your hangover'
    client.post('/admin/products/story/jelly-balance/save', data=form)
    client.post('/auth/logout', data={'csrf_token': token(client, '/auth/logout')})
    html = client.get('/products/jelly-balance').get_data(as_text=True)
    assert 'Cherry first. Party ready.' in html and f'/products/story-images/{im_id}.webp' in html
    assert client.get(f'/products/story-images/{im_id}.webp').mimetype == 'image/webp'
    assert client.get(f'/products/story-images/{up_id}.webp').status_code == 404


def test_long_detail_image_on_product_page(client, app):
    html = client.get('/products/jelly-original').get_data(as_text=True)
    assert 'pd-long-img' in html and html.count('/images/story/jelly-original/en-') == 9
    assert client.get('/images/story/jelly-original/en-01.webp').status_code == 200
    client.post('/language', data={'language': 'ko', 'csrf_token': token(client, '/')})
    assert '/images/story/jelly-original/ko-01.webp' in client.get('/products/jelly-original').get_data(as_text=True)
    other = client.get('/products/drink-original').get_data(as_text=True)
    assert 'pd-long-img' not in other and 'class="pd-long"' in other  # products without a composed image keep the HTML page


def test_sample_inventory_import_files(client, app):
    """Every file in sample_imports/inventory behaves as its README says (01–06 apply, 11–20 change nothing)."""
    import os
    from shop.inventory import Inventory
    folder = os.path.join(os.path.dirname(__file__), '..', 'sample_imports', 'inventory')
    login(client, app, 'admin')
    def snapshot():
        with app.app_context():
            return {i.option_id: (i.on_hand, i.reorder_level) for i in db.session.scalars(db.select(Inventory))}
    modes = {'03': 'add', '04': 'add', '17': 'add'}
    for name in sorted(f for f in os.listdir(folder) if f[:2].isdigit()):
        before = snapshot()
        with open(os.path.join(folder, name), 'rb') as fh:
            page = client.post('/admin/inventory/upload', data={'csrf_token': token(client, '/admin/inventory'), 'mode': modes.get(name[:2], 'set'),
                                                                'file': (_io.BytesIO(fh.read()), name)}, content_type='multipart/form-data', follow_redirects=True).get_data(as_text=True)
        changed = snapshot() != before
        if name < '10':
            assert 'CSV applied' in page and changed, name
        else:
            assert 'CSV applied' not in page and not changed, name


def test_old_database_is_upgraded_on_start(tmp_path, monkeypatch):
    """Tables made by an older version of the code get their new columns and missing tables on start (README §32)."""
    import sqlite3
    path = tmp_path / 'old.db'
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE products_story (id INTEGER PRIMARY KEY, slug VARCHAR(80) NOT NULL UNIQUE, status VARCHAR(10) NOT NULL, content JSON NOT NULL, notes TEXT NOT NULL, updated_at DATETIME NOT NULL)")
    con.execute("INSERT INTO products_story (slug, status, content, notes, updated_at) VALUES ('jelly-original', 'draft', '{}', '', '2026-10-24 00:00:00')")
    con.execute("CREATE TABLE products_story_image (id INTEGER PRIMARY KEY, slug VARCHAR(80) NOT NULL, kind VARCHAR(10) NOT NULL, status VARCHAR(10) NOT NULL, label VARCHAR(120) NOT NULL, source VARCHAR(200) NOT NULL, request TEXT NOT NULL, plan JSON NOT NULL, prompt TEXT NOT NULL, size VARCHAR(12) NOT NULL, model VARCHAR(40) NOT NULL, error VARCHAR(300) NOT NULL, data BLOB, created_at DATETIME NOT NULL)")
    con.execute("INSERT INTO products_story_image (slug, kind, status, label, source, request, plan, prompt, size, model, error, created_at) VALUES ('jelly-original','upload','ready','x','','','{}','','square','','','2026-10-24 00:00:00')")
    con.commit(); con.close()
    create_app({'TESTING': True, 'SECRET_KEY': secrets.token_hex(32), 'SQLALCHEMY_DATABASE_URI': f'sqlite:///{path}'})
    con = sqlite3.connect(path)
    cols = lambda t: {r[1] for r in con.execute(f'pragma table_info({t})')}
    assert 'draft' in cols('products_story') and {'provider', 'slot', 'cost', 'job'} <= cols('products_story_image')
    assert con.execute('select provider, cost from products_story_image').fetchone() == ('', '')   # old rows get safe values
    assert cols('admin_ai_draft') and cols('admin_assistant_upload') and cols('support_chat_question')


def test_higgsfield_combined_key_from_env(monkeypatch):
    from support import higgsfield
    for n in ('HIGGSFIELD_API_KEY_ID', 'HIGGSFIELD_API_KEY_SECRET', 'HF_KEY'): monkeypatch.delenv(n, raising=False)
    monkeypatch.setenv('HIGGSFIELD_API_KEY', ' "4e07aaaa-bbbb-cccc-dddd-eeeeffff0000:sec:ret" ')
    assert higgsfield.credentials() == ('4e07aaaa-bbbb-cccc-dddd-eeeeffff0000', 'sec:ret')


def test_spec_sheet_2026_10_25(client):
    """README §33: no 'patented', 10 jellies per pouch, Zero Sugar always with 'Not a low calorie food'."""
    import json
    from products.ingredient_roles import role
    from products.spec_fixes import fix
    from products.story_seed import SEED
    items = json.load(open('products/data/products.json'))
    for p in items:
        d = p['details']; blob = json.dumps(d)
        assert 'patent' not in blob.lower() and 'carnauba' not in blob.lower() and 'sorbate' not in blob.lower()
        if p['line'] == 'Jelly': assert '10' in p['pack']
        if p['is_balance']: assert 'Not a low calorie food' in d['facts']
        assert d['confirmed']  # confirmed by admin 2026-10-26
    seed = json.dumps(SEED, ensure_ascii=False)
    assert 'patent' not in seed and '특허' not in seed and 'Low Calorie' not in seed
    assert fix(SEED) == SEED
    assert 'patent' not in role('A-HAT', 'en') and '특허' not in role('A-HAT', 'ko')
    assert 'Not a low calorie food' in fix({'h': ['Zero Sugar']})['h'][0]
    assert fix('Zero Sugar version') == 'Zero Sugar version'  # only whole highlight chips change
    page = client.get('/products/jelly-balance').get_data(as_text=True)
    assert 'patented' not in page and 'Not a low calorie food' in page


# ---------- README §34: workspace upload, gallery photos, automatic long page ----------
def test_workspace_upload_and_forced_draft_update(client, app, monkeypatch):
    login(client, app, 'admin')
    h = {'X-CSRFToken': token(client, '/admin/ai/product')}
    page = client.get('/admin/ai/product').get_data(as_text=True)
    assert 'upload-image.js' in page and '상세페이지를 자동으로' in page
    # iPhone-style JPEG (MPO) and big photos are accepted; the photo lands in the draft right away
    from PIL import Image
    buf = _io.BytesIO(); Image.new('RGB', (2400, 1800), (200, 80, 20)).save(buf, 'JPEG'); buf.seek(0)
    up = client.post('/admin/ai/product/upload', data={'image': (buf, 'IMG_0001.JPG')}, headers=h, content_type='multipart/form-data')
    body = up.get_json()
    assert up.status_code == 200 and body['state']['fields']['image_id'] == body['id'] and body['state']['image']
    bad = client.post('/admin/ai/product/upload', data={'image': (_io.BytesIO(b'not an image'), 'x.heic')}, headers=h, content_type='multipart/form-data')
    assert bad.status_code == 400 and bad.get_json()['error']
    expired = client.post('/admin/ai/product/upload', data={'image': (_png(), 'p.png')}, headers={'X-CSRFToken': 'old'}, content_type='multipart/form-data')
    assert expired.status_code == 400 and 'expired' in expired.get_json()['error']
    big = client.post('/admin/ai/product/upload', data={'image': (_io.BytesIO(b'0' * (26 * 1024 * 1024)), 'big.png')}, headers=h, content_type='multipart/form-data')
    assert big.status_code == 413 and '25 MB' in big.get_json()['error']
    # the first AI round is always update_draft, so "젤리 오리지널" shows on the right
    monkeypatch.setenv('OPENAI_API_KEY', 'test-key')
    sent = []
    _ws_mock(monkeypatch, [_upd({'line': 'Jelly', 'version': 'original', 'badge': 'HALLOWEEN LIMITED'}), {'role': 'assistant', 'content': '이름을 정해요.'}], sent)
    st = client.post('/admin/ai/product/chat', json={'messages': [{'role': 'user', 'content': '할로윈 한정 라인을 젤리 오리지널 라인으로 등록하고 싶어'}]}, headers=h).get_json()['state']
    assert sent[0]['tool_choice'] == {'type': 'function', 'function': {'name': 'update_draft'}} and sent[1]['tool_choice'] == 'auto'
    assert st['fields']['line'] == 'Jelly' and st['fields']['version'] == 'original' and st['fields']['image_id'] == body['id']


def test_product_gallery_add_and_remove(client, app):
    from products.media import GalleryPhoto
    login(client, app, 'admin')
    page = client.get('/admin/products').get_data(as_text=True)
    assert 'PRODUCT PAGE PHOTOS' in page or '상품 페이지 사진' in page
    csrf = token(client, '/admin/products')
    r = client.post('/admin/products/gallery/add', data={'csrf_token': csrf, 'slug': 'jelly-original', 'label': 'Party scene', 'photo': [(_png(), 'a.png'), (_png(color=(0, 0, 255, 255)), 'b.png')]},
                    headers={'Accept': 'application/json'}, content_type='multipart/form-data')
    assert r.status_code == 200 and r.get_json()['ok']
    with app.app_context(): ids = [p.id for p in db.session.scalars(db.select(GalleryPhoto).filter_by(slug='jelly-original'))]
    assert len(ids) == 2
    detail = client.get('/products/jelly-original').get_data(as_text=True)
    assert f'/media/products/gallery/{ids[0]}.webp' in detail and 'Party scene' in detail
    assert client.get(f'/media/products/gallery/{ids[0]}.webp').mimetype == 'image/webp'
    assert f'/media/products/gallery/{ids[0]}.webp' not in client.get('/products/jelly-balance').get_data(as_text=True)
    client.post(f'/admin/products/gallery/{ids[0]}/delete', data={'csrf_token': csrf})
    assert f'/media/products/gallery/{ids[0]}.webp' not in client.get('/products/jelly-original').get_data(as_text=True)
    # an original gallery photo can be taken off and put back
    import json
    original = json.load(open('products/data/products.json'))[0]['images']['gallery'][-1]['src']
    client.post('/admin/products/gallery/toggle', data={'csrf_token': csrf, 'slug': 'jelly-original', 'src': original})
    from products.services import get_product
    with app.test_request_context(): assert original not in [g['src'] for g in get_product('jelly-original')['images']['gallery']]
    client.post('/admin/products/gallery/toggle', data={'csrf_token': csrf, 'slug': 'jelly-original', 'src': original})
    with app.test_request_context(): assert original in [g['src'] for g in get_product('jelly-original')['images']['gallery']]
    assert client.post('/admin/products/gallery/toggle', data={'csrf_token': csrf, 'slug': 'jelly-original', 'src': 'nope.webp'}).status_code == 400


def test_new_product_gets_automatic_long_page(client, app, monkeypatch):
    from products.autopage import AutoPage, LongPanel
    from products.story import StoryImage, ProductStory
    from support import higgsfield
    app.config.update(AUTOPAGE_SYNC=True, AUTOPAGE_POLL=0)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False); monkeypatch.delenv('OPEN_API_KEY', raising=False); monkeypatch.delenv('open_api_key', raising=False)
    monkeypatch.setattr(higgsfield, 'credentials', lambda: ('id', 'secret'))
    monkeypatch.setattr(higgsfield, 'bg_credits', lambda: 1.28)
    submitted = []
    def submit_model(model, prompt, aspect, urls=None):
        submitted.append((model, prompt, aspect)); return True, {'request_id': str(len(submitted)), 'status_url': f'https://api.higgsfield.ai/requests/{len(submitted)}/status'}
    monkeypatch.setattr(higgsfield, 'submit_model', submit_model)
    monkeypatch.setattr(higgsfield, 'status', lambda url: ('completed', 'https://cdn.example/bg.png'))
    monkeypatch.setattr(higgsfield, 'download', lambda url: _png((900, 1200), (40, 10, 60, 255)).getvalue())
    login(client, app, 'admin')
    page = client.get('/admin/products/new').get_data(as_text=True)
    assert 'auto_page_ai' in page and '6.4' in page  # credits shown before registering
    form = {'csrf_token': token(client, '/admin/products/new'), 'name': 'Reboot Jelly Halloween', 'line': 'Jelly', 'version': 'original',
            'badge': 'HALLOWEEN LIMITED', 'format': 'Shaped jelly', 'pack': 'One pouch', 'flavors': 'pumpkin, apple, grape',
            'opt_label_0': '1 Package', 'opt_price_0': '18.99', 'opt_count_0': '1', 'opt_stock_0': '50', 'auto_page': '1', 'auto_page_ai': '1'}
    client.post('/admin/products/new', data=dict(form, photo=(_png(), 'p.png')), content_type='multipart/form-data')
    slug = 'reboot-jelly-halloween'
    with app.app_context():
        job = db.session.scalar(db.select(AutoPage).filter_by(slug=slug))
        assert job.status == 'ready', job.note
        assert len(submitted) == 5 and all(m == higgsfield.BG_MODEL for m, _, _ in submitted) and 'HALLOWEEN' in submitted[0][1]
        assert all('no text' in p and 'no products' in p for _, p, _ in submitted)
        assert db.session.scalar(db.select(db.func.count(StoryImage.id)).filter_by(slug=slug, status='ready')) == 5
        assert db.session.scalar(db.select(ProductStory).filter_by(slug=slug)).status == 'published'
        panels = db.session.scalars(db.select(LongPanel).filter_by(slug=slug, lang='ko')).all()
        assert len(panels) >= 6 and job.credits.startswith('6.4')
    detail = client.get(f'/products/{slug}').get_data(as_text=True)
    assert '/products/long-panels/' in detail and 'pd-long-img' in detail
    first = re.search(r'/products/long-panels/(\d+)\.webp', detail)[1]
    assert client.get(f'/products/long-panels/{first}.webp').mimetype == 'image/webp'
    admin_page = client.get('/admin/products').get_data(as_text=True)
    assert 'Higgsfield: 6.4 credits' in admin_page
    # remake without new credits reuses the backgrounds
    client.post(f'/admin/products/{slug}/autopage', data={'csrf_token': token(client, '/admin/products')})
    assert len(submitted) == 5
    with app.app_context(): assert db.session.scalar(db.select(AutoPage.status).filter_by(slug=slug)) == 'ready'
