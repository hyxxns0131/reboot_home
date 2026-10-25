'use strict';
/* Small photo cropper for admin pages (no library).
   RebootCropper.open({ src | file, aspect: null|number, title }) -> Promise<File|null>
   Drag the box to move, drag a corner to resize, pick a ratio, rotate 90°. Output: WEBP (PNG fallback), max 2000 px. */
window.RebootCropper = (() => {
  const RATIOS = [['Free', null], ['1:1', 1], ['4:5', 4 / 5], ['4:3', 4 / 3], ['16:9', 16 / 9]];
  const MAX = 2000, MIN = 24;
  let modal, img, box, sizeLabel, ratioBar, resolveFn, source, nat = { w: 1, h: 1 }, crop = { x: 0, y: 0, w: 1, h: 1 }, aspect = null, drag = null;

  function build() {
    modal = document.createElement('div');
    modal.className = 'crop-modal'; modal.hidden = true;
    modal.setAttribute('role', 'dialog'); modal.setAttribute('aria-modal', 'true'); modal.setAttribute('aria-label', 'Crop photo');
    modal.innerHTML = '<div class="crop-card"><header><strong class="crop-title">Crop photo</strong><button type="button" class="crop-x" aria-label="Cancel">✕</button></header>'
      + '<div class="crop-stage"><div class="crop-wrap"><img alt=""><div class="crop-box" tabindex="0" aria-label="Crop area. Arrow keys move it.">'
      + '<span class="crop-h nw"></span><span class="crop-h ne"></span><span class="crop-h sw"></span><span class="crop-h se"></span><i class="crop-grid"></i></div></div></div>'
      + '<div class="crop-tools"><div class="crop-ratios"></div><button type="button" class="btn crop-rotate">⟳ Rotate 90°</button><button type="button" class="btn crop-all">Whole photo</button></div>'
      + '<footer><span class="crop-size"></span><button type="button" class="btn crop-cancel">Cancel</button><button type="button" class="btn primary crop-save">Use this crop</button></footer></div>';
    document.body.append(modal);
    img = modal.querySelector('img'); box = modal.querySelector('.crop-box'); sizeLabel = modal.querySelector('.crop-size'); ratioBar = modal.querySelector('.crop-ratios');
    RATIOS.forEach(([label, r]) => {
      const b = document.createElement('button'); b.type = 'button'; b.className = 'crop-ratio'; b.textContent = label; b.dataset.r = r === null ? '' : r;
      b.addEventListener('click', () => setAspect(r)); ratioBar.append(b);
    });
    modal.querySelector('.crop-x').addEventListener('click', () => close(null));
    modal.querySelector('.crop-cancel').addEventListener('click', () => close(null));
    modal.querySelector('.crop-save').addEventListener('click', save);
    modal.querySelector('.crop-rotate').addEventListener('click', rotate);
    modal.querySelector('.crop-all').addEventListener('click', () => { aspect = null; markRatio(); crop = { x: 0, y: 0, w: nat.w, h: nat.h }; draw(); });
    modal.addEventListener('keydown', e => {
      if (e.key === 'Escape') { e.preventDefault(); close(null); }
      if (e.target === box && e.key.startsWith('Arrow')) {
        e.preventDefault(); const step = (e.shiftKey ? 10 : 1) * nat.w / 200;
        crop.x += e.key === 'ArrowLeft' ? -step : e.key === 'ArrowRight' ? step : 0; crop.y += e.key === 'ArrowUp' ? -step : e.key === 'ArrowDown' ? step : 0; clampMove(); draw();
      }
    });
    box.addEventListener('pointerdown', e => {
      e.preventDefault(); box.setPointerCapture(e.pointerId);
      const h = e.target.classList.contains('crop-h') ? [...e.target.classList].find(c => c.length === 2) : null;
      drag = { h, sx: e.clientX, sy: e.clientY, start: { ...crop } };
    });
    box.addEventListener('pointermove', e => {
      if (!drag) return;
      const s = scale(), dx = (e.clientX - drag.sx) / s, dy = (e.clientY - drag.sy) / s, c = { ...drag.start };
      if (!drag.h) { c.x += dx; c.y += dy; crop = c; clampMove(); }
      else {
        const west = drag.h.includes('w'), north = drag.h.includes('n');
        const ax = west ? c.x + c.w : c.x, ay = north ? c.y + c.h : c.y; // fixed corner
        let w = Math.max(MIN, (west ? -dx : dx) + c.w), h = Math.max(MIN, (north ? -dy : dy) + c.h);
        w = Math.min(w, west ? ax : nat.w - ax); h = Math.min(h, north ? ay : nat.h - ay);
        if (aspect) { if (w / h > aspect) w = h * aspect; else h = w / aspect; }
        crop = { x: west ? ax - w : ax, y: north ? ay - h : ay, w, h };
      }
      draw();
    });
    const end = () => { drag = null; };
    box.addEventListener('pointerup', end); box.addEventListener('pointercancel', end);
    window.addEventListener('resize', () => { if (!modal.hidden) draw(); });
  }
  const scale = () => img.clientWidth / nat.w;
  function clampMove() { crop.x = Math.min(Math.max(0, crop.x), nat.w - crop.w); crop.y = Math.min(Math.max(0, crop.y), nat.h - crop.h); }
  function draw() {
    const s = scale();
    Object.assign(box.style, { left: crop.x * s + 'px', top: crop.y * s + 'px', width: crop.w * s + 'px', height: crop.h * s + 'px' });
    const out = outSize(); sizeLabel.textContent = `${out.w} × ${out.h} px`;
  }
  function outSize() { const k = Math.min(1, MAX / Math.max(crop.w, crop.h)); return { w: Math.round(crop.w * k), h: Math.round(crop.h * k) }; }
  function markRatio() { ratioBar.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.r === (aspect === null ? '' : String(aspect))))); }
  function setAspect(r) {
    aspect = r; markRatio();
    if (r) { // biggest centered box with this ratio
      let w = nat.w, h = w / r; if (h > nat.h) { h = nat.h; w = h * r; }
      crop = { x: (nat.w - w) / 2, y: (nat.h - h) / 2, w, h };
    }
    draw();
  }
  function loadCanvas(canvas) {
    source = canvas; nat = { w: canvas.width, h: canvas.height };
    return new Promise(res => canvas.toBlob(b => { if (img.src.startsWith('blob:')) URL.revokeObjectURL(img.src); img.onload = () => res(); img.src = URL.createObjectURL(b); }, 'image/png'));
  }
  function rotate() {
    const c = document.createElement('canvas'); c.width = source.height; c.height = source.width;
    const x = c.getContext('2d'); x.translate(c.width, 0); x.rotate(Math.PI / 2); x.drawImage(source, 0, 0);
    loadCanvas(c).then(() => { setAspect(aspect); if (!aspect) { crop = { x: 0, y: 0, w: nat.w, h: nat.h }; draw(); } });
  }
  function save() {
    const out = outSize(), c = document.createElement('canvas'); c.width = out.w; c.height = out.h;
    c.getContext('2d').drawImage(source, crop.x, crop.y, crop.w, crop.h, 0, 0, out.w, out.h);
    const done = blob => close(new File([blob], blob.type === 'image/webp' ? 'photo.webp' : 'photo.png', { type: blob.type }));
    c.toBlob(b => (b && b.type === 'image/webp') ? done(b) : c.toBlob(done, 'image/png'), 'image/webp', 0.92);
  }
  function close(file) { modal.hidden = true; document.body.style.overflow = ''; const r = resolveFn; resolveFn = null; if (r) r(file); }

  function open({ src, file, aspect: a = null, title = 'Crop photo' }) {
    if (!modal) build();
    modal.querySelector('.crop-title').textContent = title;
    return new Promise((resolve, reject) => {
      const pic = new Image();
      pic.onload = () => {
        const c = document.createElement('canvas'); c.width = pic.naturalWidth; c.height = pic.naturalHeight;
        c.getContext('2d').drawImage(pic, 0, 0);
        if (file) URL.revokeObjectURL(pic.src);
        modal.hidden = false; document.body.style.overflow = 'hidden'; resolveFn = resolve;
        loadCanvas(c).then(() => { crop = { x: 0, y: 0, w: nat.w, h: nat.h }; setAspect(a); if (!a) draw(); box.focus(); });
      };
      pic.onerror = () => reject(new Error('This file could not be opened as an image.'));
      pic.src = file ? URL.createObjectURL(file) : src;
    });
  }
  // Put a cropped File into an <input type=file> so a normal form can submit it.
  function intoInput(input, f) { const dt = new DataTransfer(); dt.items.add(f); input.files = dt.files; }
  return { open, intoInput };
})();
