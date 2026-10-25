"""Admin "Detail pages" tab (README §28): the long scroll-down detail page of each product.
Chat with Rebu Studio (persona: admin/data/story_persona.md) or use the form; AI images only after the admin allows each one.
"""
import json
import time
from pathlib import Path
from flask import render_template, request, redirect, flash, abort, jsonify, session
from flask_login import current_user
from auth.decorators import admin_required
from core.extensions import db
from admin import bp
from products.story import (ProductStory, StoryImage, LANGS, MAX_SECTIONS, SLOTS, PROVIDERS, IMAGE_SIZES, clean_content, compliance, image_choices,
                            image_config, providers, generate_copy, propose_image, add_proposal, create_image, refresh_image, get_story, story_for, product_facts)

PERSONA_FILE = Path(__file__).parent / 'data' / 'story_persona.md'


def _product(slug):
    from products.services import get_all_products
    return next((p for p in get_all_products(include_hidden=True) if p['slug'] == slug), None) or abort(404)


def _story(slug):
    story = get_story(slug)
    if not story:
        story = ProductStory(slug=slug, status='draft', content={}); db.session.add(story); db.session.flush()
    return story


def _back(slug, anchor=''):
    return redirect(f'/admin/products/story/{slug}' + (f'#{anchor}' if anchor else ''))


def form_content():
    """Editor form -> content dict (before clean_content)."""
    f = request.form
    lines = lambda name, l: [x.strip() for x in f.get(f'{name}_{l}', '').splitlines() if x.strip()]
    out = {'images': {s: f.get(f'image_{s}', '') for s in SLOTS}}
    out['images']['sections'] = [f.get(f'image_section_{i}', '') for i in range(MAX_SECTIONS)]
    for l in LANGS:
        g = lambda k: f.get(f'{k}_{l}', '')
        out[l] = dict(
            hero=dict(kicker=g('kicker'), headline=g('headline'), subhead=g('subhead')),
            occasions=dict(title=g('occ_title'), items=[dict(title=f.get(f'occ_t_{l}_{i}', ''), body=f.get(f'occ_b_{l}_{i}', '')) for i in range(4)]),
            sections=[dict(title=f.get(f'title_{l}_{i}', ''), body=f.get(f'body_{l}_{i}', '')) for i in range(MAX_SECTIONS)],
            highlights=lines('highlights', l), how_to_enjoy=lines('how', l),
            ingredients=dict(title=g('ing_title'), intro=g('ing_intro'), note=g('ing_note'),
                             roles={n.strip(): r.strip() for n, _, r in (x.partition('||') for x in lines('roles', l)) if r.strip()}),
            faq=[dict(q=q.strip(), a=a.strip()) for q, _, a in (x.partition('||') for x in lines('faq', l))],
            closing=dict(headline=g('close_headline'), subhead=g('close_subhead')))
    return out


@bp.get('/products/story')
@admin_required
def story_list():
    from products.services import get_all_products
    stories = {s.slug: s for s in db.session.scalars(db.select(ProductStory))}
    rows = [dict(p=p, story=stories.get(p['slug'])) for p in get_all_products(include_hidden=True)]
    return render_template('admin/story_list.html', title='Detail pages', rows=rows)


@bp.get('/products/story/<slug>')
@admin_required
def story_edit(slug):
    from support import chat_config
    product = _product(slug)
    story = get_story(slug)
    working = (story.draft or story.content) if story else {}
    images = db.session.scalars(db.select(StoryImage).filter_by(slug=slug).filter(StoryImage.status != 'cancelled').order_by(StoryImage.id.desc())).all()
    for im in images:
        if im.status == 'running': refresh_image(im)
    ok, problems = compliance(working) if working else (True, [])
    return render_template('admin/story_edit.html', title='Detail page', p=product, story=story, c=working, langs=LANGS, n=MAX_SECTIONS, slots=SLOTS,
                           choices=image_choices(product), images=images, problems=problems, passed=ok, config=chat_config(), provs=providers(),
                           image_cfg=image_config(), sizes=list(IMAGE_SIZES), unsaved=bool(story and story.draft and story.draft != story.content),
                           running=any(im.status == 'running' for im in images))


