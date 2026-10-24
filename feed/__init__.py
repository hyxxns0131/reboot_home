from flask import Blueprint,render_template,abort
from core.content import ARTICLES
bp=Blueprint('feed',__name__,url_prefix='/feed')
@bp.get('/')
def index(): return render_template('feed/index.html',articles=ARTICLES,title='The Reboot edit')
@bp.get('/<slug>')
def article(slug):
    article=next((a for a in ARTICLES if a['slug']==slug),None)
    if not article: abort(404)
    return render_template('feed/article.html',article=article,title=article['title'])
