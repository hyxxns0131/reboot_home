"""Long product detail pages (README §28): a tall, scroll-revealed page under each product page — hero, party occasions,
feature panels, lineup, ingredient analysis, how to enjoy, product info, FAQ, closing. English and Korean.

- ProductStory: bilingual content + which image goes in each slot. Published version (content) and working copy (draft).
- StoryImage: uploads and AI images. An AI image is first only a proposal (what will change, prompt, provider, cost).
  OpenAI or Higgsfield is called only after the admin presses "Allow & create".
"""
import base64
import json
import os
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from flask import abort, Response
from flask_login import current_user
from core.extensions import db
from products import bp

LANGS = ('en', 'ko')
MAX_SECTIONS = 4
SLOTS = ('hero', 'occasions', 'closing')          # single image slots; feature panels use sections[i]
IMAGE_SIZES = {'square': '1024x1024', 'portrait': '1024x1536', 'landscape': '1536x1024'}
ASPECTS = {'square': '1:1', 'portrait': '2:3', 'landscape': '3:2'}
COST_HINT = {'low': '~$0.01–0.02', 'medium': '~$0.04–0.07', 'high': '~$0.17–0.25'}  # per image, OpenAI price list (check the current page)
PROVIDERS = ('openai', 'higgsfield')


class ProductStory(db.Model):
    __tablename__ = 'products_story'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), nullable=False, unique=True)
    status = db.Column(db.String(10), nullable=False, default='draft')   # draft · published
    content = db.Column(db.JSON, nullable=False, default=dict)          # live version
    draft = db.Column(db.JSON)                                          # working copy; Publish copies it to content
    notes = db.Column(db.Text, nullable=False, default='')              # what the admin wrote for the AI
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class StoryImage(db.Model):
    __tablename__ = 'products_story_image'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), nullable=False, index=True)
    kind = db.Column(db.String(10), nullable=False, default='upload')    # upload · ai
    status = db.Column(db.String(10), nullable=False, default='ready')   # proposed · running · ready · cancelled · failed
    provider = db.Column(db.String(12), nullable=False, default='')      # openai · higgsfield
    label = db.Column(db.String(120), nullable=False, default='')
    slot = db.Column(db.String(20), nullable=False, default='')          # suggested place: hero · occasions · closing · section-1…
    source = db.Column(db.String(200), nullable=False, default='')       # reference photo (ref); empty = new image
    request = db.Column(db.Text, nullable=False, default='')             # what the admin asked for
    plan = db.Column(db.JSON, nullable=False, default=dict)              # {'ko': ..., 'en': ...} what will change
    prompt = db.Column(db.Text, nullable=False, default='')
    size = db.Column(db.String(12), nullable=False, default='portrait')  # square · portrait · landscape
    model = db.Column(db.String(60), nullable=False, default='')
    cost = db.Column(db.String(40), nullable=False, default='')          # what the admin was shown before allowing
    job = db.Column(db.String(300), nullable=False, default='')          # Higgsfield status URL while running
    error = db.Column(db.String(300), nullable=False, default='')
    data = db.Column(db.LargeBinary)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    @property
    def url(self):
        return f'/products/story-images/{self.id}.webp' if self.data else ''


def image_config():
    quality = (os.getenv('OPENAI_IMAGE_QUALITY') or 'medium').strip()
    quality = quality if quality in COST_HINT else 'medium'
    return dict(model=(os.getenv('OPENAI_IMAGE_MODEL') or 'gpt-image-1').strip(), quality=quality, cost=COST_HINT[quality])


def providers():
    """Which image providers have keys. {'openai': bool, 'higgsfield': bool}"""
    from support import key
    from support import higgsfield
    return {'openai': bool(key()), 'higgsfield': bool(higgsfield.credentials())}


# ---------- Image references ----------
def product_images(product):
    """Existing photos of a product (paths under /images) a page may use."""
    paths = [product['images'].get('main', '')] + [g['src'] for g in product['images'].get('gallery', [])] + [o.get('image', '') for o in product.get('options', [])]
    from products.story_seed import SEED
    seeded = SEED.get(product['slug'], {}).get('images', {})
    paths += [seeded.get(s, '') for s in SLOTS] + list(seeded.get('sections', []))
    return [p for p in dict.fromkeys(paths) if p]


