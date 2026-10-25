from flask import Blueprint,render_template,request,flash,redirect
from flask_login import current_user
from core.extensions import db
from core.messages import Message, TOPICS
from rewards.services import record
bp=Blueprint('contact',__name__,url_prefix='/contact')


@bp.route('/',methods=['GET','POST'])
def index():
    """Members send inquiries straight to the admin inbox. Their name and account email are attached
    automatically, and the team's reply shows up here under "Your inquiries"."""
    member=current_user.is_authenticated and current_user.role=='customer'
    orders=[]
    if member:
        from shop.models import Order
        orders=db.session.scalars(db.select(Order).filter_by(user_id=current_user.id).order_by(Order.id.desc()).limit(20)).all()
    if request.method=='POST':
        if not member:
            flash('Please log in to send an inquiry.','error'); return redirect('/auth/login?next=/contact/')
        topic=request.form.get('topic',''); body=request.form.get('message','').strip()
        try: order_id=int(request.form.get('order') or 0) or None
        except ValueError: order_id=None
        if order_id and order_id not in {o.id for o in orders}: order_id=None
        if topic not in TOPICS or not 10<=len(body)<=4000:
            flash('Choose a topic and write a message (10–4,000 characters).','error')
        else:
            db.session.add(Message(kind='contact',name=current_user.name[:100],email=current_user.email,user_id=current_user.id,topic=topic,order_id=order_id,body=body,status='new'))
            record('contact_submitted',{'topic':topic}); db.session.commit()
            flash('Your inquiry was sent to our team. You will see the reply on this page.')
            return redirect('/contact/#inquiries')
    mine=db.session.scalars(db.select(Message).filter_by(kind='contact',user_id=current_user.id).order_by(Message.id.desc())).all() if member else []
    return render_template('contact/form.html',kind='contact',title='Let’s talk.',topics=TOPICS,orders=orders,mine=mine,member=member)
