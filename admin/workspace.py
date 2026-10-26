"""Per-tab AI workspaces (README §30): "AI로 생성하기" on Add product, Site popups and Creator links.

Left: a chat with the tab's own persona (admin/data/personas/<kind>.md + _common.md). Right: the live draft.
The AI fills the draft only through update_draft as it agrees each value with the admin; the server answers with what is
still missing and what breaks the rules. Saving is the admin's button, and runs the same checks as the forms.
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from flask import render_template, request, jsonify, abort, session
from flask_login import current_user
from auth.decorators import admin_required
from core.extensions import db
from admin import bp
from admin.actions import ActionError
from admin.assistant import (check, perform, own_upload, site_state, read_history, to_openai, ai_tr, lang, t, LANGUAGE_NOTE)

PERSONAS = Path(__file__).parent / 'data' / 'personas'
KINDS = {
    'product': dict(action='product', ko='상품 등록', en='Add product', back='/admin/products/new',
                    fields=['name', 'line', 'version', 'format', 'pack', 'flavors', 'volume', 'badge', 'tagline', 'options', 'image_id', 'publish'],
                    required=[('name', '상품명', 'Name'), ('line', '라인', 'Line'), ('version', '버전', 'Version'), ('format', '형태', 'Format'),
                              ('pack', '포장', 'Pack'), ('flavors', '맛', 'Flavors'), ('options', '판매 옵션', 'Options'),
                              ('image_id', '상품 사진', 'Photo'), ('publish', '공개 여부', 'Publish or hide')]),
    'popup': dict(action='popup', ko='팝업', en='Site popup', back='/admin/manage#popups',
                  fields=['title', 'body', 'button_label', 'button_link', 'placement', 'starts_on', 'ends_on', 'no_period', 'image_id'],
                  required=[('title', '제목', 'Title'), ('period', '노출 기간', 'Period')]),
    'creator': dict(action='creator_link', ko='크리에이터 링크', en='Creator link', back='/admin/manage#creators',
                    fields=['name', 'platform', 'discount', 'commission', 'code', 'landing'],
                    required=[('name', '크리에이터 이름', 'Creator'), ('platform', '플랫폼', 'Platform'),
                              ('discount', '고객 할인율', 'Discount'), ('commission', '수수료율', 'Commission')]),
}


class AIDraft(db.Model):
    """The draft a tab's AI is building with one admin (one per admin and tab)."""
    __tablename__ = 'admin_ai_draft'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    kind = db.Column(db.String(20), nullable=False)
    fields = db.Column(db.JSON, nullable=False, default=dict)
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (db.UniqueConstraint('user_id', 'kind'),)


def kind_or_404(kind):
    return KINDS.get(kind) or abort(404)


def draft_for(kind):
    d = db.session.scalar(db.select(AIDraft).filter_by(user_id=current_user.id, kind=kind))
    if not d:
        d = AIDraft(user_id=current_user.id, kind=kind, fields={}); db.session.add(d); db.session.flush()
    return d


def filled(v):
    return v not in (None, '', [], {})


def args_for(kind, f):
    """Draft fields -> the arguments check()/perform() expect."""
    a = dict(f)
    if isinstance(a.get('flavors'), list): a['flavors'] = ', '.join(str(x) for x in a['flavors'])
    if kind == 'popup' and a.get('no_period'): a['starts_on'] = a['ends_on'] = ''
    if kind == 'product': a.setdefault('publish', False)
    if kind == 'creator':
        a.setdefault('code', ''); a.setdefault('landing', '')
    return a


