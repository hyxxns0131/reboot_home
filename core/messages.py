from datetime import datetime, timezone
from core.extensions import db

TOPICS = ('Order', 'Product', 'Account & points', 'Partnership', 'Other')


class Message(db.Model):
    """Contact inquiries (signed-in members, sent straight to the admin inbox) and Creators applications."""
    __tablename__='core_message'
    id=db.Column(db.Integer,primary_key=True)
    kind=db.Column(db.String(20),nullable=False)          # contact / creators
    name=db.Column(db.String(100),nullable=False)
    email=db.Column(db.String(254),nullable=False)        # contact: the member's account email (filled in automatically)
    body=db.Column(db.Text,nullable=False)
    created_at=db.Column(db.DateTime,default=lambda:datetime.now(timezone.utc))
    user_id=db.Column(db.Integer,db.ForeignKey('auth_user.id'))
    topic=db.Column(db.String(30),nullable=False,default='')
    order_id=db.Column(db.Integer)
    status=db.Column(db.String(12),nullable=False,default='new')  # new / read / answered
    reply=db.Column(db.Text)
    replied_at=db.Column(db.DateTime)
