from flask import Blueprint,render_template
from products.services import get_all_products
from core.content import ARTICLES
bp=Blueprint('main',__name__)
@bp.get('/')
def home():
    return render_template('main/home.html',products=get_all_products(),articles=ARTICLES,title='Restart your day')