@bp.get('/products/story/<slug>/preview')
@admin_required
def story_preview(slug):
    """The long page as shoppers will see it, from the draft (or the live version), in one language. Has a PNG export button."""
    product = _product(slug)
    story = get_story(slug) or abort(404)
    lang = request.args.get('lang') if request.args.get('lang') in LANGS else 'en'
    which = (story.draft or story.content) if request.args.get('version') != 'live' else story.content
    return render_template('admin/story_preview.html', title='Detail page preview', p=product, story_data=story_for(product, lang, admin=False, content=which or {}), lang=lang)


@bp.post('/products/story/<slug>/notes')
@admin_required
def story_notes(slug):
    from products.media import to_webp
    product = _product(slug); story = _story(slug)
    story.notes = request.form.get('notes', '').strip()[:4000]
    added = 0
    for f in request.files.getlist('photos')[:6]:
        if not f or not f.filename: continue
        try: data = to_webp(f.read())
        except Exception as e:
            flash(str(e) if isinstance(e, ValueError) else f'{f.filename}: not a readable image (JPG, PNG or WEBP).', 'error'); continue
        db.session.add(StoryImage(slug=product['slug'], kind='upload', status='ready', label=f.filename[:120], data=data)); added += 1
    db.session.commit()
    flash(f'Notes saved. {added} photo(s) added.' if added else 'Notes saved.')
    return _back(slug, 'notes')


@bp.post('/products/story/<slug>/generate')
@admin_required
def story_generate(slug):
    product = _product(slug); story = _story(slug)
    db.session.commit()
    ok, result = generate_copy(product, story.notes)
    if not ok:
        flash(result, 'error'); return _back(slug, 'notes')
    story.draft = result; db.session.commit()
    flash('AI draft ready. Check the preview, edit anything, then Save and Publish.')
    return _back(slug, 'editor')


def save_draft(product, story, content, publish=False):
    """(saved, published, problems)"""
    from datetime import datetime, timezone
    from rewards.services import record
    story.draft = content
    ok, problems = compliance(content)
    published = publish and ok
    if published: story.content, story.status = content, 'published'
    story.updated_at = datetime.now(timezone.utc)
    record('story_published' if published else 'story_saved', {'product': product['slug']})
    db.session.commit()
    return True, published, problems


@bp.post('/products/story/<slug>/save')
@admin_required
def story_save(slug):
    product = _product(slug); story = _story(slug)
    try: content = clean_content(form_content(), product)
    except ValueError:
        flash('Each language needs a headline and at least one panel.', 'error'); return _back(slug, 'editor')
    publish = request.form.get('publish') == '1'
    _, published, problems = save_draft(product, story, content, publish)
    if publish and not published:
        flash('Saved as a draft. Fix the lines the compliance rules stop before publishing.', 'error')
    else:
        flash('Published. The detail page is live.' if published else 'Draft saved. Shoppers still see the published version.')
    return _back(slug, 'editor')


@bp.post('/products/story/<slug>/unpublish')
@admin_required
def story_unpublish(slug):
    story = get_story(slug) or abort(404)
    story.status = 'draft'; db.session.commit()
    flash('Hidden from the product page.')
    return _back(slug)


@bp.post('/products/story/<slug>/images/propose')
@admin_required
def story_image_propose(slug):
    product = _product(slug)
    ok, result = propose_image(product, request.form.get('source', ''), request.form.get('request', ''), request.form.get('provider', 'openai'), request.form.get('slot', ''))
    if not ok: flash(result, 'error')
    else: flash('Check the plan below. Nothing is created until you press Allow & create.')
    return _back(slug, 'images')


