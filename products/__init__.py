from flask import Blueprint,render_template,abort
from products.services import get_all_products,get_product
bp=Blueprint('products',__name__,url_prefix='/products')
@bp.get('/')
def index(): return render_template('products/index.html',products=get_all_products(),title='Find your Reboot')
@bp.get('/<slug>')
def detail(slug):
    product=get_product(slug)
    if not product: abort(404)
    return render_template('products/detail.html',p=product,title=product['name'])