def image_choices(product):
    """[(ref, label, url)] for the editor and the AI: site photos + this product's ready uploads / AI images."""
    from products.services import image_url
    out = [(f'src:{p}', p.rsplit('/', 1)[-1], image_url(p)) for p in product_images(product)]
    for im in db.session.scalars(db.select(StoryImage).filter_by(slug=product['slug'], status='ready').order_by(StoryImage.id.desc())):
        out.append((f'story:{im.id}', f"#{im.id} {'AI' if im.kind == 'ai' else 'upload'} · {im.label}"[:80], im.url))
    return out


def ref_url(product, ref):
    from products.services import image_url
    ref = str(ref or '')
    if ref.startswith('src:') and ref[4:] in product_images(product): return image_url(ref[4:])
    if ref.startswith('story:') and ref[6:].isdigit():
        im = db.session.get(StoryImage, int(ref[6:]))
        if im and im.slug == product['slug'] and im.status == 'ready': return im.url
    return ''


def ref_bytes(product, ref):
    """Raw bytes of an image reference (sent to the image APIs as the source / reference)."""
    if ref.startswith('story:') and ref[6:].isdigit():
        im = db.session.get(StoryImage, int(ref[6:]))
        return im.data if im and im.slug == product['slug'] and im.status == 'ready' else None
    if ref.startswith('src:') and ref[4:] in product_images(product):
        from flask import current_app
        from products.media import ProductImage
        override = db.session.scalar(db.select(ProductImage).filter_by(original=ref[4:]))
        if override: return override.data
        path = os.path.join(current_app.root_path, 'images', ref[4:])
        return open(path, 'rb').read() if os.path.isfile(path) else None
    return None


# ---------- Content ----------
def _s(v, n): return ' '.join(str(v or '').split())[:n]


def _items(v, n, size):
    return [_s(x, size) for x in (v or [])[:n] if _s(x, size)] if isinstance(v, list) else []


def clean_content(raw, product):
    """Keep known fields, trimmed; image refs must belong to this product. Raises ValueError if a language lacks a headline or panels.
    Older stories (headline / subhead at the top, images as a list) are read too."""
    if not isinstance(raw, dict): raise ValueError('not an object')
    imgs = raw.get('images') or {}
    if isinstance(imgs, list): imgs = {'sections': imgs}
    ok = lambda r: str(r or '') if ref_url(product, r) else ''
    images = {s: ok(imgs.get(s)) for s in SLOTS}
    images['sections'] = [ok(r) for r in (imgs.get('sections') or [])[:MAX_SECTIONS]]
    out = {'images': images}
    for lang in LANGS:
        c = raw.get(lang) if isinstance(raw.get(lang), dict) else {}
        hero = c.get('hero') if isinstance(c.get('hero'), dict) else {'headline': c.get('headline'), 'subhead': c.get('subhead')}
        occ = c.get('occasions') if isinstance(c.get('occasions'), dict) else {}
        ing = c.get('ingredients') if isinstance(c.get('ingredients'), dict) else {}
        clo = c.get('closing') if isinstance(c.get('closing'), dict) else {}
        pairs = lambda v, a, b, n, sa, sb: [{a: _s(x.get(a), sa), b: _s(x.get(b), sb)} for x in (v or [])[:n] if isinstance(x, dict) and _s(x.get(a), sa) and _s(x.get(b), sb)]
        out[lang] = dict(
            hero=dict(kicker=_s(hero.get('kicker'), 60), headline=_s(hero.get('headline'), 90), subhead=_s(hero.get('subhead'), 240)),
            occasions=dict(title=_s(occ.get('title'), 60), items=pairs(occ.get('items'), 'title', 'body', 4, 50, 200)),
            sections=pairs(c.get('sections'), 'title', 'body', MAX_SECTIONS, 70, 600),
            highlights=_items(c.get('highlights'), 6, 70),
            ingredients=dict(title=_s(ing.get('title'), 50), intro=_s(ing.get('intro'), 300), note=_s(ing.get('note'), 200),
                             roles={_s(k, 120): _s(v, 200) for k, v in list((ing.get('roles') or {}).items())[:20] if _s(k, 120) and _s(v, 200)} if isinstance(ing.get('roles'), dict) else {}),
            how_to_enjoy=_items(c.get('how_to_enjoy'), 4, 140),
            faq=pairs(c.get('faq'), 'q', 'a', 5, 120, 300),
            closing=dict(headline=_s(clo.get('headline'), 90), subhead=_s(clo.get('subhead'), 200)))
        if not out[lang]['hero']['headline'] or not out[lang]['sections']:
            raise ValueError(f'{lang}: a headline and at least one panel are needed')
    n = max(len(out['en']['sections']), len(out['ko']['sections']))
    out['images']['sections'] = (out['images']['sections'] + [''] * MAX_SECTIONS)[:n]
    return out


