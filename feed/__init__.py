import re
from flask import Blueprint,render_template,abort
from core.content import ARTICLES,REELS
bp=Blueprint('feed',__name__,url_prefix='/feed')
REEL_URL=re.compile(r'^https?://(?:www\.)?instagram\.com/(reels?|p)/([A-Za-z0-9_-]+)')

def reel_embeds():
    # Only the type and shortcode are kept from each link, so every iframe points at Instagram's own embed page.
    # The plain /embed/ view has no caption; the card crops away the header, likes and comments (see .ig-card).
    return [dict(src=f"https://www.instagram.com/{'p' if m[1]=='p' else 'reel'}/{m[2]}/embed/",kind='post' if m[1]=='p' else 'reel') for m in map(REEL_URL.match,REELS) if m]

@bp.get('/')
def index(): return render_template('feed/index.html',articles=ARTICLES,reels=reel_embeds(),title='The Reboot edit')
@bp.get('/<slug>')
def article(slug):
    article=next((a for a in ARTICLES if a['slug']==slug),None)
    if not article: abort(404)
    return render_template('feed/article.html',article=article,title=article['title'])
