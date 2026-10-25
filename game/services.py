"""Reboot Town rules: score -> points, plausibility checks and the daily cap.

Scores come from the browser, so the server never trusts them blindly:
- a run must be started on the server first (start time is the server's clock),
- the score must be reachable in the elapsed time (max_rate per second + slack),
- one run pays at most RUN_CAP points, one customer earns at most DAILY_CAP points per UTC day.
"""
from datetime import datetime, timedelta, timezone

DAILY_CAP = 1000          # points per customer per UTC day, all games together
RUN_CAP = 300             # points per single run
RUN_TTL = timedelta(minutes=20)
MAX_RUNS_PER_DAY = 300
POINTS_PER_USD = 100

# per: score units for one payout step, points: points per step
GAMES = {
    'lasso-leap': dict(name='Lasso Leap', village='jelly', unit='gates', per=1, points=10,
                       rule='1 gate = 10 P', max_rate=2.0, slack=3, max_score=600, min_seconds=0),
    'jelly-drop': dict(name='Jelly Drop', village='jelly', unit='pts', per=1, points=3,
                       rule='1 pt = 3 P', max_rate=7.0, slack=10, max_score=3000, min_seconds=0),
    'bottle-pop': dict(name='Bottle Pop', village='drink', unit='pts', per=1, points=5,
                       rule='1 pt = 5 P', max_rate=4.0, slack=6, max_score=200, min_seconds=28),
    'sunrise-flight': dict(name='Sunrise Flight', village='drink', unit='m', per=5, points=1,
                           rule='5 m = 1 P', max_rate=22.0, slack=60, max_score=60000, min_seconds=0),
}


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def today():
    return utcnow().date()


def reset_at():
    return (datetime.combine(today(), datetime.min.time()) + timedelta(days=1)).isoformat() + 'Z'


def points_for(game, score):
    g = GAMES[game]
    return min(RUN_CAP, (score // g['per']) * g['points'])


def plausible(game, score, elapsed_seconds):
    g = GAMES[game]
    if elapsed_seconds < g['min_seconds']:
        return False
    return 0 <= score <= g['max_score'] and score <= g['max_rate'] * elapsed_seconds + g['slack']
