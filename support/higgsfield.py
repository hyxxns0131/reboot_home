"""Higgsfield API (README §29): server-side only. Credentials = key ID + secret from console.higgsfield.ai.

Docs: https://docs.higgsfield.ai — base URL https://api.higgsfield.ai, header "Authorization: Key <id>:<secret>",
async requests (submit -> request_id/status_url -> poll until completed), presigned uploads, POST /estimate/<model> for a USD estimate.
"""
import json
import os
import urllib.error
import urllib.request
import uuid

BASE = 'https://api.higgsfield.ai'
MODELS = {  # model id -> how to build its body from (prompt, image_urls, aspect_ratio)
    'higgsfield/ads-studio/v1.0': lambda p, urls, ar: {'prompt': p, 'image_urls': urls, 'aspect_ratio': ar, 'batch_size': 1,
                                                       'niche': 'Party snacks and drinks for adults 21+', 'language': 'en'},
    'xai/grok-imagine-image-2.0': lambda p, urls, ar: {'prompt': p, 'image_urls': urls, 'aspect_ratio': ar, 'resolution': '2k', 'quality': 'medium'},
}


def credentials():
    """(key_id, secret) from HIGGSFIELD_API_KEY_ID + HIGGSFIELD_API_KEY_SECRET, or one combined 'id:secret' value."""
    clean = lambda v: (v or '').strip().strip('"\'')
    kid, secret = clean(os.getenv('HIGGSFIELD_API_KEY_ID')), clean(os.getenv('HIGGSFIELD_API_KEY_SECRET'))
    if kid and secret: return kid, secret
    for name in ('HIGGSFIELD_API_KEY', 'HF_KEY'):
        combined = clean(os.getenv(name))
        if ':' in combined:
            a, b = combined.split(':', 1)
            if a and b: return a, b
    return None


def model():
    m = (os.getenv('HIGGSFIELD_IMAGE_MODEL') or 'higgsfield/ads-studio/v1.0').strip()
    return m if m in MODELS else 'higgsfield/ads-studio/v1.0'


def config():
    c = credentials()
    return dict(key_set=bool(c), key_hint=(c[0][:4] + '…' + c[0][-4:]) if c and len(c[0]) > 10 else ('set' if c else ''), model=model())


def request(method, path_or_url, body=None, headers=None, timeout=30):
    """Returns (status_code, parsed JSON or text). status 0 = network error."""
    c = credentials()
    if not c: return 0, 'Higgsfield API key is not set.'
    url = path_or_url if path_or_url.startswith('https://') else BASE + path_or_url
    h = {'Authorization': f'Key {c[0]}:{c[1]}', **(headers or {})}
    data = None
    if body is not None:
        data = json.dumps(body).encode(); h['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode() or '{}'
            code = getattr(r, 'status', 200)
            try: return code, json.loads(raw)
            except ValueError: return code, raw
    except urllib.error.HTTPError as e:
        try: detail = json.loads(e.read().decode()).get('detail', '')
        except Exception: detail = ''
        return e.code, detail if isinstance(detail, str) else json.dumps(detail)[:200]
    except (urllib.error.URLError, TimeoutError) as e:
        return 0, f'Could not reach api.higgsfield.ai ({getattr(e, "reason", e)}).'


def test():
    """Light authenticated call (usage analytics). (ok, message)."""
    code, body = request('GET', '/models/usage?timeframe=day')
    hint = {401: 'The key ID or secret was rejected.', 403: 'The key is disabled or expired, or the balance is empty.'}
    if code == 200: return True, 'Connected.'
    return False, f'HTTP {code}: {hint.get(code, "")} {body if isinstance(body, str) else ""}'.strip() if code else str(body)


def upload(data, content_type='image/png'):
    """Presigned upload -> public URL for image_urls. (ok, url or reason)."""
    code, up = request('POST', '/files/generate-upload-url', {'content_type': content_type})
    if code != 200 or not isinstance(up, dict): return False, f'Upload URL failed (HTTP {code}).'
    put = urllib.request.Request(up['upload_url'], data=data, method='PUT', headers=up.get('upload_headers') or {'Content-Type': content_type})
    try:
        with urllib.request.urlopen(put, timeout=60): pass
    except Exception as e:
        return False, f'Upload failed ({type(e).__name__}).'
    return True, up['public_url']


def body_for(prompt, image_urls, aspect_ratio):
    return MODELS[model()](prompt, image_urls, aspect_ratio)


def estimate(prompt, aspect_ratio, with_image=False):
    """USD estimate from Higgsfield for the same parameters (reference URL is a placeholder), or None."""
    urls = ['https://example.com/reference.png'] if with_image else []
    code, body = request('POST', f'/estimate/{model()}', body_for(prompt, urls, aspect_ratio), timeout=20)
    if code == 200 and isinstance(body, dict) and body.get('usd'): return f"~${float(body['usd']):.3f}"
    return None


def submit(prompt, image_urls, aspect_ratio):
    """(ok, {'request_id', 'status_url'} or reason). One Idempotency-Key per intended image."""
    code, body = request('POST', '/' + model(), body_for(prompt, image_urls, aspect_ratio), headers={'Idempotency-Key': str(uuid.uuid4())})
    if code in (200, 201, 202) and isinstance(body, dict) and body.get('request_id'):
        return True, {'request_id': body['request_id'], 'status_url': body.get('status_url') or f"{BASE}/requests/{body['request_id']}/status"}
    return False, f'HTTP {code}: {body}'


def status(status_url):
    """('queued'|'in_progress'|'completed'|'failed'|'nsfw'|'canceled'|'error', image_url or message)."""
    code, body = request('GET', status_url)
    if code != 200 or not isinstance(body, dict): return 'error', f'HTTP {code}: {body}'
    s = body.get('status', 'error')
    if s == 'completed':
        images = body.get('images') or []
        return ('completed', images[0]['url']) if images else ('failed', 'No image in the result.')
    return s, body.get('error') or ''


def download(url):
    with urllib.request.urlopen(urllib.request.Request(url), timeout=60) as r:
        return r.read()


# ---------- Backgrounds for the automatic long detail page (README §34) ----------
BG_MODEL = 'xai/grok-imagine-image-2.0'   # text-to-image, 1.28 credits (~$0.08) per image at 2k / medium (Higgsfield estimate 2026-10-26)


def submit_model(model_id, prompt, aspect_ratio, image_urls=None):
    """Like submit() but for a given model in MODELS. (ok, {'request_id','status_url'} or reason)."""
    body = MODELS[model_id](prompt, image_urls or [], aspect_ratio)
    code, out = request('POST', '/' + model_id, body, headers={'Idempotency-Key': str(uuid.uuid4())})
    if code in (200, 201, 202) and isinstance(out, dict) and out.get('request_id'):
        return True, {'request_id': out['request_id'], 'status_url': out.get('status_url') or f"{BASE}/requests/{out['request_id']}/status"}
    return False, f'HTTP {code}: {out}'


_bg_estimate = {}


def bg_credits():
    """Credits per background image (Higgsfield estimate, cached; 1.28 if the estimate is unavailable)."""
    if 'credits' not in _bg_estimate:
        try:
            code, body = request('POST', f'/estimate/{BG_MODEL}', MODELS[BG_MODEL]('party background', [], '3:4'), timeout=15) if credentials() else (0, None)
            _bg_estimate['credits'] = float(body['credits']) if code == 200 else 1.28
        except Exception:  # estimate is only informational
            _bg_estimate['credits'] = 1.28
    return _bg_estimate['credits']