def state(kind, f):
    """What the right-hand panel shows: missing required fields, problems, the checked card, and whether Save is allowed."""
    spec = KINDS[kind]
    missing = []
    for key, ko, en in spec['required']:
        ok = (filled(f.get('starts_on')) or f.get('no_period')) if key == 'period' else (key in f if key == 'publish' else filled(f.get(key)))
        if not ok: missing.append(t(en, ko))
    problems, rows = [], []
    texts = [f.get(k) for k in ('name', 'format', 'pack', 'flavors', 'badge', 'tagline', 'title', 'body', 'button_label') if isinstance(f.get(k), str)]
    texts += [o.get('label', '') for o in (f.get('options') or []) if isinstance(o, dict)]
    from support.guard import review, STOP
    for s in texts:
        r = review(s)
        if r['verdict'] in STOP: problems.append(t(f'Compliance ({",".join(r["codes"])}): "{s}"', f'컴플라이언스 위반({",".join(r["codes"])}): "{s}"'))
    if not missing and not problems:
        try: rows = check(spec['action'], args_for(kind, f))
        except ActionError as e: problems.append(ai_tr(str(e)))
        except (ValueError, TypeError): problems.append(t('Some values could not be read.', '읽을 수 없는 값이 있어요.'))
        db.session.rollback()
    image = ''
    if f.get('image_id'):
        try: image = f'/admin/assistant/uploads/{int(f["image_id"])}.webp' if own_upload(f['image_id']) else ''
        except ActionError: problems.append(t(f'Image #{f["image_id"]} was not found.', f'이미지 #{f["image_id"]}를 찾을 수 없어요.'))
    return dict(fields=f, missing=missing, problems=problems, rows=rows, image=image, ready=not missing and not problems)


def system_prompt(kind, f):
    spec = KINDS[kind]
    st = state(kind, f)
    return ((PERSONAS / '_common.md').read_text(encoding='utf-8') + '\n\n' + (PERSONAS / f'{kind}.md').read_text(encoding='utf-8')
            + '\n\n' + LANGUAGE_NOTE[lang()] + '\n\n# 현재 사이트 상태\n' + site_state()
            + '\n\n# 현재 초안 (오른쪽 화면에 보이는 값)\n' + json.dumps(f, ensure_ascii=False)
            + '\n- 빠진 필수 항목: ' + (', '.join(st['missing']) or '없음')
            + '\n- 문제: ' + (' | '.join(st['problems']) or '없음')
            + ('\n- 저장 가능: 예 (관리자에게 [저장] 버튼을 안내)' if st['ready'] else '')
            + '\n\n# 반드시 지킬 것\n관리자의 이번 메시지에 정해진 값(날짜, 이름, 숫자, 문구, 사진 번호 등)이 하나라도 있으면, 답을 쓰기 전에 **먼저 update_draft를 호출**해 초안에 넣는다. '
              'update_draft를 호출하지 않았다면 "설정했다/반영했다/넣었다"고 말하지 않는다. 날짜는 YYYY-MM-DD(올해 기준)로 넣는다.')


def tool(kind):
    return [{'type': 'function', 'function': {
        'name': 'update_draft',
        'description': 'Put values the admin agreed on into the live draft (shown on the right). Send only the fields that change; null clears a field.',
        'parameters': {'type': 'object', 'required': ['fields'], 'properties': {'fields': {
            'type': 'object', 'description': 'Allowed keys: ' + ', '.join(KINDS[kind]['fields'])}}}}}]


@bp.get('/ai/<kind>')
@admin_required
def ai_workspace(kind):
    from support import chat_config
    spec = kind_or_404(kind)
    d = draft_for(kind); db.session.commit()
    from admin import _autopage_info
    return render_template('admin/ai_workspace.html', title=spec['en'], kind=kind, spec=spec, ko=lang() == 'ko',
                           config=chat_config(), state=state(kind, d.fields), autopage=_autopage_info() if kind == 'product' else None)


