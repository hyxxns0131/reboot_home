import secrets
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import current_user
from sqlalchemy.exc import IntegrityError
from core.extensions import db
from auth.models import User
from auth.decorators import customer_required
from rewards.models import Game, PointEntry, Activity
from rewards.services import record

bp = Blueprint('rewards', __name__, url_prefix='/rewards')
DAILY_POINTS = 100

def state(game):
    return dict(id=game.id, day=game.day.isoformat(), matched=game.matched, first=game.first,
                first_face=game.board[game.first] if game.first is not None else None,
                faces={str(i):game.board[i] for i in game.matched}, moves=game.moves,
                complete=game.complete, version=game.version, reward=DAILY_POINTS,
                balance=db.session.get(User,current_user.id).points)

@bp.get('/')
def index():
    return render_template('rewards/game.html', title='Play. Match. Earn.')

@bp.post('/start')
@customer_required
def start():
    day=datetime.now(timezone.utc).date()
    game=db.session.scalar(db.select(Game).filter_by(user_id=current_user.id,day=day))
    if not game:
        board=list(range(6))*2
        secrets.SystemRandom().shuffle(board)
        game=Game(user_id=current_user.id,day=day,board=board,matched=[])
        db.session.add(game)
        try:
            db.session.flush()
            record('game_started',{'game_id':game.id})
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            game=db.session.scalar(db.select(Game).filter_by(user_id=current_user.id,day=day))
    return jsonify(state(game))

@bp.post('/flip')
@customer_required
def flip():
    data=request.get_json(silent=True) or {}
    if any(type(data.get(k)) is not int for k in ('id','index','version')): abort(400)
    game=db.session.scalar(db.select(Game).filter_by(id=data['id'],user_id=current_user.id))
    if not game: abort(404)
    index=data['index']
    if game.day!=datetime.now(timezone.utc).date(): return jsonify(error='A new day has started. Start a new game.'),409
    if game.complete: return jsonify(state(game))
    if not 0<=index<12 or index in game.matched or index==game.first: abort(400)
    if data['version']!=game.version: return jsonify(error='The board changed. Resume your game.'),409
    matched=list(game.matched); first=game.first; moves=game.moves
    face=game.board[index]; pair=None
    if first is None:
        first=index
    else:
        pair=[first,index]; moves+=1
        if game.board[first]==face: matched.extend(pair)
        first=None
    complete=len(matched)==12
    updated=db.session.execute(db.update(Game).where(Game.id==game.id,Game.version==data['version'],Game.complete.is_(False)).values(first=first,matched=matched,moves=moves,version=data['version']+1,complete=complete,completed_at=datetime.now(timezone.utc) if complete else None),execution_options={'synchronize_session':False})
    if updated.rowcount!=1:
        db.session.rollback()
        return jsonify(error='The board changed. Resume your game.'),409
    if complete:
        db.session.add(PointEntry(user_id=current_user.id,amount=DAILY_POINTS,reason='game_reward',reference=f'game:{game.id}'))
        db.session.execute(db.update(User).where(User.id==current_user.id).values(points=User.points+DAILY_POINTS))
        record('game_completed',{'game_id':game.id,'moves':moves,'points':DAILY_POINTS})
    db.session.commit()
    db.session.expire_all()
    response=state(db.session.get(Game,game.id)); response.update(flipped=index,face=face,pair=pair)
    return jsonify(response)

@bp.get('/wallet')
@customer_required
def wallet():
    entries=db.session.scalars(db.select(PointEntry).filter_by(user_id=current_user.id).order_by(PointEntry.id.desc()).limit(100)).all()
    activities=db.session.scalars(db.select(Activity).filter_by(user_id=current_user.id).order_by(Activity.id.desc()).limit(100)).all()
    return render_template('rewards/wallet.html',title='Your points & activity',entries=entries,activities=activities)
