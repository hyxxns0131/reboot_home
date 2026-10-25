"""What visitors ask Ask Reboot: topic tagging, counts and the AI analysis report (README §25)."""
import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from core.extensions import db
from support.models import ChatQuestion, ChatInsight

# (key, English label, Korean label, keywords). First match wins, so specific topics come first.
TOPICS = [
    ('health', 'Health effects & hangovers', '건강 효과 · 숙취',
     ['hangover', 'hungover', 'effect', 'night out', 'should i take', 'liver', 'safe to', 'before drinking', 'after drinking', 'alcohol', 'headache', 'detox', '숙취', '효과', '간 건강', '술 마시']),
    ('age', 'Age & who can buy', '연령 · 구매 자격',
     ['21', '19', '18', 'years old', 'age', 'under ', 'kid', 'teen', 'pregnan', '나이', '미성년', '임산부']),
    ('shipping', 'Shipping, orders & refunds', '배송 · 주문 · 환불',
     ['ship', 'deliver', 'arrive', 'track', 'refund', 'return', 'cancel', 'my order', 'damaged', '배송', '환불', '취소', '반품']),
    ('codes', 'Creator codes & discounts', '크리에이터 코드 · 할인 코드',
     ['code', 'coupon', 'promo', 'creator', 'influencer', 'tiktok', 'instagram', '코드', '쿠폰']),
    ('points', 'Points & Reboot Town game', '포인트 · 게임',
     ['point', 'reward', 'game', 'reboot town', 'lasso leap', 'jelly drop', '포인트', '게임']),
    ('where', 'Where to buy (stores & retailers)', '구매처 · 매장',
     ['amazon', 'weee', 'olive young', 'store', 'retail', 'near me', 'target', 'walmart', 'in person', '매장', '아마존', '어디서']),
    ('price', 'Price & sales', '가격 · 할인',
     ['price', 'cost', 'how much', 'expensive', '$', 'sale', 'discount', 'cheap', 'deal', '가격', '얼마', '할인']),
    ('ingredients', 'Ingredients, sugar & nutrition', '성분 · 당류 · 영양',
     ['ingredient', 'a-hat', 'hovenia', 'sugar', 'calorie', 'allergen', 'vegan', 'gluten', 'nutrition', 'caffeine', 'gelatin', 'halal', 'kosher', '성분', '설탕', '칼로리', '알레르기', '젤라틴']),
    ('package', 'Packs & sizes (line packages, box of 3)', '구성 · 용량 (라인 패키지 · 3병 박스)',
     ['single', 'individual', 'only the', 'how big', 'size', 'bottle', 'pouch', 'pieces', 'how many', 'package', 'pack', 'box', 'ml', 'bottle size', 'one flavor', 'just lime', 'just cherry', 'just lemon', '낱개', '봉지', '개수', '박스', '용량']),
    ('buying', 'Buying on the site & account', '사이트 구매 · 계정',
     ['buy', 'order', 'checkout', 'cart', 'bag', 'purchase', 'account', 'sign up', 'login', 'log in', 'pay', '구매', '주문', '결제', '회원', '로그인']),
    ('flavors', 'Flavors, taste & shapes', '맛 · 모양',
     ['flavor', 'flavour', 'taste', 'lime', 'lemon', 'cherry', 'shape', 'boot', 'hat', 'lasso', 'sweet', 'sour', 'original', 'balance', 'difference', '맛', '모양', '차이']),
    ('other', 'Other', '기타', []),
]
TOPIC_KEYS = [t[0] for t in TOPICS]
LABELS = {t[0]: (t[1], t[2]) for t in TOPICS}
PERIODS = (7, 30, 90)
_EMAIL = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
_PHONE = re.compile(r'(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)')


def mask(text):
    """Questions are stored without contact details."""
    return _PHONE.sub('[phone]', _EMAIL.sub('[email]', text))


def _pattern(word):
    # English words match from a word start ("hat" must not match "what", "boot" not "reboot"); Korean and symbols match anywhere.
    return re.compile((r'\b' if word[0].isascii() and word[0].isalnum() else '') + re.escape(word.strip()))


_MATCHERS = [(key, [_pattern(w) for w in words]) for key, _, _, words in TOPICS]


def topic_of(question):
    q = question.lower()
    for key, patterns in _MATCHERS:
        if any(p.search(q) for p in patterns):
            return key
    return 'other'


def save_question(question, reply, lang, visitor, log):
    db.session.add(ChatQuestion(question=mask(question)[:1000], language=lang, visitor=visitor, topic=topic_of(question),
                                reply=reply, verdict=log['verdict'], codes=','.join(log['codes'])[:80],
                                action=log['action'], flagged_reply=log['flagged_reply']))


def period_query(days):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    return db.select(ChatQuestion).filter(ChatQuestion.created_at >= since, ChatQuestion.visitor != 'admin')


