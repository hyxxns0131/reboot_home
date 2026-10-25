"""Product reviews: validation, sentiment, display summary and dummy seed."""
import random
import re
from datetime import datetime, timedelta
from core.extensions import db
from products.models import Review

# README §20: these claims must not appear anywhere on the site, including customer reviews.
# A review that uses them is still saved (and exported) but held back from the product page.
HELD_TERMS = ('hangover', 'cure', 'remedy', 'prevent', 'relieve', 'heal', 'detox', 'sober', 'flush')


def sentiment_for(rating):
    """4–5 stars = positive, 3 = neutral, 1–2 = negative."""
    return 'positive' if rating >= 4 else 'negative' if rating <= 2 else 'neutral'


def needs_hold(*texts):
    text = ' '.join(texts).lower()
    return any(re.search(r'\b' + term, text) for term in HELD_TERMS)


def summary(product_id):
    rows = db.session.execute(db.select(Review.rating, db.func.count()).filter_by(product_id=product_id, status='published').group_by(Review.rating)).all()
    count = sum(n for _, n in rows)
    average = round(sum(r * n for r, n in rows) / count, 1) if count else 0
    return dict(count=count, average=average, stars={r: n for r, n in rows})


def latest(product_id, limit=20):
    return db.session.scalars(db.select(Review).filter_by(product_id=product_id, status='published').order_by(Review.created_at.desc(), Review.id.desc()).limit(limit)).all()


# ---------- dummy reviews (fictional reviewers, compliant copy only) ----------
NAMES = ['Ava M.', 'Jordan K.', 'Mia L.', 'Ethan R.', 'Chloe P.', 'Noah S.', 'Sofia G.', 'Liam T.', 'Zoe H.', 'Lucas W.', 'Emma C.', 'Mason B.', 'Lily D.', 'Aiden F.', 'Grace Y.', 'Ryan O.', 'Nora J.', 'Caleb V.', 'Hannah N.', 'Dylan Q.']
COPY = {
    'positive': [
        ('Love the flavors', 'The lime and cherry are my favorites. Bright, fun and easy to keep in my bag.'),
        ('New go-to', 'Great taste and the cowboy shapes are so cute. My friends keep asking where I got it.'),
        ('Really tasty', 'Smooth, not too sweet, and the little bottle looks great on my shelf.'),
        ('Fun packaging', 'The design is playful and the flavors are spot on. Ordering again.'),
        ('Perfect size', 'Small enough to carry anywhere. The lemon is super refreshing.'),
        ('Worth trying', 'I was curious about this Korean brand and it did not disappoint. Tastes great.'),
    ],
    'neutral': [
        ('It is okay', 'Decent taste. I liked the cherry more than the lemon.'),
        ('Not bad', 'Nice flavors but I wish there were more pieces in the package.'),
        ('Average', 'Pretty good, packaging is fun. Price feels a little high for the size.'),
    ],
    'negative': [
        ('Too sweet for me', 'The flavor was stronger than I expected. Not for me.'),
        ('Shipping took long', 'Product was fine but it took a long time to arrive.'),
        ('Package arrived dented', 'One of the boxes was damaged in shipping. Taste was okay.'),
        ('Not my flavor', 'I did not enjoy the lemon. Might try the lime next time.'),
    ],
}


def seed_dummy_reviews(products, per_product=110, seed=7):
    """Each product gets per_product reviews between 2026-01-01 and 2026-10-22 (≈70% positive, 15% neutral, 15% negative)."""
    rng = random.Random(seed)
    days = [datetime(2026, 1, 1) + timedelta(days=i) for i in range(295)]
    counts = {}
    for product in products:
        for i in range(per_product):
            rating = rng.choices([5, 4, 3, 2, 1], weights=[45, 25, 15, 9, 6])[0]
            mood = sentiment_for(rating)
            title, body = rng.choice(COPY[mood])
            db.session.add(Review(product_id=product.id, reviewer_name=rng.choice(NAMES), rating=rating, title=title, body=body, sentiment=mood, status='published', is_dummy=True,
                                  created_at=rng.choice(days) + timedelta(hours=rng.randint(9, 23), minutes=rng.randint(0, 59))))
            counts[(product.id, mood)] = counts.get((product.id, mood), 0) + 1
    assert all(counts.get((p.id, 'positive'), 0) > 0 and counts.get((p.id, 'negative'), 0) > 0 for p in products)