@bp.post('/ai/<kind>/chat')
@admin_required
def ai_workspace_chat(kind):
    from support import openai_request, key
    kind_or_404(kind)
    history = read_history()
    if not key(): return jsonify(error='unavailable'), 503
    now = time.time()
    recent = [x for x in session.get('ai_ws_times', []) if now - x < 600]
    if len(recent) >= 60: return jsonify(error='rate_limited'), 429
    session['ai_ws_times'] = recent + [now]
    d = draft_for(kind); db.session.commit()
    allowed = set(KINDS[kind]['fields'])
    messages = [{'role': 'system', 'content': system_prompt(kind, d.fields)}] + to_openai(history)
    for n in range(4):
        # Round 1 always goes through update_draft (README §34): whatever the admin just decided lands on the right before the reply.
        choice = {'type': 'function', 'function': {'name': 'update_draft'}} if n == 0 else ('none' if n == 3 else 'auto')
        ok, message = openai_request({'messages': messages, 'tools': tool(kind), 'tool_choice': choice, 'max_completion_tokens': 1200}, timeout=60)
        if not ok: return jsonify(error='upstream', detail=message), 502
        calls = message.get('tool_calls') or []
        if not calls:
            return jsonify(reply=(message.get('content') or '').strip() or '…', state=state(kind, d.fields))
        messages.append({'role': 'assistant', 'content': message.get('content'), 'tool_calls': calls})
        for call in calls[:3]:
            try:
                changes = json.loads((call.get('function') or {}).get('arguments') or '{}').get('fields') or {}
                if not isinstance(changes, dict): raise ValueError
            except (ValueError, AttributeError):
                result = {'status': 'error', 'message': 'fields must be an object'}
            else:
                f = dict(d.fields)
                ignored = [k for k in changes if k not in allowed]
                for k, v in changes.items():
                    if k in allowed:
                        if v is None: f.pop(k, None)
                        else: f[k] = v
                d.fields = f; d.updated_at = datetime.now(timezone.utc); db.session.commit()
                st = state(kind, f)
                result = {'status': 'updated', 'missing': st['missing'], 'problems': st['problems'], 'ready': st['ready'], 'ignored_keys': ignored}
            messages.append({'role': 'tool', 'tool_call_id': call.get('id', ''), 'content': json.dumps(result, ensure_ascii=False)})
    return jsonify(reply=t('The draft is updated on the right.', '오른쪽 초안에 반영했어요.'), state=state(kind, d.fields))


@bp.post('/ai/<kind>/upload')
@admin_required
def ai_workspace_upload(kind):
    """Photo for this tab's draft (README §34): saved like the assistant uploads and put straight into the draft's image_id."""
    from products.media import to_webp
    from PIL import Image
    import io
    from admin.assistant import AssistantUpload
    kind_or_404(kind)
    f = request.files.get('image')
    if not f or not f.filename: return jsonify(error=t('Choose an image.', '이미지를 골라 주세요.')), 400
    try: data = to_webp(f.read())
    except ValueError as e: return jsonify(error=ai_tr(str(e))), 400
    except Exception: return jsonify(error=t('That file is not a readable image (JPG, PNG or WEBP).', '읽을 수 없는 이미지예요 (JPG, PNG, WEBP).')), 400
    w, h = Image.open(io.BytesIO(data)).size
    up = AssistantUpload(user_id=current_user.id, filename=f.filename[:120], width=w, height=h, data=data)
    db.session.add(up); db.session.flush()
    d = draft_for(kind)
    if 'image_id' in KINDS[kind]['fields']:
        d.fields = dict(d.fields, image_id=up.id); d.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(id=up.id, url=f'/admin/assistant/uploads/{up.id}.webp', width=w, height=h, state=state(kind, d.fields))


@bp.get('/ai/<kind>/state')
@admin_required
def ai_workspace_state(kind):
    kind_or_404(kind)
    d = draft_for(kind); db.session.commit()
    return jsonify(state=state(kind, d.fields))


@bp.post('/ai/<kind>/save')
@admin_required
def ai_workspace_save(kind):
    spec = kind_or_404(kind)
    d = draft_for(kind)
    st = state(kind, d.fields)
    if not st['ready']:
        return jsonify(error=t('Not ready yet: ', '아직 저장할 수 없어요: ') + ', '.join(st['missing'] + st['problems'])), 400
    try:
        message, link = perform(spec['action'], args_for(kind, d.fields))
    except ActionError as e:
        db.session.rollback()
        return jsonify(error=ai_tr(str(e))), 400
    d = draft_for(kind); d.fields = {}
    db.session.commit()
    if kind == 'product':
        from products import autopage
        autopage.kick()  # long detail page in the background (README §34)
    return jsonify(ok=True, message=message, link=link)


@bp.post('/ai/<kind>/reset')
@admin_required
def ai_workspace_reset(kind):
    kind_or_404(kind)
    d = draft_for(kind); d.fields = {}; db.session.commit()
    return jsonify(ok=True, state=state(kind, {}))