def texts(content):
    """Every visible line (for the compliance check)."""
    for lang in LANGS:
        c = content.get(lang, {})
        yield from c.get('hero', {}).values()
        occ = c.get('occasions', {}); yield occ.get('title', '')
        for x in occ.get('items', []): yield from (x['title'], x['body'])
        for s in c.get('sections', []): yield from (s['title'], s['body'])
        yield from c.get('highlights', []); yield from c.get('how_to_enjoy', [])
        ing = c.get('ingredients', {}); yield from (ing.get('title', ''), ing.get('intro', ''), ing.get('note', '')); yield from ing.get('roles', {}).values()
        for f in c.get('faq', []): yield from (f['q'], f['a'])
        yield from c.get('closing', {}).values()


def compliance(content):
    """Dashboard compliance rules on every line. Returns (ok, [(verdict, codes, text)]). REVIEW lines (ingredient names) may publish."""
    from support.guard import review, STOP
    problems = []
    for t in texts(content):
        if not t: continue
        r = review(t)
        if r['verdict'] != 'PASS': problems.append((r['verdict'], ','.join(r['codes']), t))
    return not any(v in STOP for v, _, _ in problems), problems


def get_story(slug):
    return db.session.scalar(db.select(ProductStory).filter_by(slug=slug))


def ingredient_rows(product, content_lang, lang, admin=False):
    """The ingredient analysis: every listed ingredient with its role. Before the list is confirmed (§26) shoppers see only
    the key ingredients; admins see all, marked as a preview."""
    from products.ingredient_roles import role, is_key, ROLES
    d = product.get('details') or {}
    names = list(d.get('ingredients') or [])
    confirmed = bool(d.get('confirmed'))
    custom = content_lang.get('ingredients', {}).get('roles', {})
    rows = [{'name': 'A-HAT', 'role': role('a-hat', lang), 'key': True}]
    for n in names:
        if confirmed or admin or is_key(n):
            rows.append({'name': n, 'role': custom.get(n) or role(n, lang), 'key': is_key(n)})
    if not names:  # products added by admins without a list: key ingredients only
        rows.append({'name': 'Hovenia dulcis (Oriental raisin tree) fruit', 'role': role('hovenia', lang), 'key': True})
    return dict(rows=rows, confirmed=confirmed, preview=admin and not confirmed, sweetened_with=d.get('sweetened_with', '') if confirmed or admin else '')


def story_for(product, lang, admin=False, content=None):
    """What the long page shows (published content, or a given draft for the admin preview), or None."""
    if content is None:
        try: story = get_story(product['slug'])
        except Exception: return None
        if not story or story.status != 'published': return None
        content = story.content
    c = content.get(lang) or content.get('en')
    if not c or 'hero' not in c: return None
    imgs = content.get('images') or {}
    url = lambda r: ref_url(product, r) if r else ''
    sections = [dict(s, image=url(imgs.get('sections', [])[i]) if i < len(imgs.get('sections', [])) else '') for i, s in enumerate(c['sections'])]
    return dict(c, sections=sections, hero_image=url(imgs.get('hero')), occasions_image=url(imgs.get('occasions')),
                closing_image=url(imgs.get('closing')), ingredient_table=ingredient_rows(product, c, lang, admin))


@bp.get('/long-panels/<int:panel_id>.webp')
def long_panel(panel_id):
    from products.autopage import LongPanel
    row = db.session.get(LongPanel, panel_id) or abort(404)
    resp = Response(row.data, mimetype='image/webp')
    resp.direct_passthrough = True
    resp.headers['Cache-Control'] = 'public, max-age=31536000, immutable'  # URL carries ?v=version
    return resp


