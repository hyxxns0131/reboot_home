"""Sample Ask Reboot questions so the Chatbot questions page has data before real visitors arrive (README §25).
All rows are is_dummy=True and written by us — no real visitors."""
import random
from datetime import datetime, timedelta, timezone
from core.extensions import db
from support.models import ChatQuestion
from support.insights import topic_of
from support.guard import SAFE_REPLY

SAMPLES = {  # topic: (how many, questions)
    'flavors': (28, ['Which flavor is the most popular?', 'What does the cherry one taste like?', "What's the difference between Original and Balance?",
                     'Is the lime jelly sour?', 'Which shape is lemon?', 'Is Balance less sweet than Original?', 'Does the cherry drink taste like cough syrup?',
                     'What flavors does the drink come in?', 'Why is the jelly shaped like a cowboy boot?']),
    'package': (24, ['Can I buy only the lime jelly?', 'How many jellies are in one pouch?', 'Do you sell single jelly pieces?',
                     'How big is the drink bottle?', "What's in the box of 3?", 'Can I get a jelly pouch with just cherry?',
                     'Is the Mixed Box one of each flavor?', 'Can I choose 3 lemon drinks in a box?']),
    'health': (22, ['Does it actually work for hangovers?', 'Should I take it before or after drinking?', 'Is it safe to take with alcohol?',
                    'Will this help my headache tomorrow?', 'Is it good for my liver?', 'How many should I take on a night out?',
                    '숙취에 효과 있어요?', 'Does it lower blood alcohol?']),
    'where': (18, ['Is Reboot on Amazon?', 'Can I buy it at a store near me in LA?', 'Do you sell at Olive Young?', 'Is it at Target or Walmart?',
                   'Where can I buy it in New York in person?', 'Is the Amazon price the same as the site?']),
    'price': (16, ['How much is the jelly?', 'Are there any sales right now?', 'Is the box of 3 cheaper than single bottles?',
                   'Why is Balance more expensive?', 'Any discount for first order?']),
    'ingredients': (16, ['What is A-HAT?', 'How many calories are in the drink?', 'Is the jelly vegan?', 'Does the jelly have gelatin?',
                         'Is Balance really zero sugar?', 'Any allergens I should know about?', 'Is there caffeine in it?', 'Is it gluten free?']),
    'shipping': (14, ['How long does shipping take to Texas?', 'Can I track my order?', 'Do you ship to Hawaii?', 'How do I get a refund?',
                      'My order arrived damaged, what do I do?', 'Can I cancel my order?']),
    'buying': (10, ['Do I need an account to buy?', 'How do I checkout?', 'Can I pay with Apple Pay?', 'I forgot my password, how do I log in?']),
    'codes': (8, ['Where do I enter a creator code?', 'Can I use two promo codes?', 'I got a code from TikTok, does it work on sale items?']),
    'points': (8, ['How do I earn points?', 'How many points do I get per game?', 'Do points expire?', 'What is Reboot Town?']),
    'age': (4, ['Can I buy this if I am 19?', 'Is it ok for teens?', 'Can I take it while pregnant?']),
    'other': (6, ['Who is Rebu?', 'Are you a real person?', 'Is ALDICOM a Korean company?', 'Do you have a song?']),
}
REPLY = {
    'flavors': 'Howdy! Jelly comes as a line package with all three shapes: lime is the boot, lemon the lasso and cherry the hat. Balance is the Zero Sugar version.',
    'package': 'Jelly is sold only as a line package — one pouch with all three flavors. Drinks come as single 100 ml bottles or a Mixed Box of 3.',
    'health': SAFE_REPLY['en'],
    'where': 'You can buy on this site or from our retail partners listed on the Where to Buy page. Availability can differ by store.',
    'price': 'Prices are on each product page, and any running sales are shown there too.',
    'ingredients': 'Every Reboot product is made with A-HAT and Hovenia dulcis fruit. Nutrition details are on the label photos; for anything else, the Contact page can help.',
    'shipping': "I don't have shipping times to share. For orders, refunds or damaged items, please use the Contact page (/contact/).",
    'buying': 'Create an account (21+), pick an option on the product page, add it to your bag and check out.',
    'codes': 'Open the creator link or type the code in your bag. One code per order, and it works on top of sale prices.',
    'points': 'Play the mini games in Reboot Town (/game/). Signed-in members earn up to 300 points a game and 1,000 a day. 100 points = $1 off.',
    'age': 'Reboot is for adults 21+ only.',
    'other': "I'm Rebu, Reboot's mascot — and an AI assistant, not a human. Happy to help with products, points or where to buy!",
}
FLAGGED = 'Reboot is made to help you bounce back from a hangover, so take it before you go to sleep.'


def seed_dummy_chats():
    if db.session.scalar(db.select(ChatQuestion).filter_by(is_dummy=True).limit(1)):
        return
    rng = random.Random(25)
    now = datetime.now(timezone.utc)
    rows = []
    for topic, (count, questions) in SAMPLES.items():
        for i in range(count):
            q = questions[i % len(questions)]
            assert topic_of(q) == topic, (topic, q)
            # Recent weeks are busier, so the 7-day view is not empty.
            when = now - timedelta(days=min(rng.expovariate(1 / 18), 85), hours=rng.randint(0, 23), minutes=rng.randint(0, 59))
            row = ChatQuestion(question=q, language='ko' if any('가' <= c <= '힣' for c in q) else 'en', visitor=rng.choice(['guest', 'guest', 'customer']),
                               topic=topic, reply=REPLY[topic], created_at=when, is_dummy=True)
            if topic == 'health':
                row.verdict, row.codes = 'BLOCK', 'R1,R2'
                row.action = 'blocked' if i % 3 == 0 else 'rewritten'
                row.flagged_reply = FLAGGED
                if row.action == 'blocked' and row.language == 'ko':
                    row.reply = SAFE_REPLY['ko']
            elif topic == 'ingredients' and i % 2 == 0:
                row.verdict, row.codes = 'REVIEW', 'R13'
            rows.append(row)
    db.session.add_all(rows)
