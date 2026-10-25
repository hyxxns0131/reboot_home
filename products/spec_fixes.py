"""Copy fixes from the REBOOT spec & ingredient sheet (internal draft 2026-10-25, README §33).
Exact old sentence -> new sentence. Applied to the launch seed and, once at startup, to long pages already saved in the
database (only exact matches change, so pages an admin rewrote keep their own words)."""
FIXES = [
    # A-HAT: never "patented" in advertising
    ('Every Reboot product is made with A-HAT, ALDICOM’s patented blend, and Hovenia dulcis fruit.',
     'Every Reboot product is made with A-HAT, ALDICOM’s blend of Hovenia dulcis extract and Lactobacillus fermentum.'),
    ('모든 리부트 제품은 알디콤의 특허 조성물 A-HAT과 헛개나무 열매로 만들어요.',
     '모든 리부트 제품은 헛개나무 추출물과 락토바실러스 퍼멘텀을 결합한 알디콤의 조성물 A-HAT으로 만들어요.'),
    ("ALDICOM's patented blend of Hovenia dulcis extract and Lactobacillus fermentum, developed in Korea.",
     "ALDICOM's blend of Hovenia dulcis extract and Lactobacillus fermentum, developed in Korea."),
    ('헛개나무 추출물과 락토바실러스 퍼멘텀을 결합한 알디콤의 특허 조성물이에요.', '헛개나무 추출물과 락토바실러스 퍼멘텀을 결합한 알디콤의 조성물이에요.'),
    ('A lactic acid bacterium, heat-treated. Part of the A-HAT blend.', 'A lactic acid bacterium. Part of the A-HAT blend.'),
    ('열처리한 락토바실러스 퍼멘텀으로, A-HAT 조성물의 일부예요.', '유산균 락토바실러스 퍼멘텀으로, A-HAT 조성물의 일부예요.'),
    # 10 jellies per pouch
    ('Individually wrapped jellies', '10 individually wrapped jellies'),
    ('개별 포장 젤리', '개별 포장 젤리 10개'),
    ('Lime, lemon and cherry jellies, each individually wrapped, in one line package made for nights out.',
     '10 lime, lemon and cherry jellies, each individually wrapped, in one line package made for nights out.'),
    ('개별 포장한 라임·레몬·체리 젤리를 한 봉지에 담은, 밤 외출을 위한 라인 패키지예요.',
     '개별 포장한 라임·레몬·체리 젤리 10개를 한 봉지에 담은, 밤 외출을 위한 라인 패키지예요.'),
    ('The Zero Sugar version of our line package: lime, lemon and cherry jellies, individually wrapped, in one pouch.',
     'The Zero Sugar version of our line package: 10 lime, lemon and cherry jellies, individually wrapped, in one pouch. Not a low calorie food.'),
    ('라인 패키지의 제로슈가 버전. 개별 포장한 라임·레몬·체리 젤리를 한 봉지에 담았어요.',
     '라인 패키지의 제로슈가 버전. 개별 포장한 라임·레몬·체리 젤리 10개를 한 봉지에 담았어요. 저칼로리 식품은 아니에요.'),
    # Zero Sugar always with "Not a low calorie food"
    ('Zero Sugar', 'Zero Sugar · Not a low calorie food'),          # highlight chip (whole string only)
    ('제로슈가', '제로슈가 · 저칼로리 식품 아님'),
    ('Yes. Balance is the Zero Sugar version of each Reboot line.',
     'Yes. Balance is the Zero Sugar version of each Reboot line. It is not a low calorie food.'),
    ('네. 밸런스는 각 리부트 라인의 제로슈가 버전이에요.', '네. 밸런스는 각 리부트 라인의 제로슈가 버전이에요. 저칼로리 식품은 아니에요.'),
    ('The Zero Sugar version of our non-carbonated drink, in a 100 ml (3.4 fl oz) glass bottle.',
     'The Zero Sugar version of our non-carbonated drink, in a 100 ml (3.4 fl oz) glass bottle. Not a low calorie food.'),
    ('100ml(3.4 fl oz) 유리병에 담은 비탄산 음료의 제로슈가 버전이에요.', '100ml(3.4 fl oz) 유리병에 담은 비탄산 음료의 제로슈가 버전이에요. 저칼로리 식품은 아니에요.'),
    ('Balance is the Zero Sugar version of each Reboot line. Original is the classic version.',
     'Balance is the Zero Sugar version of each Reboot line (not a low calorie food). Original is the classic version.'),
    ('밸런스는 각 리부트 라인의 제로슈가 버전이에요. 오리지널은 기본 버전이에요.', '밸런스는 각 리부트 라인의 제로슈가 버전이에요(저칼로리 식품은 아님). 오리지널은 기본 버전이에요.'),
    ('Reboot Jelly Balance. The party essential from Korea.', 'Reboot Jelly Balance. The party essential from Korea. Not a low calorie food.'),
    ('Reboot Drink Balance. The party essential from Korea.', 'Reboot Drink Balance. The party essential from Korea. Not a low calorie food.'),
    ('리부트 젤리 밸런스. 한국에서 온 파티 필수품.', '리부트 젤리 밸런스. 한국에서 온 파티 필수품. 저칼로리 식품은 아니에요.'),
    ('리부트 드링크 밸런스. 한국에서 온 파티 필수품.', '리부트 드링크 밸런스. 한국에서 온 파티 필수품. 저칼로리 식품은 아니에요.'),
]
WHOLE_ONLY = {'Zero Sugar', '제로슈가', 'Individually wrapped jellies', '개별 포장 젤리'}
_MAP = dict(FIXES)


def fix_text(s):
    if not isinstance(s, str): return s
    if s in _MAP: return _MAP[s]
    for old, new in FIXES:
        if old not in WHOLE_ONLY and old in s and new not in s: s = s.replace(old, new)
    return s


def fix(value):
    """Walk a page (dicts/lists) and apply the fixes; returns a new value."""
    if isinstance(value, dict): return {fix_text(k) if isinstance(k, str) and k in _MAP else k: fix(v) for k, v in value.items()}
    if isinstance(value, list): return [fix(v) for v in value]
    return fix_text(value)