def overview(days):
    rows = db.session.scalars(period_query(days).order_by(ChatQuestion.created_at.desc())).all()
    counts = Counter(r.topic for r in rows)
    total = len(rows)
    topics = [dict(key=k, label=LABELS[k][0], label_ko=LABELS[k][1], count=counts[k], pct=round(100 * counts[k] / total) if total else 0,
                   examples=list(dict.fromkeys(r.question for r in rows if r.topic == k))[:3])
              for k in sorted(TOPIC_KEYS, key=lambda k: (-counts[k], TOPIC_KEYS.index(k))) if counts[k]]
    guard = Counter(r.action for r in rows)
    return dict(days=days, total=total, sample=sum(r.is_dummy for r in rows), topics=topics,
                rewritten=guard['rewritten'], blocked=guard['blocked'],
                reviewed=sum(1 for r in rows if r.verdict == 'REVIEW'),
                recent=rows[:60], flagged=[r for r in rows if r.action != 'passed'][:30])


# ---------- AI analysis ----------
MAX_QUESTIONS = 300
SYSTEM = """You analyse questions that US visitors asked "Ask Reboot", the customer-care chatbot on the US website of Reboot
(a Korean company's line of jelly and drink products for adults 21+; jelly is sold only as a line package, drinks as single bottles or a box of 3).
The reader is the Korean overseas marketing manager who runs the site. Write every value in Korean, plain sentences, no markdown.
You get topic counts (already computed, do not change them) and the questions themselves (contact details masked).

Return one JSON object exactly like this:
{"summary": "3 sentences: what visitors want to know most, what changed or stands out, the one thing to do first",
 "topics": [{"key": "<a topic key from the counts>", "insight": "what exactly people want to know about this topic, 1-2 sentences",
             "examples": ["up to 2 representative questions, short, in the visitors' own language"],
             "action": "one concrete change to the site, product page, FAQ, chatbot or marketing"}],
 "gaps": [{"need": "something visitors ask that the site or chatbot cannot answer yet", "action": "what to add"}],
 "risk": "1-2 sentences on health / hangover / age questions and how to keep answers compliant (no health claims, 21+)"}
Include the 5 largest topics in "topics" (fewer if there are fewer), largest first. "gaps": 0-3 items.
Never suggest making hangover, health or medical claims."""


def build_request(days):
    rows = db.session.scalars(period_query(days).order_by(ChatQuestion.created_at.desc()).limit(MAX_QUESTIONS)).all()
    data = overview(days)
    counts = '\n'.join(f"- {t['key']} ({t['label']}): {t['count']} ({t['pct']}%)" for t in data['topics'])
    questions = '\n'.join(f'[{r.topic}] {r.question[:300]}' for r in rows)
    user = f"Period: last {days} days. Questions: {data['total']} (showing the latest {len(rows)}).\nTopic counts:\n{counts}\n\nQuestions:\n{questions}"
    return rows, user


def clean(result, valid_keys):
    """Keep only the fields the page shows, as plain strings."""
    if not isinstance(result, dict):
        raise ValueError('not an object')
    s = lambda v, n=400: str(v or '').strip()[:n]
    topics = []
    for t in result.get('topics') or []:
        if isinstance(t, dict) and t.get('key') in valid_keys:
            topics.append(dict(key=t['key'], label=LABELS[t['key']][1], insight=s(t.get('insight')), action=s(t.get('action')),
                               examples=[s(e, 160) for e in (t.get('examples') or [])[:2] if s(e)]))
    gaps = [dict(need=s(g.get('need')), action=s(g.get('action'))) for g in (result.get('gaps') or [])[:3] if isinstance(g, dict) and s(g.get('need'))]
    if not s(result.get('summary')) and not topics:
        raise ValueError('empty analysis')
    return dict(summary=s(result.get('summary'), 800), topics=topics[:6], gaps=gaps, risk=s(result.get('risk'), 500))


def run_analysis(days):
    """Returns (ok, ChatInsight | readable error)."""
    from support import call_openai, chat_config
    rows, user = build_request(days)
    if not rows:
        return False, 'No questions in this period yet.'
    ok, text = call_openai(SYSTEM, [{'role': 'user', 'content': user}], max_tokens=1400, json_mode=True)
    if not ok:
        return False, text
    try:
        result = clean(json.loads(text), {t['key'] for t in overview(days)['topics']})
    except (ValueError, TypeError, AttributeError):
        return False, 'The AI answer could not be read. Please run the analysis again.'
    report = ChatInsight(days=days, question_count=len(rows), model=chat_config()['model'], result=json.dumps(result, ensure_ascii=False))
    db.session.add(report)
    db.session.commit()
    return True, report


def latest_report(days):
    report = db.session.scalar(db.select(ChatInsight).filter_by(days=days).order_by(ChatInsight.id.desc()).limit(1))
    if not report:
        return None
    return dict(created_at=report.created_at, question_count=report.question_count, model=report.model, **json.loads(report.result))
