# REBOOT home showcase

Existing Flask project updated in place at `/Users/kang/Desktop/reboot_home`.

## Current behavior
- Official slogan: **Restart your day**.
- Eight product buttons surround SHOT: Original Lime/Lemon/Cherry, Balance Lime/Lemon/Cherry, Original Gummy and Balance Gummy.
- Direct selection shows the chosen product with a roughly 0.8-second multi-view turn. SHOT advances through all eight, then returns to Original Lime.
- Both drinks and gummy packages appear on the main stage. Selecting gummies puts the pouch and three candy flavors in the primary position, with a drink alongside.
- Main and collection product images link to existing product purchase/detail pages. Drink links include a validated SKU selection so the corresponding flavor and photo are selected. Collection preview buttons remain separate from purchase links.
- Image preloading, repeat-input lock, keyboard controls and reduced-motion fallback retained. Scroll and product animation use separate wrappers.

## Rendering limits
This is image-based pseudo-3D, not a reconstructed 360° mesh. Bottle and lime-candy turns sequence authentic front/quarter/side/back artwork without mirrored labels or invented views. Gummy packages have no rear photograph: the pouch lifts/tilts while the real candy angle sequence turns alongside it. Original artwork and GLBs are preserved.

## Files changed or added
- `core/templates/main/home.html`: stage, radial selector, collection links and preview controls.
- `core/templates/products/detail.html`: validated query SKU selects the purchase option and image; retained through login.
- `core/static/core/js/showcase.js`: eight-item product state, fast direct-selection animation, links and collection behavior.
- `core/static/core/css/showcase.css`: responsive stage, radial selector and separate image/preview hit areas.
- `images/showcase/`: optimized source-derived bottle/candy angles and gummy photos.
- `scripts/extract_showcase.py`: repeatable original-artwork extraction; optional `jelly` argument.
- `core/static/core/js/vendor/`: locally served GSAP/ScrollTrigger 3.12.5.
- `tests/test_app.py`: isolated reels fixture; six flavor-link checks and invalid-SKU fallback.
- `tests/browser_check.py`: updated eight-product and preview selectors (script not executed in this session).

## Validation
- Flask test suite: **37 passed**.
- JS syntax and `git diff --check`: passed.
- In-app browser: all eight direct selections and their purchase links; Balance Cherry collection preview and matching purchase selection; Balance Gummy image navigation; main stage and gummy composition inspected.
- Responsive CSS included; this update was manually viewed in the available browser panel, not separately tested on physical mobile hardware.

## Run
Run `./start.command` in `/Users/kang/Desktop/reboot_home`, then open http://127.0.0.1:5050/ . The existing server is already serving the changes. No Node build step is required.
