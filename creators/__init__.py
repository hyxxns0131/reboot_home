from flask import Blueprint,render_template,request,flash,redirect
from core.extensions import db
from core.messages import Message
bp=Blueprint('creators',__name__,url_prefix='/creators')
@bp.route('/',methods=['GET','POST'])
def index():
    if request.method=='POST':
        name=request.form.get('name','').strip(); email=request.form.get('email','').strip(); body=request.form.get('message','').strip()
        if not name or len(name)>100 or '@' not in email or len(email)>254 or not body or len(body)>4000:
            flash('Please enter your name, a valid email, and a message (up to 4,000 characters).','error')
        else:
            db.session.add(Message(kind='creators',name=name,email=email,body=body)); db.session.commit()
            flash('Thank you. Your message has been saved for the team.')
            return redirect('/creators/')
    return render_template('contact/form.html',kind='creators',title='Make something worth sharing.')