@bp.post('/products/story/<slug>/images/<int:image_id>/<decision>')
@admin_required
def story_image_decide(slug, image_id, decision):
    product = _product(slug)
    im = db.session.get(StoryImage, image_id)
    if not im or im.slug != slug: abort(404)
    wants_json = request.is_json or 'application/json' in request.headers.get('Accept', '')
    msg, ok = '', True
    if decision == 'cancel' and im.status in ('proposed', 'failed'):
        im.status = 'cancelled'; db.session.commit(); msg = 'Cancelled.'
    elif decision == 'allow' and im.status in ('proposed', 'failed'):
        from rewards.services import record
        record('story_image_allowed', {'product': slug, 'image': im.id, 'provider': im.provider, 'cost': im.cost})
        ok, detail = create_image(product, im)
        msg = ('Image created. Pick it for a slot in the editor.' if im.status == 'ready' else 'Sent to Higgsfield. This page checks it every few seconds.') if ok else detail
    elif decision == 'refresh' and im.status == 'running':
        refresh_image(im); msg = im.status
    elif decision == 'remove' and im.status == 'ready':
        im.status = 'cancelled'; db.session.commit(); msg = 'Removed from this product’s images.'
    else: abort(400)
    if wants_json: return jsonify(ok=ok, status=im.status, message=msg, url=im.url)
    flash(msg, 'message' if ok else 'error')
    return _back(slug, 'images')


# ---------- Rebu Studio: the detail-page chatbot ----------
def S(d=''): return {'type': 'string', 'description': d}


STUDIO_TOOLS = [
    {'type': 'function', 'function': {'name': 'save_draft', 'description': 'Save the WHOLE page (both languages) as the draft. Shoppers do not see it until the admin publishes.',
     'parameters': {'type': 'object', 'required': ['content'], 'properties': {'content': {'type': 'object', 'description': 'The full page JSON (shape in the system prompt).'}}}}},
    {'type': 'function', 'function': {'name': 'propose_image', 'description': 'Create an image PROPOSAL card. Nothing is generated or paid until the admin presses Allow & create.',
     'parameters': {'type': 'object', 'additionalProperties': False,
                    'required': ['slot', 'source_ref', 'provider', 'size', 'plan_ko', 'plan_en', 'prompt', 'label'],
                    'properties': {'slot': {'type': 'string', 'enum': ['hero', 'occasions', 'closing', 'section-1', 'section-2', 'section-3', 'section-4']},
                                   'source_ref': S('reference photo ref from the list, or "" for a new image'),
                                   'provider': {'type': 'string', 'enum': list(PROVIDERS)}, 'size': {'type': 'string', 'enum': list(IMAGE_SIZES)},
                                   'plan_ko': S('Korean: what will be made/changed and what stays the same'), 'plan_en': S('the same in English'),
                                   'prompt': S('English prompt for the image model; no text in the image'), 'label': S('short English label')}}}},
]


def studio_lang():
    return 'en' if session.get('lang_picked') and session.get('lang') == 'en' else 'ko'


def studio_prompt(product, story):
    from products.story import SCHEMA_NOTE, COPY_RULES
    provs = providers(); cfg = image_config()
    working = (story.draft or story.content) if story else {}
    state = [f"- 상품: {product['name']} (/products/{product['slug']})",
             f"- 게시 상태: {'게시됨' if story and story.status == 'published' else '게시 안 됨'}; 초안이 게시본과 {'다름' if story and story.draft and story.draft != story.content else '같음'}",
             f"- 이미지 제공자 키: OpenAI {'연결됨' if provs['openai'] else '없음'} (모델 {cfg['model']}, {cfg['quality']}, 1장 {cfg['cost']}), "
             f"Higgsfield {'연결됨' if provs['higgsfield'] else '없음'} (Ads Studio 기준 1장 약 $0.08, 카드에 실제 견적 표시)",
             '- 쓸 수 있는 이미지(ref — label):\n' + '\n'.join(f'  {r} — {l}' for r, l, _ in image_choices(product)),
             f"- 관리자 메모: {(story.notes if story else '') or '(없음)'}"]
    lang_note = ('# 응답 언어\n관리자에게는 한국어로 답한다 (사이트 문구는 영어+한국어).' if studio_lang() == 'ko'
                 else '# Reply language\nReply to the admin in clear English (site copy still in English + Korean).')
    return (PERSONA_FILE.read_text(encoding='utf-8') + '\n\n' + lang_note + '\n\n# 사이트 문구 규칙 (영문 원문)\n' + COPY_RULES + '\n\n# 페이지 JSON\n' + SCHEMA_NOTE
            + '\n\n# 상품 정보\n' + product_facts(product) + '\n\n# 현재 상태\n' + '\n'.join(state)
            + '\n\n# 현재 초안 JSON\n' + json.dumps(working, ensure_ascii=False)[:12000])


