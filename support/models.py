"""Ask Reboot question log and AI analysis reports (README §25). Tables use the support_ prefix."""
from datetime import datetime, timezone
from core.extensions import db


class ChatQuestion(db.Model):
    """One visitor question to the chatbot. No account id is kept: only the question, its topic and what the guard did."""
    __tablename__ = 'support_chat_question'
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)
    question = db.Column(db.Text, nullable=False)          # emails / phone numbers masked before saving
    language = db.Column(db.String(2), nullable=False, default='en')
    visitor = db.Column(db.String(10), nullable=False, default='guest')  # guest · customer · admin (admin tests are left out of analysis)
    topic = db.Column(db.String(30), nullable=False, default='other', index=True)
    reply = db.Column(db.Text, nullable=False, default='')  # what the visitor actually saw
    verdict = db.Column(db.String(10), nullable=False, default='PASS')  # compliance verdict of the first draft answer
    codes = db.Column(db.String(80), nullable=False, default='')
    action = db.Column(db.String(10), nullable=False, default='passed')  # passed · rewritten · blocked
    flagged_reply = db.Column(db.Text, nullable=False, default='')  # first draft, kept only when it was stopped
    is_dummy = db.Column(db.Boolean, nullable=False, default=False)


class ChatInsight(db.Model):
    """One AI analysis run on the question log."""
    __tablename__ = 'support_chat_insight'
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    days = db.Column(db.Integer, nullable=False)
    question_count = db.Column(db.Integer, nullable=False)
    model = db.Column(db.String(60), nullable=False, default='')
    result = db.Column(db.Text, nullable=False)  # JSON from the model, validated in support.insights
