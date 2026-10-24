from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import current_user, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy.exc import IntegrityError
from core.extensions import db
from auth.models import User
from rewards.services import record

bp = Blueprint('auth', __name__, url_prefix='/auth')

def safe_next(value):
    return value if value and value.startswith('/') and not value.startswith('//') and '\\' not in value and not any(ord(c)<32 for c in value) else None

@bp.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        user = db.session.scalar(db.select(User).filter_by(email=request.form.get('email','').strip().lower()))
        if user and check_password_hash(user.password_hash, request.form.get('password','')):
            language=session.get('lang',user.language)
            session.clear()
            session['lang']=language
            user.language=language
            record('login',user_id=user.id)
            db.session.commit()
            login_user(user, remember=request.form.get('remember') == 'on')
            return redirect(safe_next(request.args.get('next')) or ('/admin/' if user.role == 'admin' else '/'))
        if user:
            record('login_failed',user_id=user.id)
            db.session.commit()
        flash('Email or password is incorrect.', 'error')
    return render_template('auth/form.html', mode='login', title='Welcome back')

@bp.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        email=request.form.get('email','').strip().lower()
        password=request.form.get('password','')
        name=request.form.get('name','').strip()
        if not name or len(name)>100 or '@' not in email or len(email)>254 or len(password)<8 or password!=request.form.get('confirm') or not request.form.get('adult'):
            flash('Complete every field, confirm your password (8+ characters), and confirm you are 21+.', 'error')
        else:
            user=User(email=email, name=name, password_hash=generate_password_hash(password, method="pbkdf2:sha256:1000000"), role='customer')
            db.session.add(user)
            try:
                db.session.commit()
                language=session.get('lang','en')
                session.clear()
                session['lang']=language
                user.language=language
                record('registered',user_id=user.id)
                db.session.commit()
                login_user(user)
                return redirect(safe_next(request.args.get('next')) or '/')
            except IntegrityError:
                db.session.rollback()
                flash('This email is already registered.', 'error')
    return render_template('auth/form.html', mode='register', title='Join the restart')

@bp.route('/logout', methods=['GET','POST'])
def logout():
    if request.method == 'POST':
        language=session.get('lang','en')
        record('logout')
        db.session.commit()
        logout_user()
        session.clear()
        session['lang']=language
        session['_remember'] = 'clear'
        return render_template('auth/logout.html', done=True, title='See you next time')
    return render_template('auth/logout.html', done=not current_user.is_authenticated, title='See you next time')
