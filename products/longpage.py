"""Long detail image for any product, built in the app (README §34) — the same look as scripts/compose_long_image.py.

Inputs: the product's long-page copy (ProductStory content, en + ko), up to 5 party backgrounds (Higgsfield, no product or text in
them) and the product's own photo. Real product, exact text: the AI never draws the package or the words.
compose(product, content, backgrounds, photo) -> {'en': [webp bytes per panel], 'ko': [...]}
"""
import io
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

FONTS = Path(__file__).resolve().parent.parent / 'scripts' / 'fonts'
WIDTH = 1080
LIME, PINK, WHITE, MUTED, BLACK, CARD, EDGE = (177, 255, 59), (255, 77, 166), (245, 244, 233), (190, 194, 178), (11, 12, 9), (24, 27, 20), (48, 54, 38)


def _open(data):
    return Image.open(io.BytesIO(data)) if data else None


def fallback_bg(n, w, h):
    """Dark neon background when no AI image is available."""
    c = Image.new('RGBA', (w, h), BLACK + (255,))
    glow = Image.new('RGBA', (w, h), (0, 0, 0, 0)); d = ImageDraw.Draw(glow)
    spots = [((0.2, 0.25), LIME), ((0.85, 0.7), PINK), ((0.6, 0.15), (120, 90, 255))]
    for i, ((x, y), col) in enumerate(spots):
        if (i + n) % 3 == 2: continue
        r = int(w * 0.45); cx, cy = int(w * x), int(h * y)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col + (60,))
    c.alpha_composite(glow.filter(ImageFilter.GaussianBlur(140)))
    return c


