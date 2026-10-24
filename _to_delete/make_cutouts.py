"""Make transparent cutouts for the home page art from the white-background studio photos.

Reads images/product_image/web/<name>.webp and writes images/product_image/cutout/<name>.webp (RGBA).
Only the white area connected to the image border is removed, so white parts of the product stay.
Run again after replacing a studio photo:  python scripts/make_cutouts.py
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageChops

SRC = Path('images/product_image/web')
OUT = Path('images/product_image/cutout')
NAMES = [f'jelly-{line}-{v}' for line in ('original', 'balance') for v in ('package', 'lime', 'lemon', 'cherry')] + \
        [f'drink-{line}-{f}' for line in ('original', 'balance') for f in ('lime', 'lemon', 'cherry')]
WHITE = 236  # a pixel counts as background when all channels are at least this bright
# Packages stand on a light grey floor, so for them any pale, colourless pixel counts as background.
FLOOR = {'jelly-original-package': 190, 'jelly-balance-package': 190}

def cutout(path, white=WHITE):
    im = Image.open(path).convert('RGB')
    w, h = im.size
    r, g, b = im.split()
    low = ImageChops.darker(ImageChops.darker(r, g), b)
    high = ImageChops.lighter(ImageChops.lighter(r, g), b)
    grey = ImageChops.subtract(high, low).point(lambda v: 255 if v <= 18 else 0)
    light = ImageChops.multiply(low.point(lambda v: 255 if v >= white else 0), grey if white < WHITE else Image.new('L', im.size, 255))
    for x in range(0, w, 8):
        for y in (0, h - 1):
            if light.getpixel((x, y)) == 255: ImageDraw.floodfill(light, (x, y), 128)
    for y in range(0, h, 8):
        for x in (0, w - 1):
            if light.getpixel((x, y)) == 255: ImageDraw.floodfill(light, (x, y), 128)
    alpha = light.point(lambda v: 0 if v == 128 else 255).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1))
    im.putalpha(alpha)
    return im.crop(alpha.getbbox())

if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    for name in NAMES:
        cutout(SRC / f'{name}.webp', FLOOR.get(name, WHITE)).save(OUT / f'{name}.webp', quality=88, method=6)
        print('wrote', OUT / f'{name}.webp')
