"""Read-only data API for the marketing dashboard (README §39).

GET /api/export/<kind>.csv?start=YYYY-MM-DD&end=YYYY-MM-DD   header  Authorization: Bearer <EXPORT_API_TOKEN>
Same files and column names as Admin › /admin/export/<kind>.csv, without an admin login. The token lives only in the server's
environment (Render › Environment › EXPORT_API_TOKEN, local .env); with no token set the API is off (503).
"""
import hmac
import os
from flask import Blueprint, request, jsonify, abort

bp = Blueprint('export_api', __name__, url_prefix='/api/export')
KINDS = ('creator-performance', 'influencer-orders', 'influencer-sales', 'orders', 'direct-orders', 'reviews', 'review-summary',
         'product-sales', 'option-sales', 'link-sales', 'inventory', 'chatbot-questions', 'creator-visits', 'inbox')


def token_ok():
    expected = (os.getenv('EXPORT_API_TOKEN') or '').strip()
    if not expected: abort(503)
    header = request.headers.get('Authorization', '')
    given = header[7:].strip() if header[:7].lower() == 'bearer ' else ''
    return bool(given) and hmac.compare_digest(given.encode(), expected.encode())


@bp.errorhandler(503)
def off(e):
    return jsonify(error='Export API is off: set EXPORT_API_TOKEN on the server.'), 503


@bp.get('/')
def index():
    if not token_ok(): return jsonify(error='Missing or wrong token.'), 401, {'WWW-Authenticate': 'Bearer'}
    return jsonify(files=[f'/api/export/{k}.csv' for k in KINDS], params='start, end (YYYY-MM-DD); status for order files; platform for influencer files; sentiment for reviews')


@bp.get('/<kind>.csv')
def export(kind):
    if not token_ok(): return jsonify(error='Missing or wrong token.'), 401, {'WWW-Authenticate': 'Bearer'}
    if kind not in KINDS: return jsonify(error=f'Unknown file. Choose one of: {", ".join(KINDS)}'), 404
    from admin import export_payload, csv_response
    from werkzeug.exceptions import HTTPException
    try:
        return csv_response(*export_payload(kind))
    except HTTPException as e:
        return jsonify(error=e.description or e.name), e.code
