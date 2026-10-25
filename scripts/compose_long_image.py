"""Build a product's long detail image (README §31): AI party backgrounds + real product cutouts + exact text.

    python3 scripts/compose_long_image.py jelly-original

Backgrounds (made once with Higgsfield, no product / no text in them): images/story/_bg/<slug>/bg0..bg4.jpg
Product cutouts: images/product_image/web/cutout/   Fonts: scripts/fonts/ (OFL)
Output per language: images/story/<slug>/<lang>-01.webp … (one file per panel, shown stacked on the product page)
and images/story/<slug>/<lang>-full.webp (the whole tall image, for download).
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
CUT = ROOT / 'images/product_image/web/cutout'
FONTS = ROOT / 'scripts/fonts'
WIDTH = 1080
LIME, PINK, YELLOW, WHITE, MUTED, BLACK = (177, 255, 59), (255, 77, 166), (255, 210, 60), (245, 244, 233), (190, 194, 178), (11, 12, 9)

COPY = {'jelly-original': {
    'en': dict(
        kicker='THE PARTY ESSENTIAL · 21+', hero='THREE SHAPES.\nONE POUCH.\nPARTY READY.',
        hero_sub='10 lime, lemon & cherry jellies, individually wrapped.',
        every='MADE FOR\nEVERY PARTY', every_sub='Pack it when you head out.',
        club=('01', 'CLUB & BAR NIGHTS', 'Individually wrapped and small enough\nfor a clutch or a jacket pocket.'),
        bday=('02', 'BIRTHDAYS & TOASTS', 'Pass the shapes around the table.\nEveryone grabs a favorite.'),
        shape='SHAPE = FLAVOR', shape_sub='Bold Original colors you can spot across the table.',
        flavors=[('LIME', 'COWBOY BOOT'), ('LEMON', 'LASSO'), ('CHERRY', 'COWBOY HAT')],
        pack='ONE POUCH.\nALL THREE.', pack_sub='Sold only as a line package —\n10 jellies: lime, lemon & cherry in every pouch.',
        inside="WHAT'S INSIDE", inside_sub='Made with A-HAT, ALDICOM’s blend of Hovenia dulcis extract and Lactobacillus fermentum.',
        ing=[('A-HAT', "ALDICOM's blend of Hovenia dulcis extract\nand Lactobacillus fermentum, developed in Korea."),
             ('Hovenia dulcis fruit extract', 'Fruit of the Oriental raisin tree,\na familiar ingredient in Korea.'),
             ('Lactobacillus fermentum', 'A lactic acid bacterium.\nPart of the A-HAT blend.')],
        ing_note='Full ingredient list and nutrition facts are printed on the package label.',
        how='HOW TO ENJOY', steps=['Pack a pouch before you head out.', 'Share the shapes with the table.', 'Keep one in your bag for the ride home.'],
        info='PRODUCT INFO', rows=[('Product', 'Reboot Jelly Original'), ('Format', 'Individually wrapped shaped jellies'), ('Pack', '1 pouch · 10 individually wrapped jellies'),
                                   ('Flavors', 'Lime · Lemon · Cherry'), ('Price', '$17.99 per pouch'), ('Made by', 'ALDICOM · Product of Korea'), ('For', 'Adults 21+')],
        close="DON'T HEAD OUT\nWITHOUT IT.", close_sub='Reboot Jelly Original · Restart Your Day', legal='For adults 21+. Please enjoy responsibly.'),
    'ko': dict(
        kicker='파티 필수품 · 21+', hero='세 가지 모양.\n한 봉지.\n파티 준비 끝.',
        hero_sub='하나하나 개별 포장한 라임 · 레몬 · 체리 젤리 10개.',
        every='모든 파티의\n필수품', every_sub='나갈 때 챙기세요.',
        club=('01', '클럽 · 바', '개별 포장이라 작은 가방이나\n재킷 주머니에도 쏙.'),
        bday=('02', '생일 · 건배하는 자리', '테이블에 돌리면 다들\n좋아하는 모양을 하나씩.'),
        shape='모양이 곧 맛', shape_sub='진하고 선명한 오리지널 컬러, 테이블 건너편에서도 보여요.',
        flavors=[('라임', '카우보이 부츠'), ('레몬', '올가미'), ('체리', '카우보이 모자')],
        pack='한 봉지에\n세 가지 맛 모두', pack_sub='라인 패키지로만 판매해요.\n봉지마다 라임 · 레몬 · 체리 젤리 10개.',
        inside='성분 분석', inside_sub='모든 리부트 제품은 알디콤의 조성물 A-HAT으로 만들어요.',
        ing=[('A-HAT', '헛개나무 추출물과 락토바실러스 퍼멘텀을 결합한\n알디콤의 조성물이에요.'),
             ('헛개나무 열매 추출물', '한국에서 친숙한 헛개나무의\n열매 원료예요.'),
             ('락토바실러스 퍼멘텀', '유산균 락토바실러스 퍼멘텀으로,\nA-HAT 조성물의 일부예요.')],
        ing_note='전체 원재료와 영양성분은 패키지 라벨에 표시돼 있어요.',
        how='즐기는 법', steps=['나가기 전에 한 봉지 챙기기.', '테이블에 모양을 나눠 보세요.', '집에 가는 길을 위해 가방에 하나.'],
        info='제품 정보', rows=[('제품명', 'Reboot Jelly Original'), ('형태', '개별 포장 모양 젤리'), ('구성', '1봉지 · 개별 포장 젤리 10개'),
                              ('맛', '라임 · 레몬 · 체리'), ('가격', '$17.99 (1봉지)'), ('제조', 'ALDICOM · 대한민국'), ('대상', '만 21세 이상 성인')],
        close='이거 없이\n나가지 마세요.', close_sub='리부트 젤리 오리지널 · Restart Your Day', legal='만 21세 이상 성인용. 책임감 있게 즐겨 주세요.'),
}}


class Page:
    def __init__(self, slug, lang):
        self.slug, self.lang, self.T = slug, lang, COPY[slug][lang]
        self.bg = ROOT / 'images/story/_bg' / slug
        self.prefix = slug  # cutout file prefix, e.g. jelly-original-lime.webp

    def font(self, kind, size):
        if self.lang == 'ko':
            f = ImageFont.truetype(str(FONTS / 'NotoSansKR.ttf'), size)
            f.set_variation_by_name({'display': 'Black', 'bold': 'ExtraBold'}.get(kind, 'Regular'))
            return f
        if kind == 'body':
            f = ImageFont.truetype(str(FONTS / 'DMSans.ttf'), size); f.set_variation_by_axes([14, 400]); return f
        return ImageFont.truetype(str(FONTS / ('BarlowCondensed-Black.ttf' if kind == 'display' else 'BarlowCondensed-ExtraBold.ttf')), size)

    def cover(self, n, w, h):
        return ImageOps.fit(Image.open(self.bg / f'bg{n}.jpg').convert('RGB'), (w, h), Image.LANCZOS).convert('RGBA')

    def cut(self, part, width):
        im = Image.open(CUT / f'{self.prefix}-{part}.webp').convert('RGBA')
        im = im.crop(im.getbbox())
        return im.resize((width, int(im.height * width / im.width)), Image.LANCZOS)

    @staticmethod
    def place(c, im, x, y, shadow=True, glow=None):
        if glow:
            g = Image.new('RGBA', (im.width + 160, im.height + 160), (0, 0, 0, 0))
            g.paste(Image.new('RGBA', im.size, glow + (255,)), (80, 80), im.split()[3].point(lambda v: 150 if v > 10 else 0))
            c.alpha_composite(g.filter(ImageFilter.GaussianBlur(45)), (x - 80, y - 80))
        if shadow:
            s = Image.new('RGBA', (im.width + 80, im.height + 80), (0, 0, 0, 0))
            s.paste(Image.new('RGBA', im.size, (0, 0, 0, 170)), (40, 60), im.split()[3])
            c.alpha_composite(s.filter(ImageFilter.GaussianBlur(22)), (x - 40, y - 40))
        c.alpha_composite(im, (x, y))

    @staticmethod
    def text(d, xy, s, f, fill=WHITE, anchor='la', spacing=8, align='left'):
        d.multiline_text(xy, s, font=f, fill=fill, anchor=anchor, spacing=spacing, align=align)

    @staticmethod
    def gradient(c, top, height, a0=0, a1=235):
        g = Image.linear_gradient('L').resize((1, height)).point(lambda v: int(a0 + (a1 - a0) * v / 255))
        shade = Image.new('RGBA', (c.width, height), BLACK + (0,)); shade.putalpha(g.resize((c.width, height)))
        c.alpha_composite(shade, (0, top))

    def pill(self, d, x, y, s, f):
        l, t, r, b = d.textbbox((0, 0), s, font=f)
        d.rounded_rectangle((x, y, x + (r - l) + 44, y + (b - t) + 26), radius=8, fill=LIME)
        d.text((x + 22 - l, y + 13 - t), s, font=f, fill=BLACK)

    def big(self, en, ko): return en if self.lang == 'en' else ko

    # ---------- panels ----------
    def hero(self):
        T, c = self.T, self.cover(0, WIDTH, 1440)
        self.gradient(c, 0, 700, 245, 30)
        d = ImageDraw.Draw(c)
        self.pill(d, 70, 80, T['kicker'], self.font('bold', 30))
        self.text(d, (70, 160), T['hero'], self.font('display', self.big(132, 104)), spacing=self.big(0, 14))
        self.text(d, (72, self.big(590, 580)), T['hero_sub'], self.font('body', 30))
        self.place(c, self.cut('package', 560), 300, 720, glow=LIME)
        self.place(c, self.cut('lime', 230), 70, 1080); self.place(c, self.cut('cherry', 250), 790, 1010); self.place(c, self.cut('lemon', 230), 820, 1220)
        return c

    def band(self, title, sub, h=420):
        c = Image.new('RGBA', (WIDTH, h), BLACK + (255,)); d = ImageDraw.Draw(c)
        d.line((WIDTH // 2 - 40, 70, WIDTH // 2 + 40, 70), fill=LIME, width=5)
        f, sp = self.font('display', self.big(104, 84)), self.big(0, 12)
        self.text(d, (WIDTH // 2, 110), title, f, anchor='ma', align='center', spacing=sp)
        bottom = d.multiline_textbbox((WIDTH // 2, 110), title, font=f, anchor='ma', align='center', spacing=sp)[3]
        self.text(d, (WIDTH // 2, bottom + 34), sub, self.font('body', 30), MUTED, anchor='ma', align='center')
        return c

    def scene(self, n, item, px, py, pw):
        num, title, body = item
        c = self.cover(n, WIDTH, 900)
        self.place(c, self.cut('package', pw), px, py, glow=LIME)
        self.gradient(c, 560, 340, 0, 240)
        d = ImageDraw.Draw(c)
        self.text(d, (70, 640), num, self.font('display', 80), LIME)
        self.text(d, (180, 650), title, self.font('display', self.big(66, 54)))
        self.text(d, (72, 750), body, self.font('body', 30), spacing=10)
        return c

    def shapes(self):
        T, fruit = self.T, self.cover(3, WIDTH, 980)
        d = ImageDraw.Draw(fruit)
        for i, ((part, color), (fl, shape)) in enumerate(zip([('lime', LIME), ('lemon', YELLOW), ('cherry', PINK)], T['flavors'])):
            x0 = i * 360
            fruit.alpha_composite(Image.new('RGBA', (360, 980), (0, 0, 0, 70)), (x0, 0))
            self.place(fruit, self.cut(part, 260), x0 + 50, 230, glow=(255, 255, 255))
            self.text(d, (x0 + 180, 620), fl, self.font('display', self.big(96, 76)), anchor='ma')
            self.text(d, (x0 + 180, 740), f'[ {shape} ]', self.font('bold', 34), anchor='ma')
            d.line((x0 + 150, 820, x0 + 210, 820), fill=color, width=6)
        head = self.band(T['shape'], T['shape_sub'], 340)
        out = Image.new('RGBA', (WIDTH, head.height + fruit.height)); out.alpha_composite(head, (0, 0)); out.alpha_composite(fruit, (0, head.height))
        return out

    def package(self):
        T, c = self.T, Image.new('RGBA', (WIDTH, 1300), BLACK + (255,))
        glow = Image.new('RGBA', c.size, (0, 0, 0, 0)); ImageDraw.Draw(glow).ellipse((140, 420, 940, 1220), fill=LIME + (70,))
        c.alpha_composite(glow.filter(ImageFilter.GaussianBlur(120)))
        d = ImageDraw.Draw(c)
        self.text(d, (WIDTH // 2, 90), T['pack'], self.font('display', self.big(118, 88)), anchor='ma', align='center', spacing=self.big(0, 14))
        self.text(d, (WIDTH // 2, self.big(380, 370)), T['pack_sub'], self.font('body', 32), MUTED, anchor='ma', align='center', spacing=12)
        self.place(c, self.cut('package', 520), 280, 520)
        for part, x, y in (('lime', 90, 900), ('lemon', 800, 820), ('cherry', 760, 1060)): self.place(c, self.cut(part, 200), x, y)
        return c

    def ingredients(self):
        T, c = self.T, Image.new('RGBA', (WIDTH, 1300), (16, 18, 13, 255))
        d = ImageDraw.Draw(c)
        self.text(d, (WIDTH // 2, 90), T['inside'], self.font('display', self.big(104, 84)), anchor='ma')
        self.text(d, (WIDTH // 2, 230), T['inside_sub'], self.font('body', 27), MUTED, anchor='ma')
        y = 330
        for name, role in T['ing']:
            d.rounded_rectangle((70, y, WIDTH - 70, y + 230), radius=18, fill=(24, 27, 20), outline=(48, 54, 38), width=2)
            self.pill(d, 104, y + 36, self.big('KEY', '핵심'), self.font('bold', 22))
            self.text(d, (200, y + 30), name, self.font('bold', self.big(44, 38)), LIME)
            self.text(d, (104, y + 110), role, self.font('body', 29), spacing=12)
            y += 260
        self.text(d, (WIDTH // 2, y + 40), T['ing_note'], self.font('body', 26), MUTED, anchor='ma')
        return c

    def how_and_info(self):
        T, c = self.T, Image.new('RGBA', (WIDTH, 1480), BLACK + (255,))
        d = ImageDraw.Draw(c)
        self.text(d, (WIDTH // 2, 90), T['how'], self.font('display', self.big(96, 80)), anchor='ma')
        y = 250
        for i, s in enumerate(T['steps'], 1):
            d.ellipse((120, y, 196, y + 76), fill=LIME)
            self.text(d, (158, y + 38), str(i), self.font('display', 48), BLACK, anchor='mm')
            self.text(d, (230, y + 38), s, self.font('body', 34), anchor='lm')
            y += 120
        y += 80
        d.line((70, y, WIDTH - 70, y), fill=(48, 54, 38), width=2)
        self.text(d, (WIDTH // 2, y + 70), T['info'], self.font('display', self.big(80, 68)), anchor='ma')
        y += 200
        for k, v in T['rows']:
            self.text(d, (110, y), k, self.font('bold', self.big(34, 30)), LIME)
            self.text(d, (400, y + 4), v, self.font('body', 31))
            y += 74
            d.line((110, y - 18, WIDTH - 110, y - 18), fill=(36, 40, 30), width=1)
        return c

    def closing(self):
        T, c = self.T, self.cover(4, WIDTH, 1350)
        d = ImageDraw.Draw(c)
        self.text(d, (WIDTH // 2, 120), T['close'], self.font('display', self.big(120, 92)), anchor='ma', align='center', spacing=self.big(0, 14))
        self.place(c, self.cut('package', 470), 305, 470, glow=LIME)
        self.gradient(c, 1060, 290, 0, 245)
        d = ImageDraw.Draw(c)
        self.text(d, (WIDTH // 2, 1170), T['close_sub'], self.font('bold', self.big(40, 34)), LIME, anchor='ma')
        self.text(d, (WIDTH // 2, 1250), T['legal'], self.font('body', 26), MUTED, anchor='ma')
        return c

    def panels(self):
        T = self.T
        return [self.hero(), self.band(T['every'], T['every_sub']), self.scene(1, T['club'], 620, 170, 330),
                self.scene(2, T['bday'], 360, 150, 340), self.shapes(), self.package(), self.ingredients(), self.how_and_info(), self.closing()]


def build(slug):
    out = ROOT / 'images/story' / slug
    out.mkdir(parents=True, exist_ok=True)
    for lang in ('en', 'ko'):
        panels = [p.convert('RGB') for p in Page(slug, lang).panels()]
        for i, p in enumerate(panels, 1): p.save(out / f'{lang}-{i:02d}.webp', 'WEBP', quality=86, method=5)
        full = Image.new('RGB', (WIDTH, sum(p.height for p in panels)), BLACK); y = 0
        for p in panels: full.paste(p, (0, y)); y += p.height
        full.save(out / f'{lang}-full.webp', 'WEBP', quality=84, method=5)
        print(slug, lang, len(panels), 'panels', full.size)


if __name__ == '__main__':
    build(sys.argv[1] if len(sys.argv) > 1 else 'jelly-original')
