"""Sample reviews for the launch products (README §34). Fictional reviewers, shown on the site with a "Sample review" tag.
Each product has its own copy (taste, shapes, pack, bottle) and only 4–5 stars: average above 4.8, all positive.
Copy follows the compliance rules: no health, body or hangover claims."""
from datetime import datetime

R = lambda name, rating, date, title, body: dict(name=name, rating=rating, date=date, title=title, body=body)

SAMPLES = {
    'jelly-original': [
        R('Ava M.', 5, '2026-08-14', 'The cowboy boots are everything', 'Brought a pouch to a birthday dinner and the lime boots were gone first. Bright, tangy and super cute.'),
        R('Marcus T.', 5, '2026-08-22', 'Lasso shape = lemon, genius', 'I love that the shape tells you the flavor. Lemon lasso is my favorite, really bright and not too sweet.'),
        R('Jenna K.', 5, '2026-08-30', 'Party bag staple now', 'Ten individually wrapped pieces fit perfectly in my clutch. Shared them at the club and everyone asked where they were from.'),
        R('Diego R.', 5, '2026-09-05', 'Cherry hat is so good', 'Deep cherry flavor and a soft chew. The pink cowboy hats look great on a snack board too.'),
        R('Priya S.', 4, '2026-09-11', 'Fun and tasty', 'Love the flavors and the wrapping. I just wish the pouch had a zip so I could reseal it.'),
        R('Tyler B.', 5, '2026-09-18', 'Tailgate win', 'Passed the pouch around at a tailgate. Lime and cherry disappeared fast. Ordering two next time.'),
        R('Hannah L.', 5, '2026-09-24', 'Bold colors, bold flavor', 'The colors are so vivid in person. Each piece is wrapped so nothing gets sticky in my bag.'),
        R('Kevin O.', 5, '2026-09-30', 'K-snack find of the year', 'Saw this Korean brand on TikTok and finally tried it. Chewy, fruity and the shapes are hilarious.'),
        R('Sofia G.', 5, '2026-10-06', 'Bachelorette favor hit', 'Put one pouch on every seat at a bachelorette dinner. The cowboy theme matched perfectly.'),
        R('Liam W.', 5, '2026-10-12', 'Love the lime boot', 'Lime is tart and fresh, exactly how I like it. Packaging looks premium for the price.'),
        R('Chloe P.', 5, '2026-10-17', 'Gift-worthy', 'Gave a pouch to my roommate for her birthday and she loved the little hats and lassos.'),
        R('Noah S.', 5, '2026-10-21', 'Already on my second pouch', 'All three flavors are good but cherry is the one I fight my friends for. Shipping was quick too.'),
    ],
    'jelly-balance': [
        R('Emma C.', 5, '2026-08-17', 'Same shapes, lighter colors', 'The pastel boots and hats are adorable. Lime is crisp and the texture is just as chewy as Original.'),
        R('Jordan K.', 5, '2026-08-25', 'My go-to pouch', 'I keep a Balance pouch in my jacket for nights out. Ten wrapped pieces is the right amount to share.'),
        R('Mia L.', 5, '2026-09-02', 'Lemon lasso is so fresh', 'Light, clean lemon flavor. Not sugary tasting at all, which is exactly what I wanted.'),
        R('Ethan R.', 5, '2026-09-09', 'Great for game night', 'Brought these to game night and the cowboy hats were a hit. Everyone guessed the flavor by the shape.'),
        R('Grace Y.', 4, '2026-09-15', 'Really good', 'Cherry and lime are great. Lemon is a little milder than I expected but still tasty.'),
        R('Lucas W.', 5, '2026-09-21', 'Cute and tasty', 'The soft green boot looks like candy art. Tastes bright and fruity. Will buy again.'),
        R('Zoe H.', 5, '2026-09-28', 'Rooftop party favorite', 'Shared a pouch at a rooftop party and it was gone in ten minutes. Love the individual wrappers.'),
        R('Aiden F.', 5, '2026-10-04', 'Perfect sweetness', 'Sweet enough to enjoy but light. Balance is now my default pick.'),
        R('Lily D.', 5, '2026-10-10', 'Pretty packaging', 'The pouch looks great on a party table and the pastel colors photograph really well.'),
        R('Ryan O.', 5, '2026-10-16', 'Better than I hoped', 'I was not sure what to expect from Balance but the flavor is spot on. Cherry is my favorite.'),
        R('Nora J.', 5, '2026-10-22', 'Bag essential', 'Fits in my smallest bag and nothing melts or sticks. Lime boot forever.'),
    ],
    'drink-original': [
        R('Caleb V.', 5, '2026-08-12', 'Tiny bottle, big flavor', 'The 100 ml glass bottle is so cute and the lime is zesty and smooth. Perfect to grab on the way out.'),
        R('Isabella F.', 5, '2026-08-20', 'Mixed Box is the move', 'Got the Mixed Box to try all three. Lemon is bright, cherry is rich, lime is crisp. Love them all.'),
        R('Dylan Q.', 5, '2026-08-28', 'Cherry is so good', 'Deep cherry flavor without being syrupy. I keep one chilled in the fridge before going out.'),
        R('Olivia N.', 5, '2026-09-03', 'Looks great at parties', 'Lined up the three colors on our bar cart for a house party and guests loved the bottles.'),
        R('Mason B.', 4, '2026-09-10', 'Tasty, wish it was bigger', 'Great taste and nice glass bottle. I would happily buy a bigger size too.'),
        R('Ella J.', 5, '2026-09-16', 'Pocket sized', 'Fits in my jacket pocket for concerts. Lemon is refreshing and not too sweet.'),
        R('Ben A.', 5, '2026-09-23', 'Non-carbonated and smooth', 'I like that it is not fizzy. Easy to sip and the lime has a nice tang.'),
        R('Camila R.', 5, '2026-09-29', 'Birthday table hit', 'Ordered two Mixed Boxes for my birthday and set them out on ice. Everyone wanted the cherry.'),
        R('Henry Z.', 5, '2026-10-05', 'Premium feel', 'The glass bottle and label feel premium. Great little thing to bring to a friend’s place.'),
        R('Avery P.', 5, '2026-10-11', 'Lemon all day', 'Lemon is my favorite. Clean, bright and really easy to drink chilled.'),
        R('Logan M.', 5, '2026-10-18', 'Fun Korean find', 'Never tried a Korean party drink like this before. Fun bottle, great flavors, quick delivery.'),
        R('Harper S.', 5, '2026-10-23', 'Restocking already', 'Finished my Mixed Box in a weekend of get-togethers. Buying the lime singles next.'),
    ],
    'drink-balance': [
        R('Scarlett T.', 5, '2026-08-15', 'Light and bright', 'The lemon Balance is crisp and clean. Love the small glass bottle for nights out.'),
        R('Jack D.', 5, '2026-08-23', 'Balance done right', 'Tastes fresh, not artificial. Lime is my favorite and it is great chilled.'),
        R('Aria K.', 5, '2026-08-31', 'Mixed Box for the win', 'Tried all three in the Mixed Box. Cherry surprised me, really smooth and fruity.'),
        R('Owen G.', 5, '2026-09-07', 'Perfect pre-party bottle', 'I grab one while getting ready and the bottle fits right in my pocket.'),
        R('Luna H.', 4, '2026-09-13', 'Really nice', 'Great flavor and cute bottle. Lime is a little lighter than Original but I like it.'),
        R('Wyatt E.', 5, '2026-09-19', 'Clean taste', 'Not too sweet and no fizz, which I prefer. The lemon is super refreshing.'),
        R('Chloe A.', 5, '2026-09-26', 'House party staple', 'Set out a Mixed Box on ice at our house party. The pastel bottles looked amazing.'),
        R('Elijah N.', 5, '2026-10-02', 'Go-to order', 'I reorder the lime singles every couple of weeks. Easy to sip, great quality.'),
        R('Penelope W.', 5, '2026-10-08', 'Love the bottle design', 'Minimal label, small glass bottle, bright flavors. Feels like a premium little treat.'),
        R('Sebastian L.', 5, '2026-10-14', 'Cherry is underrated', 'Everyone talks about lime but the cherry Balance is so good. Smooth and fruity.'),
        R('Victoria C.', 5, '2026-10-20', 'Great for concerts', 'Tossed one in my bag for a concert and it was the perfect size. Will keep buying.'),
        R('Mateo F.', 5, '2026-10-24', 'Shared with friends', 'Shared a Mixed Box at a birthday and now my friends are ordering their own.'),
    ],
}


def seed_sample_reviews():
    """Replace the old random dummy reviews with these samples, product by product, once (idempotent; customers' reviews are kept)."""
    from core.extensions import db
    from products.models import Review
    from products.reviews import sentiment_for
    from shop.models import Product
    for slug, items in SAMPLES.items():
        product = db.session.scalar(db.select(Product).filter_by(slug=slug))
        if not product: continue
        dummy = db.session.scalars(db.select(Review).filter_by(product_id=product.id, is_dummy=True)).all()
        if sorted((r.reviewer_name, r.title) for r in dummy) == sorted((x['name'], x['title']) for x in items): continue
        for r in dummy: db.session.delete(r)
        db.session.flush()
        for i, x in enumerate(items):
            db.session.add(Review(product_id=product.id, reviewer_name=x['name'], rating=x['rating'], title=x['title'], body=x['body'],
                                  sentiment=sentiment_for(x['rating']), status='published', is_dummy=True,
                                  created_at=datetime.fromisoformat(x['date']).replace(hour=12 + i % 10, minute=(i * 7) % 60)))