@bp.record_once
def register(state):
    def product_story(product):
        from core.i18n import language
        admin = current_user.is_authenticated and current_user.role == 'admin'
        return story_for(product, 'ko' if language() == 'ko' else 'en', admin)
    state.app.jinja_env.globals['product_story'] = product_story

    def product_long_image(product):
        from core.i18n import language
        return long_image(product['slug'], 'ko' if language() == 'ko' else 'en')
    state.app.jinja_env.globals['product_long_image'] = product_long_image


@bp.get('/story-images/<int:image_id>.webp')
def story_image(image_id):
    """Uploaded / AI images. Shoppers see only images used by a published page; admins see all."""
    im = db.session.get(StoryImage, image_id)
    if not im or not im.data: abort(404)
    is_admin = current_user.is_authenticated and current_user.role == 'admin'
    if not is_admin:
        story = get_story(im.slug)
        used = json.dumps((story.content or {}).get('images', {})) if story and story.status == 'published' else ''
        if f'"story:{im.id}"' not in used: abort(404)
    return Response(im.data, mimetype='image/webp', headers={'Cache-Control': 'public, max-age=3600' if not is_admin else 'private, no-store'})


def apply_spec_fixes(story):
    """Swap exact old launch sentences for the 2026-10-25 spec-sheet wording (README §33). Admin-written text is left alone."""
    from products.spec_fixes import fix
    new = fix(story.content or {})
    if new != story.content: story.content = new
    if story.draft:
        d = fix(story.draft)
        if d != story.draft: story.draft = d


def seed_stories():
    """Published long pages for the launch products, once. Older short stories (no hero) are upgraded; edited pages are never overwritten."""
    from products.story_seed import SEED
    from products.services import get_all_products
    products = {p['slug']: p for p in get_all_products(include_hidden=True)}
    for slug, raw in SEED.items():
        if slug not in products: continue
        story = get_story(slug)
        if story and 'hero' in (story.content.get('en') or {}):
            apply_spec_fixes(story); continue
        imgs = raw['images']
        content = clean_content(dict(raw, images={**{s: f'src:{imgs[s]}' for s in SLOTS}, 'sections': [f'src:{p}' for p in imgs['sections']]}), products[slug])
        if story: story.content, story.status, story.draft = content, 'published', None
        else: db.session.add(ProductStory(slug=slug, status='published', content=content, notes='Written for launch: the party essential (README §28).'))


# ---------- AI: copy ----------
SCHEMA_NOTE = """JSON shape of a page (both languages, same meaning; "images" refs only from the list given to you):
{"images": {"hero": "<ref>", "occasions": "<ref>", "closing": "<ref>", "sections": ["<ref per panel>"]},
 "en": {"hero": {"kicker": "<= 40 chars, e.g. THE PARTY ESSENTIAL · 21+", "headline": "<= 80", "subhead": "<= 200"},
        "occasions": {"title": "...", "items": [{"title": "<= 40", "body": "1 sentence"}]},      # 3-4 party moments
        "sections": [{"title": "<= 60", "body": "2-3 sentences"}],                                # 2-4 feature panels
        "highlights": ["3-5 short facts"],
        "ingredients": {"title": "...", "intro": "1-2 sentences", "note": "where the full list is", "roles": {"<exact ingredient name>": "neutral role"}},
        "how_to_enjoy": ["2-3 short party-kit lines"], "faq": [{"q": "...", "a": "..."}],       # 2-4 FAQ, include one saying 21+
        "closing": {"headline": "<= 80", "subhead": "<= 160"}},
 "ko": { same keys in Korean }}"""

