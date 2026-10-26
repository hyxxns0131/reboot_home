"""Admin AI assistant "Rebu Operator" (README §27): creates popups, creator links and products from a chat.

Flow: chat -> OpenAI (tools) -> the server checks the proposal with the same rules as the forms (admin/actions.py)
plus the dashboard compliance rules (support/guard.py) -> a pending action -> the admin presses Save -> saved.
The model never writes to the database by itself.
"""
import base64
import io
import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from flask import request, jsonify, abort, session, Response, current_app
from flask_login import current_user
from auth.decorators import admin_required
from core.extensions import db
from admin import bp
from admin.actions import ActionError, build_creator, build_popup, build_product, create_product

PERSONA_FILE = Path(__file__).parent / 'data' / 'assistant_persona.md'
LIMIT, WINDOW = 40, 600          # admin messages per 10 minutes
MAX_ROUNDS = 3                   # tool call rounds per message
KST = timezone(timedelta(hours=9))


class AssistantUpload(db.Model):
    """An image the admin attached in the assistant chat (WEBP, same conversion as product photos)."""
    __tablename__ = 'admin_assistant_upload'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    filename = db.Column(db.String(120), nullable=False, default='')
    width = db.Column(db.Integer, nullable=False, default=0)
    height = db.Column(db.Integer, nullable=False, default=0)
    data = db.Column(db.LargeBinary, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class AssistantAction(db.Model):
    """A checked proposal waiting for the admin's Save (or saved / cancelled)."""
    __tablename__ = 'admin_assistant_action'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    kind = db.Column(db.String(20), nullable=False)          # popup · creator_link · product
    payload = db.Column(db.Text, nullable=False)             # JSON of the proposed fields
    status = db.Column(db.String(10), nullable=False, default='pending')  # pending · saved · cancelled
    result = db.Column(db.String(200), nullable=False, default='')        # where to see it after saving
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


# ---------- Tools the model may call ----------
def S(d=''): return {'type': 'string', 'description': d}


def tool(name, description, props):
    return {'type': 'function', 'function': {'name': name, 'description': description, 'parameters': {
        'type': 'object', 'additionalProperties': False, 'required': list(props), 'properties': props}}}


TOOLS = [
    tool('propose_popup', 'Prepare a site popup. Call only when the title and the period (or "no period") are known.', {
        'title': S('English, up to 80 characters'), 'body': S('English, up to 600 characters, or empty'),
        'button_label': S('up to 30 characters, or empty'), 'button_link': S('/path on this site or https:// address, or empty'),
        'placement': {'type': 'string', 'enum': ['home', 'all']},
        'starts_on': S('YYYY-MM-DD or empty'), 'ends_on': S('YYYY-MM-DD or empty'),
        'image_id': {'type': 'integer', 'description': 'attached image number, 0 for no image'}}),
    tool('propose_creator_link', "Prepare an influencer's dedicated link and discount code.", {
        'name': S('creator name'), 'platform': {'type': 'string', 'enum': ['Instagram', 'TikTok']},
        'discount': {'type': 'integer', 'description': 'customer discount %, 0-50'},
        'commission': {'type': 'integer', 'description': 'creator commission %, 0-50'},
        'code': S('A-Z0-9, 3-40 characters, or empty for automatic'), 'landing': S('"" for home or /products/<slug>')}),
    tool('propose_product', 'Prepare a new (seasonal / limited) product. Needs an attached photo.', {
        'name': S('English, 3-80 characters'), 'line': {'type': 'string', 'enum': ['Jelly', 'Drink']},
        'version': {'type': 'string', 'enum': ['original', 'balance']},
        'format': S('English'), 'pack': S('English'), 'flavors': S('comma separated, up to 6'),
        'volume': S('e.g. 100ml, or empty'), 'badge': S('e.g. LIMITED, or empty'), 'tagline': S('English, or empty'),
        'options': {'type': 'array', 'minItems': 1, 'maxItems': 4, 'items': {
            'type': 'object', 'additionalProperties': False, 'required': ['label', 'price', 'pieces', 'stock'],
            'properties': {'label': S('English'), 'price': {'type': 'number', 'description': 'USD'},
                           'pieces': {'type': 'integer'}, 'stock': {'type': 'integer'}}}},
        'image_id': {'type': 'integer', 'description': 'attached product photo number'},
        'publish': {'type': 'boolean', 'description': 'true = live now, false = hidden'}}),
]
KINDS = {'propose_popup': 'popup', 'propose_creator_link': 'creator_link', 'propose_product': 'product'}


def persona():
    return PERSONA_FILE.read_text(encoding='utf-8')


def site_state():
    """Facts the assistant needs: today, pages, popups, creator codes, products."""
    from admin import landing_pages
    from core.popups import Popup
    from shop.models import ReferralLink
    from products.services import get_all_products
    today = datetime.now(KST).date()
    popups = db.session.scalars(db.select(Popup).order_by(Popup.id.desc()).limit(8)).all()
    codes = db.session.scalars(db.select(ReferralLink.code).order_by(ReferralLink.id)).all()
    return '\n'.join([
        f"- 오늘: {today.isoformat()} ({'월화수목금토일'[today.weekday()]}요일, 한국 시간)",
        '- 상품: ' + '; '.join(f"{p['name']} (/products/{p['slug']}, {p.get('line', '')})" for p in get_all_products(include_hidden=True)),
        '- 크리에이터 링크 도착 페이지: ' + ', '.join(f'"{k}"={v}' for k, v in landing_pages().items()),
        '- 이미 쓰는 할인코드: ' + (', '.join(codes) or '없음'),
        '- 최근 팝업: ' + ('; '.join(f"{p.title} [{p.starts_on or '시작일 없음'}~{p.ends_on or '종료일 없음'}, {'노출 중' if p.is_live() else '비노출'}]" for p in popups) or '없음')])


LANGUAGE_NOTE = {
    'ko': '# 응답 언어\n관리자 화면 언어가 한국어다. 모든 답을 한국어 존댓말로 한다 (사이트에 올라갈 문구만 영어).',
    'en': ('# Reply language\nThe admin set the site to English. Reply to the admin in clear, simple English (not Korean), '
           'keeping every rule of this persona. Site copy stays in US English as always.'),
}


def lang():
    """Admins are mostly Korean, so the assistant speaks Korean unless English was picked with the language switch this session."""
    return 'en' if session.get('lang_picked') and session.get('lang') == 'en' else 'ko'


def ai_tr(text):
    """tr() for the assistant panel: Korean by default for admins (see lang())."""
    from core.translations import KO
    return KO.get(str(text), str(text)) if lang() == 'ko' else str(text)


@bp.record_once
def register_ai_tr(state):
    state.app.jinja_env.globals['ai_tr'] = ai_tr


def t(en, ko):
    return ko if lang() == 'ko' else en


def system_prompt():
    # The persona is written in Korean (Korean admins are the main users); the reply language follows the site language switch.
    return persona() + '\n\n' + LANGUAGE_NOTE[lang()] + '\n\n# 현재 사이트 상태\n' + site_state() + '\n'


# ---------- Checking a proposal ----------
def copy_check(*texts):
    """Site copy must pass the dashboard compliance rules (REVISE / BLOCK are refused)."""
    from support.guard import review, STOP
    result = review('\n'.join(t for t in texts if t))
    if result['verdict'] in STOP:
        words = sorted({w for found in result['hits'].values() for w in found})
        raise ActionError(f"Compliance check failed ({result['verdict']}, rules {', '.join(result['codes'])}): remove or reword {', '.join(words)}.")


def own_upload(image_id, required=False):
    if not image_id:
        if required: raise ActionError('Attach a product photo in the chat first.')
        return None
    up = db.session.get(AssistantUpload, int(image_id))
    if not up or up.user_id != current_user.id: raise ActionError(f'Image #{image_id} was not found. Attach the photo again.')
    return up


def product_form(a):
    form = {k: a.get(k, '') for k in ('name', 'line', 'version', 'format', 'pack', 'flavors', 'volume', 'badge', 'tagline')}
    for i, o in enumerate((a.get('options') or [])[:4]):
        form.update({f'opt_label_{i}': o.get('label', ''), f'opt_price_{i}': o.get('price', ''), f'opt_count_{i}': o.get('pieces', 1), f'opt_stock_{i}': o.get('stock', 0)})
    form['hidden'] = '' if a.get('publish') else '1'
    return form


def check(kind, a):
    """Raise ActionError, or return the card rows the admin will see (in the admin's language)."""
    tr = ai_tr
    if kind == 'popup':
        from core.popups import Popup, PLACEMENTS
        p = build_popup(Popup(), a); up = own_upload(a.get('image_id'))
        copy_check(p.title, p.body, p.button_label)
        return [(tr('Title'), p.title), (tr('Text'), p.body or '—'), (tr('Button'), f'{p.button_label} → {p.button_link}' if p.button_label else '—'),
                (tr('Show on'), tr(PLACEMENTS[p.placement])),
                (tr('Period'), f"{p.starts_on or t('now', '지금부터')} → {p.ends_on or t('no end', '종료일 없음')}"), (tr('Image'), f'#{up.id}' if up else '—')]
    if kind == 'creator_link':
        link = build_creator(a)
        return [(tr('Creator'), link.influencer_name), (tr('Platform'), link.platform), (tr('Code / link'), f'{link.code} · /r/{link.code}'),
                (tr('Discount'), f'{int(link.discount_rate * 100)}%'), (tr('Commission'), f'{int(link.commission_rate * 100)}%'),
                (tr('Opens'), link.landing or t('Home', '홈'))]
    if kind == 'product':
        up = own_upload(a.get('image_id'), required=True)
        plan = build_product(product_form(a), True)
        d = plan['data']
        copy_check(d['name'], d['format'], d['pack'], ', '.join(d['flavors']), d.get('badge', ''), a.get('tagline', ''), *[o['label'] for o in plan['opts']])
        return [(tr('Name'), d['name']), (tr('Line'), f"{d['line']} · {'Balance (Zero Sugar)' if d['is_balance'] else 'Original'}"), (tr('Format'), d['format']),
                (tr('Pack'), d['pack']), (tr('Flavors'), ', '.join(d['flavors'])),
                (tr('Options'), '; '.join(f"{o['label']} ${o['price_usd']:.2f} ×{o['unit_count']} ({t('stock', '재고')} {o['stock']})" for o in plan['opts'])),
                (tr('Status'), t('Hidden (press Show later)', '숨김 (나중에 Show로 공개)') if plan['hidden'] else t('Live now', '바로 공개')), (tr('Photo'), f'#{up.id}')]
    raise ActionError('Unknown action.')


def run_tool(name, raw):
    """One tool call -> (result for the model, card for the admin or None)."""
    kind = KINDS.get(name)
    try:
        args = json.loads(raw or '{}')
        if not kind or not isinstance(args, dict): raise ActionError('Unknown tool.')
        rows = check(kind, args)
    except ActionError as e:
        db.session.rollback()
        return {'status': 'error', 'message': str(e)}, None
    except (ValueError, TypeError, AttributeError):
        db.session.rollback()
        return {'status': 'error', 'message': 'The fields could not be read. Check the values and try again.'}, None
    db.session.rollback()  # checking never saves anything; only the pending action below is stored
    action = AssistantAction(user_id=current_user.id, kind=kind, payload=json.dumps(args, ensure_ascii=False))
    db.session.add(action); db.session.commit()
    card = dict(id=action.id, kind=kind, rows=rows, image=f'/admin/assistant/uploads/{args["image_id"]}.webp' if args.get('image_id') else '')
    return {'status': 'ready', 'action_id': action.id, 'summary': rows}, card


# ---------- Conversation ----------
def to_openai(history):
    """Browser history -> OpenAI messages. Only the newest attached images go as pictures; older ones as text."""
    last = max((i for i, m in enumerate(history) if m.get('images')), default=-1)
    out = []
    for i, m in enumerate(history):
        ids = m.get('images', [])[:3]
        text = m['content'] + ('\n' + ' '.join(f'[첨부 이미지 #{x}]' for x in ids) if ids else '')
        if i == last and m['role'] == 'user':
            parts = [{'type': 'text', 'text': text}]
            for x in ids:
                up = db.session.get(AssistantUpload, x)
                if up and up.user_id == current_user.id:
                    parts.append({'type': 'image_url', 'image_url': {'url': 'data:image/webp;base64,' + base64.b64encode(up.data).decode(), 'detail': 'low'}})
            out.append({'role': 'user', 'content': parts})
        else:
            out.append({'role': m['role'], 'content': text})
    return out


def read_history():
    history = (request.get_json(silent=True) or {}).get('messages')
    if not isinstance(history, list) or not 0 < len(history) <= 40: abort(400)
    clean = []
    for m in history[-16:]:
        if not isinstance(m, dict) or m.get('role') not in ('user', 'assistant') or not isinstance(m.get('content'), str): abort(400)
        content, images = m['content'].strip(), m.get('images') or []
        if not 0 < len(content) <= 2000 or not isinstance(images, list) or not all(type(x) is int for x in images): abort(400)
        clean.append({'role': m['role'], 'content': content, 'images': images})
    if clean[-1]['role'] != 'user': abort(400)
    return clean


@bp.post('/assistant/chat')
@admin_required
def assistant_chat():
    from support import openai_request, key
    history = read_history()
    if not key(): return jsonify(error='unavailable'), 503
    now = time.time()
    recent = [t for t in session.get('assistant_times', []) if now - t < WINDOW]
    if len(recent) >= LIMIT: return jsonify(error='rate_limited'), 429
    session['assistant_times'] = recent + [now]
    messages = [{'role': 'system', 'content': system_prompt()}] + to_openai(history)
    cards = []
    for _ in range(MAX_ROUNDS):
        # Guide only (README §30): creating happens in each tab's AI workspace, so no tools here.
        ok, message = openai_request({'messages': messages, 'max_completion_tokens': 700}, timeout=45)
        if not ok:
            current_app.logger.error('Admin assistant failed: %s', message)
            return jsonify(error='upstream', detail=message), 502
        calls = message.get('tool_calls') or []
        if not calls:
            return jsonify(reply=(message.get('content') or '').strip() or '…', actions=cards)
        messages.append({'role': 'assistant', 'content': message.get('content'), 'tool_calls': calls})
        for n, call in enumerate(calls):
            fn = call.get('function') or {}
            if n < 3: result, card = run_tool(fn.get('name'), fn.get('arguments'))
            else: result, card = {'status': 'error', 'message': 'Up to 3 requests at a time.'}, None
            if card: cards.append(card)
            messages.append({'role': 'tool', 'tool_call_id': call.get('id', ''), 'content': json.dumps(result, ensure_ascii=False)})
    return jsonify(reply=t('Please check the card below.', '아래 확인 카드를 확인해 주세요.') if cards else t('I could not finish that. Please say it again.', '요청을 처리하지 못했어요. 다시 말씀해 주세요.'), actions=cards)


@bp.post('/assistant/upload')
@admin_required
def assistant_upload():
    from products.media import to_webp
    from PIL import Image
    f = request.files.get('image')
    if not f or not f.filename: return jsonify(error='Choose an image.'), 400
    try: data = to_webp(f.read())
    except Exception as e: return jsonify(error=str(e) if isinstance(e, ValueError) else 'That file is not a readable image (JPG, PNG or WEBP).'), 400
    w, h = Image.open(io.BytesIO(data)).size
    up = AssistantUpload(user_id=current_user.id, filename=f.filename[:120], width=w, height=h, data=data)
    db.session.add(up); db.session.commit()
    return jsonify(id=up.id, url=f'/admin/assistant/uploads/{up.id}.webp', width=w, height=h)


@bp.get('/assistant/uploads/<int:upload_id>.webp')
@admin_required
def assistant_upload_file(upload_id):
    up = db.session.get(AssistantUpload, upload_id) or abort(404)
    return Response(up.data, mimetype='image/webp', headers={'Cache-Control': 'private, max-age=3600'})


@bp.post('/assistant/actions/<int:action_id>/<decision>')
@admin_required
def assistant_decide(action_id, decision):
    """Save (or cancel) a proposal. Everything is checked again, since the site may have changed since."""
    action = db.session.get(AssistantAction, action_id)
    if not action or action.user_id != current_user.id: abort(404)
    if decision not in ('save', 'cancel'): abort(400)
    if action.status != 'pending': return jsonify(error=t(f'This request is already {action.status}.', '이미 처리된 요청이에요.')), 409
    if decision == 'cancel':
        action.status = 'cancelled'; db.session.commit()
        return jsonify(ok=True, message=t('Cancelled.', '취소했어요.'), status='cancelled')
    args = json.loads(action.payload)
    try:
        message, link = perform(action.kind, args)
    except ActionError as e:
        db.session.rollback()
        return jsonify(error=ai_tr(str(e))), 400
    action = db.session.get(AssistantAction, action_id)
    action.status = 'saved'; action.result = link
    db.session.commit()
    return jsonify(ok=True, message=message, link=link, status='saved')


def perform(kind, args):
    """Check again and save a popup / creator link / product. Returns (message, link). Raises ActionError. Caller commits."""
    from rewards.services import record
    check(kind, args)
    db.session.rollback()
    if kind == 'popup':
        from core.popups import Popup
        p = build_popup(Popup(), args); up = own_upload(args.get('image_id'))
        if up: p.image = up.data
        p.is_active = True; db.session.add(p)
        record('popup_saved', {'title': p.title, 'via': 'ai'})
        message = t(f'Popup saved: {p.title}', f'팝업을 저장했어요: {p.title}') + ('' if p.is_live() else t(' (not live yet — check its dates)', ' (아직 노출 전 — 기간을 확인하세요)'))
        link = '/admin/manage#popups'
    elif kind == 'creator_link':
        link_row = build_creator(args); db.session.add(link_row)
        record('creator_link_created', {'code': link_row.code, 'via': 'assistant'})
        message, link = t(f'Creator link created: /r/{link_row.code}', f'크리에이터 링크를 만들었어요: /r/{link_row.code}'), '/admin/manage#creators'
    else:
        up = own_upload(args.get('image_id'), required=True)
        plan = build_product(product_form(args), True)
        create_product(plan, up.data)
        from products import autopage
        autopage.queue(plan['slug'], use_ai_images=args.get('auto_page', True) is not False)
        message = t(f"{plan['name']} was added" + (' as hidden.' if plan['hidden'] else ' and is live.'),
                    f"{plan['name']} 상품을 " + ('숨김으로 등록했어요.' if plan['hidden'] else '등록하고 공개했어요.'))
        message += t(' Its long detail page is being made automatically (Admin › Products shows the progress).', ' 상세페이지를 자동으로 만들고 있어요 (관리자 › 상품에서 진행 상황 확인).')
        link = f"/admin/products#p-{plan['slug']}"
    return message, link
