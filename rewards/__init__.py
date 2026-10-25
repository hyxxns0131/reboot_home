from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user
from core.extensions import db
from auth.decorators import customer_required
from rewards.models import PointEntry, Activity

bp = Blueprint('rewards', __name__, url_prefix='/rewards')


@bp.get('/')
def index():
    # The daily memory card game moved to Reboot Town (/game/).
    return redirect(url_for('game.index'), 301)


@bp.get('/wallet')
@customer_required
def wallet():
    entries=db.session.scalars(db.select(PointEntry).filter_by(user_id=current_user.id).order_by(PointEntry.id.desc()).limit(100)).all()
    activities=db.session.scalars(db.select(Activity).filter_by(user_id=current_user.id).order_by(Activity.id.desc()).limit(100)).all()
    return render_template('rewards/wallet.html',title='Your points & activity',entries=entries,activities=activities)
