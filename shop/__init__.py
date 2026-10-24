import secrets
from flask import Blueprint, render_template, request, session, redirect, flash, abort
from flask_login import current_user
from auth.decorators import customer_required
from core.extensions import db
from shop.models import ProductOption, Order
from auth.models import User
from rewards.models import CartItem, PointEntry, CheckoutReceipt
from rewards.services import record
from sqlalchemy.exc import IntegrityError
from shop.services import cart_lines, totals, referral as active_referral, create_order

bp=Blueprint('shop',__name__,url_prefix='/shop')
@bp.get('/')
def index():
    return redirect('/products/')

@bp.route('/cart',methods=['GET','POST'])
@customer_required
def cart():
    if request.method=='POST':
        sku=request.form.get('sku','')
        option=db.session.scalar(db.select(ProductOption).filter_by(sku=sku,is_active=True))
        if not option or not option.product.is_active: abort(400)
        try: qty=int(request.form.get('quantity','1'))
        except ValueError: abort(400)
        if not 0<=qty<=10: abort(400)
        row=db.session.scalar(db.select(CartItem).filter_by(user_id=current_user.id,option_id=option.id))
        if qty:
            if row: row.quantity=qty
            else: db.session.add(CartItem(user_id=current_user.id,option_id=option.id,quantity=qty))
        elif row: db.session.delete(row)
        record('cart_updated',{'sku':sku,'quantity':qty})
        db.session.commit()
        session.pop('checkout_nonce',None)
        flash('Your bag has been updated.')
        return redirect('/shop/cart')
    lines=cart_lines()
    return render_template('shop/cart.html',title='Your bag',lines=lines,totals=totals(lines,active_referral()))

@bp.route('/checkout',methods=['GET','POST'])
@customer_required
def checkout():
    lines=cart_lines()
    if not lines: return redirect('/shop/cart')
    link=active_referral()
    if request.method=='POST':
        if not session.get('checkout_nonce') or request.form.get('nonce')!=session.pop('checkout_nonce'): abort(400)
        name=request.form.get('name','').strip(); city=request.form.get('city','').strip(); state=request.form.get('state','').strip().upper()
        if not name or len(name)>100 or not city or len(city)>100 or state not in 'AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC'.split():
            flash('Enter your name, city, and a valid two-letter US state.', 'error')
        else:
            try:
                points=int(request.form.get('points','0'))
            except ValueError:
                points=-1
            maximum=min(current_user.points,int(totals(lines,link)[2]*100))
            if points<0 or points>maximum:
                flash('Enter a valid points amount within your balance and order total.', 'error')
            else:
                try:
                    receipt=CheckoutReceipt(token=request.form['nonce'],user_id=current_user.id)
                    db.session.add(receipt)
                    db.session.flush()
                    if points:
                        result=db.session.execute(db.update(User).where(User.id==current_user.id,User.points>=points).values(points=User.points-points))
                        if result.rowcount!=1:
                            db.session.rollback()
                            abort(409)
                    order=create_order(lines,link,points_used=points,user_id=current_user.id,ship_name=name,ship_city=city,ship_state=state)
                    db.session.flush()
                    receipt.order_id=order.id
                    if points:
                        db.session.add(PointEntry(user_id=current_user.id,amount=-points,reason='order_payment',reference=f'order:{order.id}',order_id=order.id))
                    db.session.execute(db.delete(CartItem).where(CartItem.user_id==current_user.id))
                    record('order_placed',{'order_id':order.id,'points_used':points,'total_usd':str(order.total)})
                    db.session.commit()
                    flash('Your mock order is confirmed. No payment was taken.')
                    return redirect('/shop/orders')
                except IntegrityError:
                    db.session.rollback()
                    flash('This order has already been processed.')
                    return redirect('/shop/orders')
    session['checkout_nonce']=secrets.token_urlsafe(24)
    return render_template('shop/checkout.html',title='One more step',totals=totals(lines,link),link=link,max_points=min(current_user.points,int(totals(lines,link)[2]*100)))

@bp.get('/orders')
@customer_required
def orders():
    orders=db.session.scalars(db.select(Order).filter_by(user_id=current_user.id).order_by(Order.ordered_at.desc())).all()
    return render_template('shop/orders.html',title='Your orders',orders=orders)
