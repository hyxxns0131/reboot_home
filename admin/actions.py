"""Create popups, creator links and products — one set of rules for the admin forms and the admin AI assistant (README §27).

Each build_* function only checks and prepares; nothing is added to the session until the caller decides to save,
so the assistant can check a request first ("dry run") and save it only after the admin presses Confirm.
Errors are ActionError with the same message the forms show.
"""
import re
from datetime import date
from decimal import Decimal
from core.extensions import db


class ActionError(ValueError):
    pass


def parse_day(value):
    if isinstance(value, date): return value
    return date.fromisoformat(value) if value else None


# ---------- Creator links ----------
def build_creator(f):
    """f: mapping with name, platform, discount, commission, code (optional), landing (optional). Returns an unsaved ReferralLink."""
    from admin.services import PLATFORMS
    from shop.models import ReferralLink
    from admin import landing_pages
    name = str(f.get('name', '')).strip(); platform = str(f.get('platform', ''))
    code = re.sub(r'[^A-Z0-9]', '', str(f.get('code', '') or '').upper())
    try: discount = int(f.get('discount', '')); commission = int(f.get('commission', ''))
    except (ValueError, TypeError): discount = commission = -1
    if not name or len(name) > 80 or platform not in PLATFORMS.values() or not 0 <= discount <= 50 or not 0 <= commission <= 50:
        raise ActionError('Enter a creator name, Instagram or TikTok, and discount/commission between 0 and 50%.')
    landing = str(f.get('landing', '') or '')
    if landing not in landing_pages(): landing = ''
    code = code or (re.sub(r'[^A-Z0-9]', '', name.upper())[:10] + str(discount))
    if not 3 <= len(code) <= 40 or db.session.scalar(db.select(ReferralLink).filter_by(code=code)):
        raise ActionError('That discount code is already used. Enter a different code.')
    return ReferralLink(code=code, influencer_name=name, platform=platform, discount_rate=Decimal(discount) / 100,
                        commission_rate=Decimal(commission) / 100, clicks=0, is_active=True, landing=landing)


# ---------- Popups ----------
def build_popup(p, f):
    """Check popup fields and copy them onto p (a Popup, new or existing). Image is handled by the caller."""
    from core.popups import PLACEMENTS, safe_link
    title = str(f.get('title', '')).strip(); body = str(f.get('body', '') or '').strip()
    label = str(f.get('button_label', '') or '').strip(); raw_link = str(f.get('button_link', '') or '').strip(); link = safe_link(raw_link)
    placement = f.get('placement') or 'home'
    try: starts, ends = parse_day(f.get('starts_on')), parse_day(f.get('ends_on'))
    except ValueError: raise ActionError('Enter valid dates.')
    if not 1 <= len(title) <= 80 or len(body) > 600 or len(label) > 30 or placement not in PLACEMENTS:
        raise ActionError('Popups need a title (up to 80 characters); text up to 600; button label up to 30.')
    if raw_link and not link:
        raise ActionError('Button links must be a page on this site (/products/...) or an https:// address.')
    if bool(label) != bool(link):
        raise ActionError('Fill in both the button label and the link, or leave both empty.')
    if starts and ends and ends < starts:
        raise ActionError('The end date must be on or after the start date.')
    p.title, p.body, p.button_label, p.button_link, p.placement, p.starts_on, p.ends_on = title, body, label, link, placement, starts, ends
    return p


