from datetime import datetime, timezone
from core.extensions import db
class Message(db.Model):
    __tablename__='core_message'
    id=db.Column(db.Integer,primary_key=True)
    kind=db.Column(db.String(20),nullable=False)
    name=db.Column(db.String(100),nullable=False)
    email=db.Column(db.String(254),nullable=False)
    body=db.Column(db.Text,nullable=False)
    created_at=db.Column(db.DateTime,default=lambda:datetime.now(timezone.utc))
