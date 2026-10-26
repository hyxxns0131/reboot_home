"""Long detail pages for the four launch products (README §28). Position: the party essential (adults 21+).
Hand-written, checked against the compliance rules in tests. Images are the existing product photos until AI panels replace them."""
W = 'product_image/web/'

OCC = {
    'jelly': {
        'en': [('Getting ready', 'Drop a pouch in your bag while you pick the outfit.'),
               ('Birthdays & toasts', 'Pass the shapes around the table. Everyone grabs a favorite.'),
               ('Club & bar nights', 'Individually wrapped and small enough for a clutch or jacket pocket.'),
               ('House parties & tailgates', 'Set a pouch next to the snacks and let friends help themselves.')],
        'ko': [('외출 준비', '옷 고르면서 가방에 한 봉지 챙기세요.'),
               ('생일 · 건배하는 자리', '테이블에 돌리면 다들 좋아하는 모양을 하나씩 집어 가요.'),
               ('클럽 · 바', '개별 포장이라 작은 가방이나 재킷 주머니에도 쏙.'),
               ('홈파티 · 테일게이트', '간식 옆에 한 봉지 두면 친구들이 알아서 꺼내 먹어요.')]},
    'drink': {
        'en': [('Getting ready', 'Chill a bottle while you get dressed and head out.'),
               ('Birthdays & toasts', 'Line up lemon, lime and cherry for the whole table.'),
               ('Club & bar nights', 'A 100 ml bottle fits in a jacket pocket or a small bag.'),
               ('House parties & tailgates', 'Keep a Mixed Box in the cooler for the crew.')],
        'ko': [('외출 준비', '옷 입는 동안 한 병 차갑게 두고 바로 출발.'),
               ('생일 · 건배하는 자리', '레몬·라임·체리를 테이블에 나란히 세워 보세요.'),
               ('클럽 · 바', '100ml 병이라 재킷 주머니나 작은 가방에 쏙.'),
               ('홈파티 · 테일게이트', '아이스박스에 믹스 박스 하나 넣어 두면 끝.')]},
}
FAQ_AGE = {'en': ('Who is Reboot for?', 'Reboot is a general food product for adults 21 and over.'),
           'ko': ('누가 먹을 수 있나요?', '리부트는 만 21세 이상 성인을 위한 일반식품이에요.')}
ING = {
    'en': {'title': "What's inside", 'intro': 'Every Reboot product is made with A-HAT, ALDICOM’s blend of Hovenia dulcis extract and Lactobacillus fermentum.',
           'note': 'The full ingredient list and nutrition facts are printed on the package label.'},
    'ko': {'title': '성분 분석', 'intro': '모든 리부트 제품은 헛개나무 추출물과 락토바실러스 퍼멘텀을 결합한 알디콤의 조성물 A-HAT으로 만들어요.',
           'note': '전체 원재료와 영양성분은 패키지 라벨에 표시돼 있어요.'},
}


def page(kind, lang, hero, sections, highlights, how, faq, closing):
    return {'hero': dict(zip(('kicker', 'headline', 'subhead'), hero)),
            'occasions': {'title': 'Made for every party' if lang == 'en' else '모든 파티의 필수품',
                          'items': [{'title': t, 'body': b} for t, b in OCC[kind][lang]]},
            'sections': [{'title': t, 'body': b} for t, b in sections],
            'highlights': highlights, 'ingredients': dict(ING[lang]), 'how_to_enjoy': how,
            'faq': [{'q': q, 'a': a} for q, a in faq + [FAQ_AGE[lang]]],
            'closing': dict(zip(('headline', 'subhead'), closing))}


