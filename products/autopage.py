"""Automatic long detail page for a newly registered product (README §34).

Register a product (form or "AI로 생성하기") -> in the background:
  1. copy   — OpenAI writes the long page in English + Korean (same rules as Rebu Studio); without a key a plain template is used
  2. images — Higgsfield makes 5 party backgrounds (no product, no text; ~1.28 credits each — shown before the admin registers)
  3. layout — the real product photo + exact text are laid over them (products/longpage.py), English and Korean panels
The page goes live under the product (ProductStory published + LongPanel images). Progress is shown on Admin › Products.
"""
import threading
import time
from datetime import datetime, timezone
from flask import current_app
from core.extensions import db

N_BACKGROUNDS = 5
POLL_SECONDS, POLL_LIMIT = 6, 600


class AutoPage(db.Model):
    __tablename__ = 'products_autopage'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), nullable=False, unique=True)
    status = db.Column(db.String(12), nullable=False, default='queued')   # queued · copy · images · layout · ready · failed · off
    use_ai_images = db.Column(db.Boolean, nullable=False, default=True)
    note = db.Column(db.String(300), nullable=False, default='')          # what happened (shown to the admin)
    credits = db.Column(db.String(40), nullable=False, default='')        # what it cost / will cost
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class LongPanel(db.Model):
    """One panel of a long detail image made in the app (Render's disk is reset on deploy, so the images live in the DB)."""
    __tablename__ = 'products_long_panel'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), nullable=False, index=True)
    lang = db.Column(db.String(2), nullable=False)
    idx = db.Column(db.Integer, nullable=False)
    data = db.Column(db.LargeBinary, nullable=False)
    version = db.Column(db.Integer, nullable=False, default=1)


def panel_urls(slug, lang):
    try:
        rows = db.session.execute(db.select(LongPanel.id, LongPanel.version).filter_by(slug=slug, lang=lang).order_by(LongPanel.idx)).all()
    except Exception:
        return []
    return [f'/products/long-panels/{i}.webp?v={v}' for i, v in rows]


def estimate():
    """(credits per page, credits per image) for the notice shown before registering."""
    from support import higgsfield
    per = higgsfield.bg_credits()
    return round(per * N_BACKGROUNDS, 2), per


def ai_images_ready():
    from support import higgsfield
    return bool(higgsfield.credentials())


def queue(slug, use_ai_images=True):
    """Mark a new product for an automatic page. Caller commits, then calls kick()."""
    job = db.session.scalar(db.select(AutoPage).filter_by(slug=slug)) or AutoPage(slug=slug)
    job.status, job.note, job.use_ai_images = 'queued', '', bool(use_ai_images)
    job.updated_at = datetime.now(timezone.utc)
    db.session.add(job)
    return job


def kick():
    """Start the queued jobs in a background thread (inline when AUTOPAGE_SYNC is set, e.g. tests)."""
    app = current_app._get_current_object()
    slugs = list(db.session.scalars(db.select(AutoPage.slug).filter_by(status='queued')))
    if not slugs or app.config.get('AUTOPAGE_OFF') or (app.testing and not app.config.get('AUTOPAGE_SYNC')): return
    if app.config.get('AUTOPAGE_SYNC'):
        for s in slugs: run(app, s)
        return
    threading.Thread(target=lambda: [run(app, s) for s in slugs], daemon=True).start()


def _set(job, status, note=''):
    job.status, job.note, job.updated_at = status, note[:300], datetime.now(timezone.utc)
    db.session.commit()