def run_studio_tool(product, story, name, raw):
    try: args = json.loads(raw or '{}')
    except ValueError: return {'status': 'error', 'message': 'Arguments were not valid JSON.'}, None
    if name == 'save_draft':
        try: content = clean_content(args.get('content') or {}, product)
        except ValueError as e: return {'status': 'error', 'message': str(e)}, None
        _, _, problems = save_draft(product, story, content)
        stop = [f'[{v} {c}] {t}' for v, c, t in problems if v in ('REVISE', 'BLOCK')]
        review = [f'[{v} {c}] {t}' for v, c, t in problems if v not in ('REVISE', 'BLOCK')]
        return ({'status': 'saved_with_problems' if stop else 'saved', 'must_fix': stop, 'review_only': review[:8]},
                {'type': 'draft', 'problems': len(stop), 'review': len(review)})
    if name == 'propose_image':
        ok, im = add_proposal(product, args.get('provider'), args.get('source_ref', ''), 'Rebu Studio chat', args.get('plan_ko'), args.get('plan_en'),
                              args.get('prompt'), args.get('size'), args.get('label'), args.get('slot', ''))
        if not ok: return {'status': 'error', 'message': im}, None
        return ({'status': 'proposed', 'image_id': im.id, 'cost': im.cost},
                {'type': 'image', 'id': im.id, 'slot': im.slot, 'provider': im.provider, 'model': im.model, 'cost': im.cost, 'size': im.size,
                 'plan': im.plan.get(studio_lang()) or im.plan.get('en'), 'source': im.source})
    return {'status': 'error', 'message': 'Unknown tool.'}, None


@bp.post('/products/story/<slug>/chat')
@admin_required
def story_chat(slug):
    from support import openai_request, key
    product = _product(slug)
    history = (request.get_json(silent=True) or {}).get('messages')
    if not isinstance(history, list) or not 0 < len(history) <= 40: abort(400)
    msgs = []
    for m in history[-16:]:
        if not isinstance(m, dict) or m.get('role') not in ('user', 'assistant') or not isinstance(m.get('content'), str) or not 0 < len(m['content'].strip()) <= 3000: abort(400)
        msgs.append({'role': m['role'], 'content': m['content'].strip()})
    if msgs[-1]['role'] != 'user': abort(400)
    if not key(): return jsonify(error='unavailable'), 503
    now = time.time()
    recent = [t for t in session.get('studio_times', []) if now - t < 600]
    if len(recent) >= 40: return jsonify(error='rate_limited'), 429
    session['studio_times'] = recent + [now]
    story = _story(slug); db.session.commit()
    messages = [{'role': 'system', 'content': studio_prompt(product, story)}] + msgs
    events = []
    for _ in range(4):
        ok, message = openai_request({'messages': messages, 'tools': STUDIO_TOOLS, 'max_completion_tokens': 4000}, timeout=90)
        if not ok: return jsonify(error='upstream', detail=message), 502
        calls = message.get('tool_calls') or []
        if not calls: return jsonify(reply=(message.get('content') or '').strip() or '…', events=events)
        messages.append({'role': 'assistant', 'content': message.get('content'), 'tool_calls': calls})
        for call in calls[:3]:
            fn = call.get('function') or {}
            result, event = run_studio_tool(product, story, fn.get('name'), fn.get('arguments'))
            if event: events.append(event)
            messages.append({'role': 'tool', 'tool_call_id': call.get('id', ''), 'content': json.dumps(result, ensure_ascii=False)})
        for call in calls[3:]:
            messages.append({'role': 'tool', 'tool_call_id': call.get('id', ''), 'content': '{"status":"error","message":"Up to 3 at a time."}'})
    ko = studio_lang() == 'ko'
    return jsonify(reply='저장했어요. 미리보기를 확인해 주세요.' if ko else 'Saved. Please check the preview.', events=events)
