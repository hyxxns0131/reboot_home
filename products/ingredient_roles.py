"""What each ingredient does, in plain words (README §28). Used to "analyze" a product's ingredient list on its detail page.
Keyword (lowercase, matched inside the ingredient name) -> (English, Korean). First match wins. Only neutral, factual roles —
never an effect on the body (compliance rules). Key ingredients are shown even before the full list is confirmed."""
KEY = ('hovenia', 'lactobacillus', 'a-hat')

ROLES = [
    ('a-hat', ("ALDICOM's blend of Hovenia dulcis extract and Lactobacillus fermentum, developed in Korea.",
               '헛개나무 추출물과 락토바실러스 퍼멘텀을 결합한 알디콤의 조성물이에요.')),
    ('hovenia', ('Fruit of the Oriental raisin tree, a familiar ingredient in Korea.', '한국에서 친숙한 헛개나무의 열매 원료예요.')),
    ('lactobacillus', ('A lactic acid bacterium. Part of the A-HAT blend.', '유산균 락토바실러스 퍼멘텀으로, A-HAT 조성물의 일부예요.')),
    ('sucralose', ('A high-intensity sweetener, used in tiny amounts.', '아주 적은 양으로 단맛을 내는 고감미 감미료예요.')),
    ('allulose', ('A rare sugar that gives sweetness in our Zero Sugar recipe.', '제로슈가 레시피에 단맛을 내는 희소당이에요.')),
    ('soluble fiber', ('Gives body and a soft texture.', '부드러운 식감과 바디감을 줘요.')),
    ('fructose', ('Fruit sugar for a clean sweetness.', '깔끔한 단맛을 내는 과당이에요.')),
    ('cane sugar', ('Classic sweetness.', '기본 단맛을 내요.')),
    ('tapioca syrup', ('Adds body and a soft chew.', '쫀득한 식감과 바디감을 더해요.')),
    ('glucose syrup', ('A classic candy syrup that keeps the chew soft.', '말랑한 식감을 지켜 주는 물엿이에요.')),
    ('sugar', ('Classic sweetness.', '기본 단맛을 내요.')),
    ('water', ('The base.', '기본 베이스예요.')),
    ('pectin', ('A fruit-derived gelling agent that makes the soft chew.', '과일에서 온 겔화제로 말랑한 식감을 만들어요.')),
    ('citric acid', ('Bright, citrusy tartness.', '상큼한 시트러스 산미를 내요.')),
    ('malic acid', ('Crisp, apple-like tartness.', '사과 같은 산뜻한 산미를 더해요.')),
    ('citrate', ('Rounds out the tartness.', '산미를 부드럽게 잡아줘요.')),
    ('stevia', ('Plant-based sweetener.', '식물 유래 감미료예요.')),
    ('monk fruit', ('Plant-based sweetener.', '식물 유래 감미료예요.')),
    ('natural flavor', ('Gives the lime, lemon and cherry taste.', '라임·레몬·체리 맛을 내요.')),
    ('colors', ('Colors from turmeric, spirulina and vegetable and fruit juice — no Red 3.', '강황·스피루리나·채소·과일즙에서 얻은 색이에요. 적색 3호는 쓰지 않아요.')),
    ('coconut oil', ('A light coating that keeps each piece from sticking.', '조각끼리 달라붙지 않게 하는 얇은 코팅이에요.')),
    ('lecithin', ('Keeps the texture smooth and even.', '식감을 매끄럽게 해요.')),
]


def role(name, lang):
    n = name.lower()
    for k, (en, ko) in ROLES:
        if k in n: return ko if lang == 'ko' else en
    return ''


def is_key(name):
    n = name.lower()
    return any(k in n for k in KEY)
