from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import current_user
from sqlalchemy.exc import IntegrityError
from core.extensions import db
from auth.models import User
from auth.decorators import customer_required
from products.services import get_all_products, image_url
from rewards.models import PointEntry
from rewards.services import record
from game.models import GameRun, GameDaily
from game.services import (GAMES, DAILY_CAP, RUN_CAP, RUN_TTL, MAX_RUNS_PER_DAY, POINTS_PER_USD,
                           utcnow, today, reset_at, points_for, plausible)

bp = Blueprint('game', __name__, url_prefix='/game')


def today_earned(user_id):
    return db.session.scalar(db.select(GameDaily.earned).filter_by(user_id=user_id, day=today())) or 0


def best_scores(user_id):
    rows = db.session.execute(db.select(GameRun.game, db.func.max(GameRun.score))
                              .filter_by(user_id=user_id, status='finished').group_by(GameRun.game)).all()
    return {game: score for game, score in rows if score is not None}


def status(user_id):
    return dict(today_earned=today_earned(user_id), daily_cap=DAILY_CAP, run_cap=RUN_CAP,
                balance=db.session.get(User, user_id).points, reset_at=reset_at(), best=best_scores(user_id))


def award(user_id, wanted):
    """Add up to `wanted` points without passing DAILY_CAP, safe against parallel finishes."""
    day = today()
    for _ in range(4):
        row = db.session.scalar(db.select(GameDaily).filter_by(user_id=user_id, day=day))
        if row is None:
            try:
                with db.session.begin_nested():
                    db.session.add(GameDaily(user_id=user_id, day=day, earned=0))
            except IntegrityError:
                pass
            continue
        earned = row.earned
        give = min(wanted, DAILY_CAP - earned)
        if give <= 0:
            return 0
        result = db.session.execute(db.update(GameDaily).where(GameDaily.id == row.id, GameDaily.earned == earned)
                                    .values(earned=earned + give), execution_options={'synchronize_session': False})
        if result.rowcount == 1:
            db.session.execute(db.update(User).where(User.id == user_id).values(points=User.points + give))
            return give
        db.session.expire(row)
    return 0


def catalog():
    """Products shown in the village stores (same data as /products/)."""
    items = []
    for p in get_all_products():
        options = sorted(p['options'], key=lambda o: o['price_usd'])
        items.append(dict(slug=p['slug'], name=p['name'], line=p['line'], balance=p.get('is_balance', False),
                          image=image_url(p['images'].get('main')), flavors=p['flavors'],
                          options=[dict(label=o['label'], price=o['price_usd']) for o in options]))
    return items


def play_context():
    """Everything game/_play.html needs (the /game/ page and the home page both show the game)."""
    customer = current_user.is_authenticated and current_user.role == 'customer'
    return dict(games=GAMES, game_products=catalog(), daily_cap=DAILY_CAP, run_cap=RUN_CAP,
                points_per_usd=POINTS_PER_USD, game_status=status(current_user.id) if customer else None)


@bp.get('/')
def index():
    return render_template('game/index.html', title='Reboot Town', **play_context())


@bp.get('/api/status')
@customer_required
def api_status():
    return jsonify(status(current_user.id))


@bp.post('/api/runs')
@customer_required
def start_run():
    game = (request.get_json(silent=True) or {}).get('game')
    if game not in GAMES:
        abort(400)
    runs_today = db.session.scalar(db.select(db.func.count(GameRun.id)).filter_by(user_id=current_user.id, day=today()))
    if runs_today >= MAX_RUNS_PER_DAY:
        return jsonify(error='Daily play limit reached. Come back tomorrow.'), 429
    run = GameRun(user_id=current_user.id, game=game, day=today(), started_at=utcnow())
    db.session.add(run)
    db.session.flush()
    record('game_started', {'game': game, 'run_id': run.id})
    db.session.commit()
    return jsonify(run_id=run.id, **status(current_user.id))


@bp.post('/api/runs/<int:run_id>/finish')
@customer_required
def finish_run(run_id):
    score = (request.get_json(silent=True) or {}).get('score')
    if type(score) is not int or score < 0:
        abort(400)
    run = db.session.scalar(db.select(GameRun).filter_by(id=run_id, user_id=current_user.id))
    if not run:
        abort(404)
    if run.status != 'open':
        return jsonify(error='This run is already finished.'), 409
    now = utcnow()
    elapsed = (now - run.started_at).total_seconds()
    if elapsed > RUN_TTL.total_seconds():
        new_status, possible = 'expired', 0
    elif not plausible(run.game, score, elapsed):
        new_status, possible = 'rejected', 0
    else:
        new_status, possible = 'finished', points_for(run.game, score)
    closed = db.session.execute(db.update(GameRun).where(GameRun.id == run.id, GameRun.status == 'open')
                                .values(status=new_status, score=score, finished_at=now),
                                execution_options={'synchronize_session': False})
    if closed.rowcount != 1:
        db.session.rollback()
        return jsonify(error='This run is already finished.'), 409
    earned = award(current_user.id, possible) if possible else 0
    if earned:
        db.session.execute(db.update(GameRun).where(GameRun.id == run.id).values(points=earned))
        db.session.add(PointEntry(user_id=current_user.id, amount=earned, reason='game_reward', reference=f'game_run:{run.id}'))
    record('game_completed', {'game': run.game, 'run_id': run.id, 'score': score, 'points': earned, 'status': new_status})
    db.session.commit()
    db.session.expire_all()
    message = {'expired': 'This run took too long, so no points were added.',
               'rejected': 'We could not verify this score, so no points were added.'}.get(new_status)
    return jsonify(run_status=new_status, score=score, points_possible=possible, points_earned=earned,
                   message=message, **status(current_user.id))