# ---------- 1. copy ----------
def fallback_content(product):
    """Plain bilingual page from the product facts (used when there is no OpenAI key or the AI copy fails)."""
    from products.story_seed import OCC, ING, FAQ_AGE
    from core.translations import KO
    kind = 'drink' if product.get('line') == 'Drink' else 'jelly'
    name = product['name'].replace('Reboot ', '')
    flv = product.get('flavors') or []
    tag = f" · {product['badge'].upper()}" if product.get('badge') else ''
    ko = lambda v: KO.get(v, v)
    page = lambda lang, hero, sections, highlights, how, faq, closing: {
        'hero': dict(zip(('kicker', 'headline', 'subhead'), hero)),
        'occasions': {'title': 'Made for every party' if lang == 'en' else '모든 파티의 필수품', 'items': [{'title': t, 'body': b} for t, b in OCC[kind][lang]]},
        'sections': [{'title': t, 'body': b} for t, b in sections if b], 'highlights': [h for h in highlights if h], 'ingredients': dict(ING[lang]),
        'how_to_enjoy': how, 'faq': [{'q': q, 'a': a} for q, a in faq], 'closing': dict(zip(('headline', 'subhead'), closing))}
    en = page('en', (f'THE PARTY ESSENTIAL{tag} · 21+', f'{name}. Party ready.', f"{product.get('format', '')}. {product.get('pack', '')}."),
              [('Made for the night', product.get('tagline') if product.get('tagline') not in (None, '', 'TBD') else f'{name} is the party essential from Korea.'),
               ('Flavors', ' · '.join(flv)), ('How it is sold', product.get('pack', ''))],
              [product.get('format', ''), ' · '.join(flv), 'Made by ALDICOM in Korea'],
              ['Pack it before you head out.', 'Share it with the table.', 'Keep one in your bag for later.'],
              [FAQ_AGE['en']], ("Don’t head out without it.", f"{product['name']}. The party essential from Korea."))
    kr = page('ko', (f'파티 필수품{tag} · 21+', f'{name}. 파티 준비 끝.', f"{ko(product.get('format', ''))}. {ko(product.get('pack', ''))}."),
              [('밤을 위한 준비물', product.get('tagline') if product.get('tagline') not in (None, '', 'TBD') else f'{name}, 한국에서 온 파티 필수품이에요.'),
               ('맛', ' · '.join(ko(f) for f in flv)), ('판매 단위', ko(product.get('pack', '')))],
              [ko(product.get('format', '')), ' · '.join(ko(f) for f in flv), '한국 알디콤에서 만들어요'],
              ['나가기 전에 챙기기.', '테이블에서 함께 나눠 보세요.', '나중을 위해 가방에 하나.'],
              [FAQ_AGE['ko']], ('이거 없이 나가지 마세요.', f"{product['name']}. 한국에서 온 파티 필수품."))
    return {'images': {}, 'en': en, 'ko': kr}


def make_copy(product):
    from support import key
    from products.story import generate_copy, clean_content
    notes = ('Newly registered product. ' + (f"Season / limited: {product['badge']}. " if product.get('badge') else '')
             + (f"Tagline idea: {product['tagline']}. " if product.get('tagline') not in (None, '', 'TBD') else '')
             + 'Write the full long page (hero, 3-4 occasions, 3 feature panels, highlights, how to enjoy, FAQ with 21+, closing).')
    if key():
        ok, content = generate_copy(product, notes)
        if ok: return content, 'AI copy'
    return clean_content(fallback_content(product), product), 'template copy (no OpenAI key or the AI copy failed)'


# ---------- 2. backgrounds ----------
def bg_prompts(product):
    flv = ', '.join(f.lower() for f in product.get('flavors') or []) or 'lime, lemon and cherry'
    theme = product.get('badge') or ''
    season = f' Subtle {theme} seasonal decorations.' if theme else ''
    base = (' Photorealistic, cinematic lighting, shallow depth of field. Black and neon look with lime-green and magenta accents.'
            ' No people, no faces, no hands, no text, no letters, no logos, no products, no bottles, no packages, no drinks being poured.' + season)
    return [
        ('3:4', 'Vertical night-party table close-up: glossy dark surface with neon reflections, confetti and sparklers, bokeh lights, empty space in the lower center.' + base),
        ('1:1', 'Empty nightclub bar counter at night with magenta and lime neon lights and a lit dance floor in the background, empty bar top in the foreground.' + base),
        ('1:1', 'Rooftop birthday party at dusk with a city skyline, warm string lights, a small birthday cake at the edge of an empty wooden table.' + base),
        ('1:1', f'Top-down close-up of fresh {flv} fruits filling the frame in bold vertical stripes, juicy and colorful.' + base),
        ('3:4', 'Black background with falling neon green and pink confetti and party streamers, glowing haze, empty dark center.' + base),
    ]