SEED = {}
SEED['jelly-original'] = {
    'images': {'hero': W + 'jelly-original-scene-wide.webp', 'occasions': W + 'jelly-original-scene.webp', 'closing': W + 'jelly-original-package.webp',
               'sections': [W + 'jelly-original-mix.webp', W + 'jelly-original-lime.webp', W + 'jelly-original-package.webp']},
    'en': page('jelly', 'en', ('THE PARTY ESSENTIAL · 21+', 'Three shapes. One pouch. Party ready.', '10 lime, lemon and cherry jellies, each individually wrapped, in one line package made for nights out.'),
               [('Shape = flavor', 'Lime is the cowboy boot, lemon is the lasso and cherry is the cowboy hat. Original comes in deep, bold colors you can spot across the table.'),
                ('Wrapped for the night', 'Every jelly is individually wrapped, so one pouch works for the whole group, from the pre-party to the last song.'),
                ('One pouch, all three', 'Reboot Jelly is sold only as a line package. Every pouch holds all three shapes and flavors.')],
               ['10 individually wrapped jellies', 'Lime · Lemon · Cherry in every pouch', 'Bold Original colors', 'Made by ALDICOM in Korea'],
               ['Pack a pouch before you head out.', 'Share the shapes with the table.', 'Keep one in your bag for the ride home.'],
               [('Can I buy just one flavor?', 'No. Jelly comes only as a line package with all three shapes and flavors in one pouch.'),
                ('What is the difference between Original and Balance?', 'Original is the classic recipe with deeper colors. Balance is the Zero Sugar version with lighter colors.')],
               ('Don’t head out without it.', 'Reboot Jelly Original. The party essential from Korea.')),
    'ko': page('jelly', 'ko', ('파티 필수품 · 21+', '세 가지 모양, 한 봉지. 파티 준비 끝.', '개별 포장한 라임·레몬·체리 젤리 10개를 한 봉지에 담은, 밤 외출을 위한 라인 패키지예요.'),
               [('모양이 곧 맛', '라임은 카우보이 부츠, 레몬은 올가미, 체리는 카우보이 모자. 오리지널은 진하고 선명한 색이라 테이블 건너편에서도 보여요.'),
                ('밤을 위한 개별 포장', '하나하나 개별 포장이라 한 봉지로 일행 모두 나눌 수 있어요. 프리파티부터 마지막 곡까지.'),
                ('한 봉지에 세 가지 맛 모두', '리부트 젤리는 라인 패키지로만 판매해요. 봉지마다 세 가지 모양과 맛이 모두 들어 있어요.')],
               ['개별 포장 젤리 10개', '봉지마다 라임 · 레몬 · 체리', '진하고 선명한 오리지널 컬러', '한국 알디콤에서 만들어요'],
               ['나가기 전에 한 봉지 챙기기.', '테이블에 모양을 나눠 보세요.', '집에 가는 길을 위해 가방에 하나 남겨 두기.'],
               [('한 가지 맛만 살 수 있나요?', '아니요. 젤리는 세 가지 모양과 맛이 한 봉지에 모두 든 라인 패키지로만 판매해요.'),
                ('오리지널과 밸런스는 뭐가 다른가요?', '오리지널은 진한 색의 기본 레시피, 밸런스는 연한 색의 제로슈가 버전이에요.')],
               ('이거 없이 나가지 마세요.', '리부트 젤리 오리지널. 한국에서 온 파티 필수품.')),
}
SEED['jelly-balance'] = {
    'images': {'hero': W + 'jelly-balance-scene-wide.webp', 'occasions': W + 'jelly-balance-scene.webp', 'closing': W + 'jelly-balance-package.webp',
               'sections': [W + 'jelly-balance-mix.webp', W + 'jelly-balance-lemon.webp', W + 'jelly-balance-package.webp']},
    'en': page('jelly', 'en', ('THE PARTY ESSENTIAL · ZERO SUGAR · 21+', 'All the shapes. Zero Sugar. Party ready.', 'The Zero Sugar version of our line package: 10 lime, lemon and cherry jellies, individually wrapped, in one pouch. Not a low calorie food.'),
               [('Zero Sugar, same fun', 'Balance keeps the cowboy shapes and bright fruit flavors, made as the Zero Sugar version of Reboot Jelly.'),
                ('Lighter colors', 'A pale green boot for lime, a light yellow lasso for lemon and a pink hat for cherry.'),
                ('Sold as a line package', 'Every pouch holds all three shapes and flavors. Never sold by single flavor or by the piece.')],
               ['Zero Sugar · Not a low calorie food', '10 individually wrapped jellies', 'Lime · Lemon · Cherry in every pouch', 'Made by ALDICOM in Korea'],
               ['Pack a pouch before you head out.', 'Pass it around the table.', 'Keep one in your bag for later.'],
               [('Is Balance really Zero Sugar?', 'Yes. Balance is the Zero Sugar version of each Reboot line. It is not a low calorie food.'),
                ('Can I buy only the lime jelly?', 'No. Each pouch is a line package with all three shapes and flavors.')],
               ('Zero Sugar. Full party.', 'Reboot Jelly Balance. The party essential from Korea. Not a low calorie food.')),
    'ko': page('jelly', 'ko', ('파티 필수품 · 제로슈가 · 21+', '모양은 그대로, 설탕은 제로. 파티 준비 끝.', '라인 패키지의 제로슈가 버전. 개별 포장한 라임·레몬·체리 젤리 10개를 한 봉지에 담았어요. 저칼로리 식품은 아니에요.'),
               [('제로슈가, 재미는 그대로', '카우보이 모양과 상큼한 과일 맛은 그대로, 제로슈가로 만든 리부트 젤리예요.'),
                ('연한 색으로 한눈에', '라임은 연두색 부츠, 레몬은 연노랑 올가미, 체리는 분홍 모자예요.'),
                ('라인 패키지로만 판매', '봉지마다 세 가지 모양과 맛이 모두 들어 있어요. 맛별·낱개 판매는 하지 않아요.')],
               ['제로슈가 · 저칼로리 식품 아님', '개별 포장 젤리 10개', '봉지마다 라임 · 레몬 · 체리', '한국 알디콤에서 만들어요'],
               ['나가기 전에 한 봉지 챙기기.', '테이블에 돌려 보세요.', '나중을 위해 가방에 하나.'],
               [('밸런스는 정말 제로슈가인가요?', '네. 밸런스는 각 리부트 라인의 제로슈가 버전이에요. 저칼로리 식품은 아니에요.'),
                ('라임 젤리만 살 수 있나요?', '아니요. 봉지마다 세 가지 모양과 맛이 모두 든 라인 패키지예요.')],
               ('설탕은 제로, 파티는 풀로.', '리부트 젤리 밸런스. 한국에서 온 파티 필수품. 저칼로리 식품은 아니에요.')),
}
SEED['drink-original'] = {
    'images': {'hero': W + 'drink-original-box3.webp', 'occasions': W + 'drink-original-lime-34.webp', 'closing': W + 'drink-original-box3.webp',
               'sections': [W + 'drink-original-cherry-34.webp', W + 'drink-original-box3.webp', W + 'drink-original-lemon-side.webp']},
    'en': page('drink', 'en', ('THE PARTY ESSENTIAL · 21+', 'A small bottle for big nights.', 'A non-carbonated drink in a 100 ml (3.4 fl oz) glass bottle, in lemon, lime and cherry.'),
               [('Pocket-size glass bottle', 'Each 100 ml bottle fits a jacket pocket or a clutch, and the neon label is easy to find in a dark room.'),
                ('One flavor or all three', 'Pick a single bottle of lemon, lime or cherry, or get the Mixed Box with one of each for the group.'),
                ('From Korea, made for the US', 'Reboot is the US-only line from ALDICOM, a Korean company. Restart Your Day.')],
               ['100 ml (3.4 fl oz) glass bottle', 'Non-carbonated', 'Lemon · Lime · Cherry', 'Mixed Box of 3'],
               ['Chill it before the party.', 'Bring a Mixed Box for the group.', 'Keep one in the fridge for tomorrow.'],
               [('Is it carbonated?', 'No. Reboot Drink is non-carbonated.'), ('What comes in the Mixed Box?', 'Three bottles: one lemon, one lime and one cherry.')],
               ('Grab a bottle on the way out.', 'Reboot Drink Original. The party essential from Korea.')),
    'ko': page('drink', 'ko', ('파티 필수품 · 21+', '큰 밤을 위한 작은 한 병.', '100ml(3.4 fl oz) 유리병에 담은 비탄산 음료. 레몬, 라임, 체리 맛.'),
               [('주머니 크기 유리병', '100ml 병이라 재킷 주머니나 작은 가방에 쏙, 네온 라벨이라 어두운 곳에서도 잘 보여요.'),
                ('한 가지 맛 또는 세 가지 모두', '레몬·라임·체리 중 한 병씩, 또는 일행과 나눌 믹스 박스로.'),
                ('한국에서, 미국을 위해', '리부트는 한국 기업 알디콤의 미국 전용 라인이에요. Restart Your Day.')],
               ['100ml (3.4 fl oz) 유리병', '비탄산', '레몬 · 라임 · 체리', '3병 믹스 박스'],
               ['파티 전에 차갑게.', '일행을 위해 믹스 박스 챙기기.', '내일을 위해 냉장고에 한 병.'],
               [('탄산이 있나요?', '아니요. 리부트 드링크는 비탄산 음료예요.'), ('믹스 박스에는 뭐가 들어 있나요?', '레몬, 라임, 체리 각 한 병씩 총 세 병이에요.')],
               ('나가는 길에 한 병.', '리부트 드링크 오리지널. 한국에서 온 파티 필수품.')),
}
SEED['drink-balance'] = {
    'images': {'hero': W + 'drink-balance-box3.webp', 'occasions': W + 'drink-balance-lemon-34.webp', 'closing': W + 'drink-balance-box3.webp',
               'sections': [W + 'drink-balance-cherry-34.webp', W + 'drink-balance-box3.webp', W + 'drink-balance-lime-side.webp']},
    'en': page('drink', 'en', ('THE PARTY ESSENTIAL · ZERO SUGAR · 21+', 'Same small bottle. Zero Sugar.', 'The Zero Sugar version of our non-carbonated drink, in a 100 ml (3.4 fl oz) glass bottle. Not a low calorie food.'),
               [('Zero Sugar, bright flavor', 'Balance keeps the lemon, lime and cherry flavors of Reboot Drink, made as the Zero Sugar version.'),
                ('Single bottles or a Mixed Box', 'Buy one flavor by the bottle, or get the Mixed Box with one lemon, one lime and one cherry.'),
                ('Easy to carry', 'The 100 ml glass bottle fits a pocket or a small bag, from the pre-party to the after-party.')],
               ['Zero Sugar · Not a low calorie food', '100 ml (3.4 fl oz) glass bottle', 'Non-carbonated', 'Lemon · Lime · Cherry'],
               ['Serve it chilled.', 'Share a Mixed Box with the group.', 'Pack one for the road.'],
               [('What does Balance mean?', 'Balance is the Zero Sugar version of each Reboot line (not a low calorie food). Original is the classic version.'),
                ('Is it carbonated?', 'No. Reboot Drink Balance is non-carbonated.')],
               ('Zero Sugar. Full night.', 'Reboot Drink Balance. The party essential from Korea. Not a low calorie food.')),
    'ko': page('drink', 'ko', ('파티 필수품 · 제로슈가 · 21+', '작은 병은 그대로, 설탕은 제로.', '100ml(3.4 fl oz) 유리병에 담은 비탄산 음료의 제로슈가 버전이에요. 저칼로리 식품은 아니에요.'),
               [('제로슈가, 상큼함은 그대로', '리부트 드링크의 레몬·라임·체리 맛을 그대로 살린 제로슈가 버전이에요.'),
                ('한 병씩 또는 믹스 박스', '원하는 맛을 한 병씩, 또는 레몬·라임·체리가 하나씩 든 믹스 박스로.'),
                ('들고 다니기 쉬워요', '100ml 유리병이라 주머니나 작은 가방에 쏙. 프리파티부터 애프터파티까지.')],
               ['제로슈가 · 저칼로리 식품 아님', '100ml (3.4 fl oz) 유리병', '비탄산', '레몬 · 라임 · 체리'],
               ['차갑게 즐기기.', '일행과 믹스 박스 나누기.', '나갈 때 한 병 챙기기.'],
               [('밸런스는 무슨 뜻인가요?', '밸런스는 각 리부트 라인의 제로슈가 버전이에요(저칼로리 식품은 아님). 오리지널은 기본 버전이에요.'),
                ('탄산이 있나요?', '아니요. 리부트 드링크 밸런스는 비탄산 음료예요.')],
               ('설탕은 제로, 밤은 풀로.', '리부트 드링크 밸런스. 한국에서 온 파티 필수품. 저칼로리 식품은 아니에요.')),
}
