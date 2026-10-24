import json
import os
import time
import urllib.error
import urllib.request
from flask import Blueprint, request, jsonify, session, abort, current_app
from core.extensions import db
from core.i18n import language
from products.services import get_all_products
from rewards.services import record
from where_to_buy import RETAILERS

bp = Blueprint('support', __name__, url_prefix='/support')
API_URL = 'https://api.openai.com/v1/chat/completions'
LIMIT, WINDOW = 20, 600  # messages per browser session per 10 minutes, to cap API spend

def system_prompt():
    products = '\n'.join(f"- {p['name']} ({p['format']}; {p['pack']}): flavors {', '.join(p['flavors'])}; "
                         + ', '.join(f"{o['label']} ${o['price_usd']:.2f}" for o in p['options']) for p in get_all_products())
    return f"""You are the customer support assistant on the official website of Reboot, a US line by the Korean company ALDICOM.
Reply briefly and kindly in {'Korean' if language() == 'ko' else 'English'}, unless the customer writes in another language.
Products (sample prices; flavors and prices are not final):
{products}
Retail partners: {', '.join(f'{name} ({url})' for name, url in RETAILERS)}. The site's own shop is a mock checkout and takes no real payment.
Points: signed-in customers earn 100 points once a day from the card game at /rewards/. 100 points = $1 at checkout.
Rules: the products are for adults 21+. Never make health, medical, hangover, or sugar claims, and never promise effects.
If you don't know something, say so instead of guessing. For orders, refunds, partnerships, or anything you can't resolve,
point to the contact form at /contact/ (signed-in customers see their orders at /shop/orders).
Never ask for passwords or payment card details."""

@bp.post('/chat')
def chat():
    history = (request.get_json(silent=True) or {}).get('messages')
    if not isinstance(history, list) or not 0 < len(history) <= 20: abort(400)
    messages = []
    for m in history[-10:]:
        if not isinstance(m, dict) or m.get('role') not in ('user', 'assistant') or not isinstance(m.get('content'), str): abort(400)
        content = m['content'].strip()
        if not 0 < len(content) <= 1000: abort(400)
        messages.append({'role': m['role'], 'content': content})
    if messages[-1]['role'] != 'user': abort(400)
    key = os.getenv('OPENAI_API_KEY')
    if not key: return jsonify(error='unavailable'), 503
    now = time.time()
    recent = [t for t in session.get('chat_times', []) if now - t < WINDOW]
    if len(recent) >= LIMIT: return jsonify(error='rate_limited'), 429
    session['chat_times'] = recent + [now]
    body = json.dumps({'model': os.getenv('OPENAI_MODEL') or 'gpt-4o-mini', 'max_completion_tokens': 500,
                       'messages': [{'role': 'system', 'content': system_prompt()}] + messages}).encode()
    upstream = urllib.request.Request(API_URL, data=body, headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(upstream, timeout=25) as response:
            reply = json.load(response)['choices'][0]['message']['content'].strip()
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, TypeError, ValueError, AttributeError):
        current_app.logger.exception('Support chat request failed')
        return jsonify(error='upstream'), 502
    record('support_chat', {'chars': len(messages[-1]['content'])})
    db.session.commit()
    return jsonify(reply=reply)
