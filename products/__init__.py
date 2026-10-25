from flask import Blueprint, render_template, abort, request, redirect, flash
from flask_login import current_user
from sqlalchemy.exc import IntegrityError
from auth.decorators import customer_required
from core.extensions import db
from products.services import get_all_products, get_product
from products.models import Review  # noqa: F401  (registers products_review table)
from products import reviews as review_service

bp=Blueprint('products',__name__,url_prefix='/products')


@bp.record_once
def ensure_review_table(state):
    """Create products_review on startup if an older local DB doesn't have it yet (additive, never drops data)."""
    with state.app.app_context():
        Review.__table__.create(db.engine, checkfirst=True)


def shop_product(slug):
    from shop.models import Product
    return db.session.scalar(db.select(Product).filter_by(slug=slug))


@bp.get('/')
def index(): return render_template('products/index.html',products=get_all_products(),title='Find your Reboot')


@bp.get('/<slug>')
def detail(slug):
    product=get_product(slug)
    if not product: abort(404)
    row=shop_product(slug)
    mine=None
    if row and current_user.is_authenticated and current_user.role=='customer':
        mine=db.session.scalar(db.select(Review).filter_by(product_id=row.id,user_id=current_user.id))
    return render_template('products/detail.html',p=product,title=product['name'],
                           review_summary=review_service.summary(row.id) if row else dict(count=0,average=0,stars={}),
                           reviews=review_service.latest(row.id) if row else [],my_review=mine)


@bp.post('/<slug>/reviews')
@customer_required
def add_review(slug):
    row=shop_product(slug)
    if not row or not get_product(slug): abort(404)
    back=f'/products/{slug}#reviews'
    try: rating=int(request.form.get('rating',''))
    except ValueError: rating=0
    title=request.form.get('title','').strip(); body=request.form.get('body','').strip()
    if not 1<=rating<=5 or len(title)>100 or not 10<=len(body)<=1000:
        flash('Choose 1–5 stars and write 10–1,000 characters.','error'); return redirect(back)
    if db.session.scalar(db.select(Review).filter_by(product_id=row.id,user_id=current_user.id)):
        flash('You have already reviewed this product.','error'); return redirect(back)
    held=review_service.needs_hold(title,body)
    db.session.add(Review(product_id=row.id,user_id=current_user.id,reviewer_name=current_user.name[:60],rating=rating,title=title,body=body,
                          sentiment=review_service.sentiment_for(rating),status='held' if held else 'published'))
    from rewards.services import record
    record('review_posted',{'product':slug,'rating':rating})
    try: db.session.commit()
    except IntegrityError:
        db.session.rollback(); flash('You have already reviewed this product.','error'); return redirect(back)
    flash('Thanks! Your review is pending a quick check.' if held else 'Thanks! Your review is live.')
    return redirect(back)


@bp.post('/<slug>/reviews/delete')
@customer_required
def delete_review(slug):
    """A customer removes their own review (other people's reviews can't be touched)."""
    row=shop_product(slug)
    if not row or not get_product(slug): abort(404)
    mine=db.session.scalar(db.select(Review).filter_by(product_id=row.id,user_id=current_user.id))
    if mine:
        db.session.delete(mine)
        from rewards.services import record
        record('review_deleted',{'product':slug})
        db.session.commit()
        flash('Your review has been deleted.')
    return redirect(f'/products/{slug}#reviews')
