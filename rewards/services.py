from flask_login import current_user
from core.extensions import db
from rewards.models import Activity

def record(action, details=None, user_id=None):
    uid = user_id or (current_user.id if current_user.is_authenticated else None)
    if uid:
        db.session.add(Activity(user_id=uid, action=action, details=details or {}))