COPY_RULES = """Positioning: Reboot is THE PARTY ESSENTIAL for adults 21+ — something you pack for nights out, birthdays, club and bar nights,
house parties and tailgates. Fun, bold, neon, Korean-brand energy.
Hard rules (a compliance checker rejects the page otherwise):
- No health or medical claims at all. Never use: hangover, hungover, morning after, cure, prevent, relieve, relief, remedy, treat, heal,
  detox, toxin, sober, liver, intoxication, guaranteed, clinically proven, FDA approved, miracle; Korean: 숙취, 치료, 예방, 완화, 해독, 간 건강, 효과 보장.
- Never encourage drinking alcohol or drinking more ("drink more", "drink all night", "party harder", "keep drinking", "as much as you want").
  Party, nights out, toasts and celebrations are fine; the product itself is never presented as letting people drink more.
- No ingredient hype ("packed with", "rich in", 듬뿍, 가득, 고함량) and no reviews/ratings/testimonials. Adults 21+ only; nothing that appeals to minors.
- Ingredient roles describe what an ingredient is or does in the recipe (taste, texture, sweetness, color, freshness) — never an effect on the body.
- Only state facts given to you. Jelly is sold only as a line package (all flavors in one pouch), never by single flavor or piece."""

COPY_SYSTEM = ('You write the long, scroll-down detail page under a product page on the official US website of Reboot by ALDICOM '
               '(a Korean company\'s US-only line). Write natural US English ("en") and natural Korean ("ko") with the same meaning.\n'
               + COPY_RULES + '\n\nReturn one JSON object.\n' + SCHEMA_NOTE)


def product_facts(product):
    d = product.get('details') or {}
    opts = '; '.join(f"{o['label']} ${o['price_usd']:.2f}" for o in product['options'])
    return (f"Name: {product['name']}\nLine: {product.get('line')} · {'Balance (Zero Sugar)' if product.get('is_balance') else 'Original'}\n"
            f"Format: {product.get('format')}\nPack: {product.get('pack')}\nVolume: {product.get('volume', '-')}\nFlavors: {', '.join(product.get('flavors', []))}\n"
            f"Options (USD): {opts}\nMade by ALDICOM, Product of Korea. Made with A-HAT (ALDICOM's blend of Hovenia dulcis fruit extract and Lactobacillus fermentum — never call it 'patented' in copy). Jelly pouch = 10 individually wrapped jellies. Balance: every 'Zero Sugar' mention must sit next to 'Not a low calorie food'; never say 'Low Calorie' or give calorie/sugar numbers for Original.\n"
            f"Ingredient list ({'confirmed' if d.get('confirmed') else 'NOT confirmed yet — shoppers see only the key ingredients'}): {'; '.join(d.get('ingredients') or []) or '(none given)'}\n"
            f"Sweetened with: {d.get('sweetened_with') or '-'}\nFacts: {'; '.join(d.get('facts') or [])}")


def notes_and_images(product, notes):
    choices = image_choices(product)
    user = (f"PRODUCT FACTS\n{product_facts(product)}\n\nADMIN NOTES (may be rough, any language)\n{notes or '(none)'}\n\n"
            "IMAGES YOU MAY USE (ref — label)\n" + '\n'.join(f'{r} — {l}' for r, l, _ in choices))
    parts = [{'type': 'text', 'text': user}]
    for im in db.session.scalars(db.select(StoryImage).filter_by(slug=product['slug'], status='ready', kind='upload').order_by(StoryImage.id.desc()).limit(3)):
        parts += [{'type': 'text', 'text': f'Photo story:{im.id}'},
                  {'type': 'image_url', 'image_url': {'url': 'data:image/webp;base64,' + base64.b64encode(im.data).decode(), 'detail': 'low'}}]
    return parts


def generate_copy(product, notes):
    """One-click draft. (True, content) or (False, reason). Rewrites once when the compliance check stops a line."""
    from support import openai_request
    messages = [{'role': 'system', 'content': COPY_SYSTEM}, {'role': 'user', 'content': notes_and_images(product, notes)}]
    for attempt in range(2):
        ok, message = openai_request({'messages': messages, 'response_format': {'type': 'json_object'}, 'max_completion_tokens': 3500}, timeout=90)
        if not ok: return False, message
        try:
            content = clean_content(json.loads(message.get('content') or ''), product)
        except (ValueError, TypeError, AttributeError) as e:
            return False, f'The AI answer could not be used ({e}). Please try again.'
        passed, problems = compliance(content)
        if passed: return True, content
        messages += [{'role': 'assistant', 'content': message.get('content') or ''},
                     {'role': 'user', 'content': 'The compliance checker stopped these lines. Rewrite the whole JSON without them or any variant: ' +
                      ' | '.join(f'[{v} {c}] {t}' for v, c, t in problems if v in ('REVISE', 'BLOCK'))}]
    return False, 'The AI copy still broke the compliance rules after one rewrite. Add clearer notes or edit by hand.'


