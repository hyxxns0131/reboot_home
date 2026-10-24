import re
from flask import Blueprint,render_template,abort
from core.content import ARTICLES,REELS
bp=Blueprint('feed',__name__,url_prefix='/feed')
REEL_URL=re.compile(r'^https?://(?:www\.)?instagram\.com/(?:reels?|p)/([A-Za-z0-9_-]+)')

def reel_embeds():
    # Only the shortcode is kept from each link, so every iframe points at Instagram's own embed page.
    return [f'https://www.instagram.com/reel/{m[1]}/embed/' for m in map(REEL_URL.match,REELS) if m]

@bp.get('/')
def index(): return render_template('feed/index.html',articles=ARTICLES,reels=reel_embeds(),title='The Reboot edit')
@bp.get('/<slug>')
def article(slug):
    article=next((a for a in ARTICLES if a['slug']==slug),None)
    if not article: abort(404)
    return render_template('feed/article.html',article=article,title=article['title'])