# ---------- Products ----------
def build_product(f, has_photo):
    """Check the Add product form (or the assistant's fields in the same shape). Returns a plan for create_product()."""
    from products.custom import CustomProduct, INGREDIENTS, slugify
    from products.services import load_original
    from shop.models import Product, ProductOption
    name = ' '.join(str(f.get('name', '')).split()); line = f.get('line'); badge = ' '.join(str(f.get('badge', '') or '').split())[:30]
    fmt = str(f.get('format', '') or '').strip()[:120]; pack = str(f.get('pack', '') or '').strip()[:120]; volume = str(f.get('volume', '') or '').strip()[:20]
    tagline = str(f.get('tagline', '') or '').strip()[:120]
    flavors = [x.strip().title() for x in str(f.get('flavors', '') or '').split(',') if x.strip()][:6]
    if not 3 <= len(name) <= 80: raise ActionError('Enter a product name (3–80 characters).')
    if line not in ('Jelly', 'Drink'): raise ActionError('Choose Jelly or Drink.')
    if not fmt or not pack: raise ActionError('Describe the format and the pack.')
    if not flavors: raise ActionError('Enter at least one flavor (comma separated).')
    options = []
    for i in range(4):
        label = ' '.join(str(f.get(f'opt_label_{i}', '') or '').split())[:60]; price = str(f.get(f'opt_price_{i}', '') or '').strip()
        if not label and not price: continue
        try:
            price = Decimal(price).quantize(Decimal('.01')); count = int(f.get(f'opt_count_{i}') or 1); stock = int(f.get(f'opt_stock_{i}') or 0)
        except Exception: raise ActionError(f'Option {i+1}: check the price, pieces and stock.')
        if not label or not Decimal('0.50') <= price <= Decimal('999') or not 1 <= count <= 48 or not 0 <= stock <= 100000:
            raise ActionError(f'Option {i+1}: label, price $0.50–$999, pieces 1–48, stock 0–100,000.')
        options.append((label, price, count, stock))
    if not options: raise ActionError('Add at least one sales option with a price.')
    if not has_photo: raise ActionError('Add a product photo.')
    taken = {p['slug'] for p in load_original()} | set(db.session.scalars(db.select(Product.slug)))
    base = slugify(name); slug = base; n = 2
    while slug in taken: slug = f'{base}-{n}'; n += 1
    key = f'custom/{slug}/main.webp'
    used_skus = set(db.session.scalars(db.select(ProductOption.sku)))
    opts = []
    for label, price, count, stock in options:
        sku = f'{slug}-{slugify(label)}'[:90]; k = 2
        while sku in used_skus: sku = f'{slug}-{slugify(label)}-{k}'[:90]; k += 1
        used_skus.add(sku); opts.append(dict(sku=sku, label=label, unit_count=count, price_usd=float(price), image=key, stock=stock))
    order = 100 + db.session.scalar(db.select(db.func.count(CustomProduct.id)))
    data = dict(slug=slug, name=name, line=line, format=fmt, pack=pack, ingredients=INGREDIENTS, flavors=flavors,
                options=[{k: v for k, v in o.items() if k != 'stock'} for o in opts], images=dict(main=key, card=key, gallery=[]),
                is_balance=f.get('version') == 'balance', badge=badge, tagline=tagline or 'TBD', buy_links={}, order=order,
                image_dir='custom', variant=slug, color='#b1ff3b', price_is_sample=False, custom=True)
    if volume: data['volume'] = volume
    return dict(slug=slug, name=name, key=key, data=data, opts=opts, hidden=bool(f.get('hidden')))


def create_product(plan, image):
    """Save a checked product plan with its WEBP photo. Caller commits."""
    from products.custom import CustomProduct
    from products.media import ProductImage
    from shop.models import Product, ProductOption
    from shop.inventory import set_stock
    from rewards.services import record
    db.session.add(CustomProduct(slug=plan['slug'], data=plan['data']))
    db.session.add(ProductImage(slug=plan['slug'], original=plan['key'], data=image))
    product = Product(slug=plan['slug'], name=plan['name'], is_active=not plan['hidden']); db.session.add(product); db.session.flush()
    for o in plan['opts']:
        option = ProductOption(product_id=product.id, sku=o['sku'], label=o['label'], unit_count=o['unit_count'], price=Decimal(str(o['price_usd'])), is_active=True)
        db.session.add(option); db.session.flush()
        set_stock(option, on_hand=o['stock'], reorder_level=20, reason='manual', note='New product')
    record('product_created', {'product': plan['slug']})
    return product