# ---------- AI: images (proposal first; created only after the admin allows it) ----------
PLAN_SYSTEM = """You plan one image panel for the long detail page of a Reboot product (US website; adults 21+; Korean brand ALDICOM;
black & neon look with a lime-green accent; positioning: the party essential). The admin, a Korean marketer, describes what they want.
Return JSON: {"ko": "2-4 Korean sentences: exactly what will be made or changed, and what stays the same (the real product, its label and shape stay unchanged)",
"en": "the same in English", "prompt": "a precise English prompt for the image model", "size": "square | portrait | landscape", "label": "short English label"}
Prompt rules: keep the real product, label and package exactly as in the reference; party / nightlife mood is fine (neon lights, confetti,
friends' hands, tables, club or rooftop settings); no faces that look under 21; nobody drinking heavily or passed out; no pouring shots;
no medical, hospital or before/after imagery; no words in the image (the page adds its own text); no other brands' logos."""


def cost_for(provider, prompt, size, with_image):
    if provider == 'higgsfield':
        from support import higgsfield
        est = higgsfield.estimate(prompt, ASPECTS.get(size, '2:3'), with_image)
        return f'{est} (Higgsfield estimate)' if est else '~$0.08 (Higgsfield list price, estimate unavailable)'
    cfg = image_config()
    return f"{cfg['cost']} (OpenAI {cfg['quality']})"


def higgsfield_model():
    from support import higgsfield
    return higgsfield.model()


def add_proposal(product, provider, source_ref, request_text, plan_ko, plan_en, prompt, size, label, slot=''):
    """Store a checked proposal. Returns (True, StoryImage) or (False, reason). Nothing is generated or paid here."""
    from support.guard import review, STOP
    if provider not in PROVIDERS: return False, 'Choose OpenAI or Higgsfield.'
    if not providers()[provider]: return False, f'The {provider} API key is not set (Admin › Settings › API connections).'
    if source_ref and not ref_url(product, source_ref): return False, 'Choose one of this product’s photos as the reference.'
    prompt = _s(prompt, 1500)
    if not prompt or not _s(plan_ko, 600): return False, 'The plan is empty.'
    check = review(prompt)
    if check['verdict'] in STOP:
        return False, f"The image prompt uses words the compliance rules stop ({', '.join(check['codes'])}). Rephrase it."
    size = size if size in IMAGE_SIZES else 'portrait'
    im = StoryImage(slug=product['slug'], kind='ai', status='proposed', provider=provider, label=_s(label, 120) or 'AI panel', slot=_s(slot, 20),
                    source=source_ref or '', request=_s(request_text, 800), plan={'ko': _s(plan_ko, 600), 'en': _s(plan_en, 600)}, prompt=prompt, size=size,
                    model=image_config()['model'] if provider == 'openai' else higgsfield_model(),
                    cost=cost_for(provider, prompt, size, bool(source_ref)))
    db.session.add(im); db.session.commit()
    return True, im


def propose_image(product, source_ref, request_text, provider='openai', slot=''):
    """From the image form: the AI writes the plan first. (True, StoryImage) or (False, reason)."""
    from support import call_openai
    request_text = _s(request_text, 800)
    if not request_text: return False, 'Describe the image you want.'
    user = f"Product: {product['name']} ({product.get('format')}). Reference photo: {source_ref or 'none — create a new image'}. Slot: {slot or 'any'}.\nAdmin request: {request_text}"
    ok, text = call_openai(PLAN_SYSTEM, [{'role': 'user', 'content': user}], max_tokens=700, json_mode=True)
    if not ok: return False, text
    try: plan = json.loads(text); plan['prompt']; plan['ko']
    except (ValueError, KeyError, TypeError): return False, 'The AI plan could not be read. Please try again.'
    return add_proposal(product, provider, source_ref, request_text, plan.get('ko'), plan.get('en'), plan.get('prompt'), plan.get('size'), plan.get('label'), slot)


def _multipart(fields, files):
    boundary = uuid.uuid4().hex
    body = b''
    for k, v in fields.items():
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
    for k, (name, data, mime) in files.items():
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"; filename="{name}"\r\nContent-Type: {mime}\r\n\r\n'.encode() + data + b'\r\n'
    return body + f'--{boundary}--\r\n'.encode(), f'multipart/form-data; boundary={boundary}'