def make_backgrounds(product, job):
    """Submit the 5 Higgsfield backgrounds (StoryImage rows, visible in Rebu Studio too) and wait for them. Returns [bytes]."""
    from support import higgsfield
    from products.story import StoryImage, refresh_image
    slug = product['slug']
    rows = {im.slot: im for im in db.session.scalars(db.select(StoryImage).filter(StoryImage.slug == slug, StoryImage.slot.like('auto-bg-%')))}
    per = higgsfield.bg_credits()
    for n, (aspect, prompt) in enumerate(bg_prompts(product)):
        slot = f'auto-bg-{n}'
        im = rows.get(slot)
        if im and im.status in ('ready', 'running'): continue
        im = im or StoryImage(slug=slug, kind='ai', provider='higgsfield', slot=slot, label=f'Auto background {n + 1}', size='portrait' if aspect == '3:4' else 'square',
                              request='Automatic long detail page', plan={'ko': '자동 상세페이지 배경 (제품·글자 없음)', 'en': 'Automatic page background (no product, no text)'})
        im.prompt, im.model, im.cost = prompt, higgsfield.BG_MODEL, f'{per:g} credits (Higgsfield estimate)'
        ok, out = higgsfield.submit_model(higgsfield.BG_MODEL, prompt, aspect)
        if ok: im.status, im.job, im.error = 'running', out['status_url'], ''
        else: im.status, im.error = 'failed', str(out)[:300]
        db.session.add(im); db.session.commit()
        rows[slot] = im
    waited = 0
    while any(im.status == 'running' for im in rows.values()) and waited <= POLL_LIMIT:
        for im in rows.values():
            if im.status == 'running': refresh_image(im)
        if any(im.status == 'running' for im in rows.values()):
            time.sleep(current_app.config.get('AUTOPAGE_POLL', POLL_SECONDS)); waited += current_app.config.get('AUTOPAGE_POLL', POLL_SECONDS) or 1
    ready = [rows[f'auto-bg-{n}'] for n in range(N_BACKGROUNDS) if rows.get(f'auto-bg-{n}') is not None and rows[f'auto-bg-{n}'].status == 'ready']
    job.credits = f'{len(ready) * per:g} credits ({len(ready)} × {per:g})'
    return ready


# ---------- 3. layout ----------
def product_photo(product):
    """Bytes of the product's main photo (admin upload in the DB, or the file in /images)."""
    import os
    from products.media import ProductImage
    from products.services import load_original
    original = next((p for p in load_original() if p['slug'] == product['slug']), product)
    key = (original.get('images') or {}).get('main', '')
    row = db.session.scalar(db.select(ProductImage).filter_by(original=key)) if key else None
    if row: return row.data
    path = os.path.join(current_app.root_path, 'images', key) if key else ''
    return open(path, 'rb').read() if path and os.path.isfile(path) else None


def save_panels(slug, panels):
    db.session.execute(db.delete(LongPanel).where(LongPanel.slug == slug))
    v = int(time.time())
    for lang, items in panels.items():
        for i, data in enumerate(items): db.session.add(LongPanel(slug=slug, lang=lang, idx=i, data=data, version=v))
    db.session.commit()


def run(app, slug):
    from products.services import get_product
    from products.story import ProductStory, get_story
    from products.longpage import compose
    with app.app_context():
        job = db.session.scalar(db.select(AutoPage).filter_by(slug=slug))
        if not job or job.status not in ('queued',): return
        try:
            product = get_product(slug, include_hidden=True)
            if not product: return _set(job, 'failed', 'Product not found.')
            _set(job, 'copy', 'Writing the page (English + Korean)…')
            content, how = make_copy(product)
            from products.story import StoryImage
            if job.use_ai_images and ai_images_ready():
                _set(job, 'images', 'Higgsfield is making 5 party backgrounds…')
                backgrounds = make_backgrounds(product, job)
            else:  # remake without new credits: reuse backgrounds made earlier, if any
                backgrounds = sorted(db.session.scalars(db.select(StoryImage).filter(StoryImage.slug == slug, StoryImage.slot.like('auto-bg-%'), StoryImage.status == 'ready')), key=lambda im: im.slot)
                imgs = [f'story:{im.id}' for im in backgrounds]
                if imgs:
                    content['images'] = {'hero': imgs[0], 'occasions': imgs[1 % len(imgs)], 'closing': imgs[-1],
                                         'sections': [imgs[(i + 1) % len(imgs)] for i in range(len(content['en']['sections']))]}
            _set(job, 'layout', 'Laying out the long detail image…')
            story = get_story(slug) or ProductStory(slug=slug)
            story.content, story.status, story.draft = content, 'published', None
            story.notes = story.notes or 'Made automatically when the product was registered (README §34).'
            db.session.add(story); db.session.commit()
            panels = compose(product, content, [im.data for im in backgrounds], product_photo(product))
            save_panels(slug, panels)
            note = f"Done · {how} · {len(backgrounds)} AI background(s)" + ('' if backgrounds else ' (dark neon backgrounds used instead)')
            _set(job, 'ready', note)
        except Exception as e:  # never leave a job hanging
            db.session.rollback()
            job = db.session.scalar(db.select(AutoPage).filter_by(slug=slug))
            if job: _set(job, 'failed', f'{type(e).__name__}: {e}')
            app.logger.exception('Automatic detail page failed for %s', slug)