class Composer:
    def __init__(self, product, c, lang, backgrounds, photo, table):
        self.p, self.c, self.lang, self.table = product, c, lang, table
        self.bgs = [b for b in (backgrounds or [])]
        self.photo = self._prepare_photo(photo)

    # ---------- helpers ----------
    def font(self, kind, size):
        if self.lang == 'ko':
            f = ImageFont.truetype(str(FONTS / 'NotoSansKR.ttf'), size)
            f.set_variation_by_name({'display': 'Black', 'bold': 'ExtraBold'}.get(kind, 'Regular'))
            return f
        if kind == 'body':
            f = ImageFont.truetype(str(FONTS / 'DMSans.ttf'), size); f.set_variation_by_axes([14, 400]); return f
        return ImageFont.truetype(str(FONTS / ('BarlowCondensed-Black.ttf' if kind == 'display' else 'BarlowCondensed-ExtraBold.ttf')), size)

    def up(self, s):
        return s.upper() if self.lang == 'en' else s

    @staticmethod
    def wrap(text, font, width):
        """Lines that fit `width` px. Words first; a word longer than a line (or Korean without spaces) breaks by character."""
        measure = lambda s: font.getlength(s)
        lines = []
        for para in str(text or '').split('\n'):
            line = ''
            for word in para.split(' '):
                trial = (line + ' ' + word).strip()
                if measure(trial) <= width: line = trial; continue
                if line: lines.append(line); line = ''
                while measure(word) > width:
                    cut = len(word)
                    while cut > 1 and measure(word[:cut]) > width: cut -= 1
                    lines.append(word[:cut]); word = word[cut:]
                line = word
            lines.append(line)
        return [l for l in lines if l is not None]

    def block(self, d, xy, text, kind, size, width, fill=WHITE, anchor='la', align='left', spacing=10, max_lines=None, min_size=None):
        """Draw wrapped text; shrinks the font (down to min_size) to stay within max_lines. Returns the bottom y."""
        while True:
            f = self.font(kind, size)
            lines = self.wrap(text, f, width)
            if not max_lines or len(lines) <= max_lines or not min_size or size <= min_size: break
            size -= 4
        if max_lines: lines = lines[:max_lines]
        body = '\n'.join(lines)
        d.multiline_text(xy, body, font=f, fill=fill, anchor=anchor, align=align, spacing=spacing)
        return d.multiline_textbbox(xy, body or ' ', font=f, anchor=anchor, align=align, spacing=spacing)[3]

    def cover(self, n, w, h):
        data = self.bgs[n % len(self.bgs)] if self.bgs else None
        if data:
            try: return ImageOps.fit(_open(data).convert('RGB'), (w, h), Image.LANCZOS).convert('RGBA')
            except Exception: pass
        return fallback_bg(n, w, h)

    @staticmethod
    def gradient(c, top, height, a0=0, a1=235):
        g = Image.linear_gradient('L').resize((1, height)).point(lambda v: int(a0 + (a1 - a0) * v / 255))
        shade = Image.new('RGBA', (c.width, height), BLACK + (0,)); shade.putalpha(g.resize((c.width, height)))
        c.alpha_composite(shade, (0, top))

    def pill(self, d, x, y, s, f, anchor_center=False):
        l, t, r, b = d.textbbox((0, 0), s, font=f)
        w, h = (r - l) + 44, (b - t) + 26
        if anchor_center: x -= w // 2
        d.rounded_rectangle((x, y, x + w, y + h), radius=8, fill=LIME)
        d.text((x + 22 - l, y + 13 - t), s, font=f, fill=BLACK)
        return x + w, y + h

    def _prepare_photo(self, data):
        """Product photo as RGBA. Cut-outs (transparent PNG/WEBP) are used as they are; photos with a background get a rounded card."""
        im = _open(data)
        if im is None: return None
        im = ImageOps.exif_transpose(im).convert('RGBA')
        alpha = im.split()[3]
        if alpha.getextrema()[0] < 200:  # has real transparency
            box = alpha.point(lambda v: 255 if v > 10 else 0).getbbox()
            return im.crop(box) if box else im
        side = max(im.size)
        mask = Image.new('L', im.size, 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius=int(side * 0.05), fill=255)
        im.putalpha(mask)
        return im

    def product(self, width, max_h=None):
        if self.photo is None: return None
        im = self.photo
        h = int(im.height * width / im.width)
        if max_h and h > max_h: width, h = int(width * max_h / h), max_h
        return im.resize((max(1, width), max(1, h)), Image.LANCZOS)

    @staticmethod
    def place(c, im, x, y, glow=None):
        if im is None: return
        if glow:
            g = Image.new('RGBA', (im.width + 160, im.height + 160), (0, 0, 0, 0))
            g.paste(Image.new('RGBA', im.size, glow + (255,)), (80, 80), im.split()[3].point(lambda v: 140 if v > 10 else 0))
            c.alpha_composite(g.filter(ImageFilter.GaussianBlur(45)), (x - 80, y - 80))
        s = Image.new('RGBA', (im.width + 80, im.height + 80), (0, 0, 0, 0))
        s.paste(Image.new('RGBA', im.size, (0, 0, 0, 170)), (40, 60), im.split()[3])
        c.alpha_composite(s.filter(ImageFilter.GaussianBlur(22)), (x - 40, y - 40))
        c.alpha_composite(im, (x, y))

    # ---------- panels ----------
    def hero(self):
        h = self.c.get('hero', {})
        c = self.cover(0, WIDTH, 1440); self.gradient(c, 0, 760, 245, 20)
        d = ImageDraw.Draw(c)
        y = 80
        if h.get('kicker'): y = self.pill(d, 70, y, h['kicker'], self.font('bold', 30))[1] + 40
        y = self.block(d, (70, y), self.up(h.get('headline', '')), 'display', 124 if self.lang == 'en' else 96, WIDTH - 140, max_lines=3, min_size=72, spacing=4 if self.lang == 'en' else 14)
        y = self.block(d, (72, y + 28), h.get('subhead', ''), 'body', 30, WIDTH - 160, max_lines=3, spacing=10)
        wide = self.photo is not None and self.photo.width > self.photo.height * 1.15
        im = self.product(820 if wide else 560, max_h=1440 - max(y + 80, 700) - 60)
        if im: self.place(c, im, (WIDTH - im.width) // 2, 1440 - im.height - 60, glow=LIME)
        return c

    def band(self, title, sub='', min_h=380):
        c = Image.new('RGBA', (WIDTH, 1200), BLACK + (255,)); d = ImageDraw.Draw(c)
        d.line((WIDTH // 2 - 40, 70, WIDTH // 2 + 40, 70), fill=LIME, width=5)
        y = self.block(d, (WIDTH // 2, 110), self.up(title), 'display', 104 if self.lang == 'en' else 80, WIDTH - 140, anchor='ma', align='center', max_lines=2, min_size=64, spacing=4)
        if sub: y = self.block(d, (WIDTH // 2, y + 30), sub, 'body', 30, WIDTH - 200, MUTED, anchor='ma', align='center')
        return c.crop((0, 0, WIDTH, max(min_h, y + 80)))

    def occasions(self):
        occ = self.c.get('occasions', {})
        items = occ.get('items', [])[:4]
        if not items: return None
        head = self.band(occ.get('title') or ('Made for every party' if self.lang == 'en' else '모든 파티의 필수품'), min_h=300)
        c = Image.new('RGBA', (WIDTH, 2400), BLACK + (255,)); d = ImageDraw.Draw(c)
        y = 10
        for i, it in enumerate(items, 1):
            tmp = Image.new('RGBA', (WIDTH - 140, 700), (0, 0, 0, 0)); td = ImageDraw.Draw(tmp)
            td.text((34, 26), f'{i:02d}', font=self.font('display', 60), fill=LIME)
            yy = self.block(td, (130, 34), it['title'], 'bold', 44 if self.lang == 'en' else 38, WIDTH - 320, LIME)
            yy = self.block(td, (130, yy + 16), it['body'], 'body', 29, WIDTH - 320, spacing=10)
            d.rounded_rectangle((70, y, WIDTH - 70, y + yy + 34), radius=18, fill=CARD, outline=EDGE, width=2)
            c.alpha_composite(tmp.crop((0, 0, WIDTH - 140, yy + 34)), (70, y))
            y += yy + 34 + 22
        body = c.crop((0, 0, WIDTH, y + 50))
        out = Image.new('RGBA', (WIDTH, head.height + body.height), BLACK + (255,)); out.alpha_composite(head, (0, 0)); out.alpha_composite(body, (0, head.height))
        return out

    def scene(self, i, sec):
        c = self.cover(i, WIDTH, 980)
        im = self.product(320, max_h=420)
        if im: self.place(c, im, WIDTH - im.width - 90 if i % 2 else 90, 120, glow=LIME)
        self.gradient(c, 520, 460, 0, 245)
        d = ImageDraw.Draw(c)
        d.text((70, 600), f'{i:02d}', font=self.font('display', 80), fill=LIME)
        y = self.block(d, (190, 612), sec['title'], 'display', 62 if self.lang == 'en' else 50, WIDTH - 260, max_lines=2, min_size=44, spacing=4)
        self.block(d, (72, max(y + 26, 720)), sec['body'], 'body', 29, WIDTH - 144, max_lines=6, spacing=10)
        return c

    def highlights(self):
        hl = self.c.get('highlights', [])[:6]
        if not hl: return None
        c = Image.new('RGBA', (WIDTH, 900), (16, 18, 13, 255)); d = ImageDraw.Draw(c)
        y = 80
        for s in hl:
            d.ellipse((90, y + 12, 112, y + 34), fill=LIME)
            y = self.block(d, (140, y), s, 'bold', 40 if self.lang == 'en' else 34, WIDTH - 230, spacing=8) + 34
        return c.crop((0, 0, WIDTH, y + 50))

    def ingredients(self):
        ing = self.c.get('ingredients', {})
        rows = [r for r in self.table['rows'] if r['key']][:3] or self.table['rows'][:3]
        c = Image.new('RGBA', (WIDTH, 2200), (16, 18, 13, 255)); d = ImageDraw.Draw(c)
        title = ing.get('title') or ("What's inside" if self.lang == 'en' else '성분 분석')
        y = self.block(d, (WIDTH // 2, 90), self.up(title), 'display', 100 if self.lang == 'en' else 80, WIDTH - 140, anchor='ma', align='center')
        if ing.get('intro'): y = self.block(d, (WIDTH // 2, y + 30), ing['intro'], 'body', 27, WIDTH - 180, MUTED, anchor='ma', align='center')
        y += 60
        for r in rows:
            top = y
            tmp = Image.new('RGBA', (WIDTH, 600), (0, 0, 0, 0)); td = ImageDraw.Draw(tmp)
            self.pill(td, 34, 36, 'KEY' if self.lang == 'en' else '핵심', self.font('bold', 22))
            yy = self.block(td, (130, 30), r['name'], 'bold', 40 if self.lang == 'en' else 34, WIDTH - 340, LIME)
            yy = self.block(td, (34, max(yy, 90) + 20), r['role'], 'body', 28, WIDTH - 210, spacing=10)
            d.rounded_rectangle((70, top, WIDTH - 70, top + yy + 34), radius=18, fill=CARD, outline=EDGE, width=2)
            c.alpha_composite(tmp.crop((0, 0, WIDTH - 140, yy + 34)), (70, top))
            y = top + yy + 34 + 26
        note = ing.get('note') or ('Full ingredient list and nutrition facts are printed on the package label.' if self.lang == 'en' else '전체 원재료와 영양성분은 패키지 라벨에 표시돼 있어요.')
        y = self.block(d, (WIDTH // 2, y + 20), note, 'body', 25, WIDTH - 180, MUTED, anchor='ma', align='center')
        return c.crop((0, 0, WIDTH, y + 70))

    def how_and_info(self):
        p, en = self.p, self.lang == 'en'
        c = Image.new('RGBA', (WIDTH, 2400), BLACK + (255,)); d = ImageDraw.Draw(c)
        y = 90
        steps = self.c.get('how_to_enjoy', [])[:4]
        if steps:
            y = self.block(d, (WIDTH // 2, y), 'HOW TO ENJOY' if en else '즐기는 법', 'display', 96 if en else 78, WIDTH - 140, anchor='ma') + 60
            for i, s in enumerate(steps, 1):
                d.ellipse((110, y, 186, y + 76), fill=LIME)
                d.text((148, y + 38), str(i), font=self.font('display', 48), fill=BLACK, anchor='mm')
                yy = self.block(d, (220, y + 14), s, 'body', 32, WIDTH - 300, spacing=8)
                y = max(y + 76, yy) + 40
            y += 40; d.line((70, y, WIDTH - 70, y), fill=EDGE, width=2); y += 70
        y = self.block(d, (WIDTH // 2, y), 'PRODUCT INFO' if en else '제품 정보', 'display', 80 if en else 66, WIDTH - 140, anchor='ma') + 60
        opts = ' · '.join(f"{o['label']} ${o['price_usd']:.2f}" for o in p.get('options', [])[:3])
        rows = [('Product' if en else '제품명', p['name']), ('Format' if en else '형태', p.get('format', '')), ('Pack' if en else '구성', p.get('pack', '')),
                ('Flavors' if en else '맛', ' · '.join(p.get('flavors', []))), ('Price' if en else '가격', opts),
                ('Made by' if en else '제조', 'ALDICOM · Product of Korea' if en else 'ALDICOM · 대한민국'), ('For' if en else '대상', 'Adults 21+' if en else '만 21세 이상 성인')]
        if not en:
            from core.translations import KO
            rows = [(k, KO.get(v, v)) for k, v in rows]
        for k, v in rows:
            if not v: continue
            self.block(d, (110, y), k, 'bold', 32 if en else 28, 260, LIME)
            yy = self.block(d, (400, y + 4), v, 'body', 29, WIDTH - 510, spacing=8)
            y = max(y + 56, yy) + 22
            d.line((110, y - 10, WIDTH - 110, y - 10), fill=(36, 40, 30), width=1)
        return c.crop((0, 0, WIDTH, y + 60))

    def closing(self):
        clo = self.c.get('closing', {})
        c = self.cover(4, WIDTH, 1350); d = ImageDraw.Draw(c)
        self.gradient(c, 0, 420, 230, 0)
        y = self.block(d, (WIDTH // 2, 110), self.up(clo.get('headline') or self.p['name']), 'display', 112 if self.lang == 'en' else 84, WIDTH - 140, anchor='ma', align='center', max_lines=3, min_size=64, spacing=4)
        im = self.product(440, max_h=1350 - y - 380)
        if im: self.place(c, im, (WIDTH - im.width) // 2, y + 60, glow=LIME)
        self.gradient(c, 1010, 340, 0, 245)
        d = ImageDraw.Draw(c)
        if clo.get('subhead'): self.block(d, (WIDTH // 2, 1120), clo['subhead'], 'bold', 36 if self.lang == 'en' else 30, WIDTH - 160, LIME, anchor='ma', align='center', max_lines=2)
        self.block(d, (WIDTH // 2, 1260), 'For adults 21+. Please enjoy responsibly.' if self.lang == 'en' else '만 21세 이상 성인용. 책임감 있게 즐겨 주세요.', 'body', 25, WIDTH - 160, MUTED, anchor='ma', align='center')
        return c

    def panels(self):
        out = [self.hero(), self.occasions()]
        out += [self.scene(i, s) for i, s in enumerate(self.c.get('sections', [])[:3], 1)]
        out += [self.highlights(), self.ingredients(), self.how_and_info(), self.closing()]
        return [p for p in out if p is not None]


def compose(product, content, backgrounds, photo):
    from products.story import ingredient_rows
    result = {}
    for lang in ('en', 'ko'):
        c = content.get(lang) or content.get('en')
        panels = Composer(product, c, lang, backgrounds, photo, ingredient_rows(product, c, lang)).panels()
        out = []
        for im in panels:
            buf = io.BytesIO(); im.convert('RGB').save(buf, 'WEBP', quality=86, method=4); out.append(buf.getvalue())
        result[lang] = out
    return result