def _png(data):
    from PIL import Image
    import io
    out = io.BytesIO(); Image.open(io.BytesIO(data)).convert('RGBA').save(out, 'PNG'); return out.getvalue()


def _openai_image(product, im):
    from support import key
    from products.media import to_webp
    cfg = image_config()
    fields = {'model': im.model or cfg['model'], 'prompt': im.prompt, 'size': IMAGE_SIZES.get(im.size, '1024x1536'), 'quality': cfg['quality'], 'n': '1'}
    if im.source:
        raw = ref_bytes(product, im.source)
        if not raw: raise ValueError('The reference photo is no longer available.')
        body, ctype = _multipart(fields, {'image': ('source.png', _png(raw), 'image/png')}); url = 'https://api.openai.com/v1/images/edits'
    else:
        body, ctype = json.dumps(dict(fields, n=1)).encode(), 'application/json'; url = 'https://api.openai.com/v1/images/generations'
    req = urllib.request.Request(url, data=body, headers={'Authorization': f'Bearer {key()}', 'Content-Type': ctype})
    with urllib.request.urlopen(req, timeout=170) as r:
        return to_webp(base64.b64decode(json.load(r)['data'][0]['b64_json']))


def create_image(product, im):
    """Run an allowed proposal. OpenAI answers in one call; Higgsfield is queued and checked with refresh_image()."""
    from support import higgsfield
    from products.media import to_webp
    try:
        if im.provider == 'higgsfield':
            urls = []
            if im.source:
                raw = ref_bytes(product, im.source)
                if not raw: raise ValueError('The reference photo is no longer available.')
                ok, url = higgsfield.upload(_png(raw), 'image/png')
                if not ok: raise ValueError(url)
                urls = [url]
            ok, job = higgsfield.submit(im.prompt, urls, ASPECTS.get(im.size, '2:3'))
            if not ok: raise ValueError(job)
            im.status, im.job, im.error = 'running', job['status_url'], ''
        else:
            im.data = _openai_image(product, im); im.status, im.error = 'ready', ''
    except urllib.error.HTTPError as e:
        try: msg = json.loads(e.read().decode()).get('error', {}).get('message', '')
        except Exception: msg = ''
        im.status, im.error = 'failed', f'HTTP {e.code}: {msg}'[:300]
    except Exception as e:
        im.status, im.error = 'failed', (str(e) if isinstance(e, ValueError) else f'Image could not be created ({type(e).__name__}).')[:300]
    db.session.commit()
    return im.status in ('ready', 'running'), im.error or im.status


def refresh_image(im):
    """Check a running Higgsfield job once and save the image when it is done."""
    from support import higgsfield
    from products.media import to_webp
    if im.status != 'running' or not im.job: return im.status
    state, detail = higgsfield.status(im.job)
    if state == 'completed':
        try: im.data = to_webp(higgsfield.download(detail)); im.status, im.job = 'ready', ''
        except Exception as e: im.status, im.error = 'failed', f'Download failed ({type(e).__name__}).'
    elif state in ('failed', 'nsfw', 'canceled', 'error'):
        im.status, im.error = 'failed', f'Higgsfield: {state} {detail}'.strip()[:300]
    db.session.commit()
    return im.status


# ---------- Long detail image (README §31) ----------
def long_image(slug, lang):
    """Panel images of the composed long detail image, in order, or [] when there is none: panels made in the app for new
    products (README §34, in the DB) first, then files from scripts/compose_long_image.py. Korean falls back to English."""
    from flask import current_app
    from products.autopage import panel_urls
    for code in ([lang, 'en'] if lang != 'en' else ['en']):
        urls = panel_urls(slug, code)
        if urls: return urls
    folder = Path(current_app.root_path) / 'images' / 'story' / slug
    for code in ([lang, 'en'] if lang != 'en' else ['en']):
        files = sorted(folder.glob(f'{code}-[0-9][0-9].webp')) if folder.is_dir() else []
        if files:
            v = int(max(f.stat().st_mtime for f in files))
            return [f'/images/story/{slug}/{f.name}?v={v}' for f in files]
    return []
