/* Motion hero: product switcher + entrance + Rebu (3D, loaded lazily).
 * Switching never reassigns img.src — every image is already in the DOM and only
 * classes change, so the new product shows in the same frame as the click. */
(() => {
  'use strict';
  const root = document.querySelector('[data-motion-hero]');
  if (!root) return;
  const $ = s => root.querySelector(s);
  const $$ = s => [...root.querySelectorAll(s)];
  const items = JSON.parse($('#mh-data').textContent);
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const byKind = k => items.filter(it => it.kind === k);
  const nameOf = it => it.kind === 'drink' ? `${cap(it.line)} ${cap(it.flavor)} drink` : `${cap(it.line)} gummy pack`;
  const cap = s => s[0].toUpperCase() + s.slice(1);

  const el = {
    eyebrow: $('#mh-eyebrow'), title: $('#mh-title'), lede: $('#mh-lede'), price: $('#mh-price'),
    cta: $('#mh-cta'), ctaText: $('#mh-cta-text'), product: $('#mh-product'), bubble: $('#mh-bubble'),
    status: $('#mh-status'), chips: $('#mh-chips'), videos: $('.mh-videos')
  };
  const shots = new Map($$('.mh-shot').map(s => [s.dataset.id, s]));
  const sides = {l: $('.mh-side-l'), r: $('.mh-side-r')};
  const tabs = $$('[role=tab]');
  const chipsOf = k => $$(`.mh-chip[data-kind="${k}"]`);
  let kind = 'drink', index = 0, current = items[0];

  // Every animation is owned by its element: starting a new one cancels whatever that
  // element was doing, so rapid clicks can never leave a stale frame behind.
  const stop = node => node.getAnimations?.().forEach(a => a.cancel());
  const animate = (node, frames, opts) => {
    stop(node);
    if (reduced.matches || !node.animate) return null;
    const a = node.animate(frames, {fill: 'backwards', ...opts});
    a.finished.then(() => a.cancel(), () => {});
    return a;
  };

  // Swap text inside a mask: old line slides up and out, new line rises in.
  function swapText(node, text, {delay = 0, dist = '115%', dur = 650} = {}) {
    const token = {}; node._swap = token;
    stop(node);
    const set = () => { node.textContent = text; };
    if (reduced.matches || !node.animate) return set();
    const out = node.animate([{transform: 'translateY(0)', opacity: 1}, {transform: `translateY(-${dist})`, opacity: 0}],
      {duration: 200, delay, easing: 'cubic-bezier(.4,0,1,1)', fill: 'forwards'});
    out.finished.then(() => {
      if (node._swap !== token) return;
      set(); out.cancel();
      const inn = node.animate([{transform: `translateY(${dist})`, opacity: 0}, {transform: 'translateY(0)', opacity: 1}],
        {duration: dur, easing: 'cubic-bezier(.16,1,.3,1)', fill: 'backwards'});
      inn.finished.then(() => inn.cancel(), () => {});
    }, () => {});
  }

  // Hide every shot that is neither current nor still flying out.
  const tidy = () => shots.forEach((s, id) => {
    if (id !== current.id && !s.getAnimations().length) s.classList.remove('is-on');
  });

  function show(nextKind, nextIndex, dir = 1, {initial = false} = {}) {
    const list = byKind(nextKind);
    nextIndex = (nextIndex + list.length) % list.length;
    const next = list[nextIndex];
    if (!initial && next.id === current.id) return;
    const kindChanged = nextKind !== kind;
    const prev = current;
    kind = nextKind; index = nextIndex; current = next;

    root.dataset.kind = kind;
    root.style.setProperty('--flavor', next.color);

    // product: same-frame class swap, then a directional fly-through
    const inShot = shots.get(next.id), outShot = shots.get(prev.id);
    shots.forEach((s, id) => { if (id !== next.id && id !== prev.id) { stop(s); s.classList.remove('is-on'); } });
    inShot.classList.add('is-on');
    if (!initial) {
      const w = el.product.offsetWidth;
      const o = animate(outShot, [
        {transform: 'none', opacity: 1, filter: 'blur(0)'},
        {transform: `translateX(${-dir * w * .42}px) translateY(${w * .05}px) rotate(${-dir * 9}deg) scale(.86)`, opacity: 0, filter: 'blur(6px)'}
      ], {duration: 420, easing: 'cubic-bezier(.55,0,.85,.35)', fill: 'forwards'});
      if (o) o.finished.then(() => { o.cancel(); tidy(); }, tidy); else tidy();
      animate(inShot, [
        {transform: `translateX(${dir * w * .55}px) translateY(${w * .1}px) rotate(${dir * 12}deg) scale(.82)`, opacity: 0},
        {transform: 'none', opacity: 1}
      ], {duration: 820, delay: 90, easing: 'cubic-bezier(.16,1,.3,1)'});
    }

    // copy
    if (initial) {
      el.eyebrow.textContent = next.eyebrow; el.title.textContent = next.title;
      el.lede.textContent = next.lede; el.price.textContent = next.price;
    } else {
      swapText(el.eyebrow, next.eyebrow, {dur: 500});
      swapText(el.title, next.title, {delay: 40, dur: 820});
      swapText(el.lede, next.lede, {delay: 80, dist: '14px', dur: 600});
      swapText(el.price, next.price, {delay: 120, dist: '10px', dur: 500});
    }
    el.ctaText.textContent = next.cta;
    el.cta.href = el.product.href = next.href;
    el.product.setAttribute('aria-label', `Shop ${nameOf(next)}`);
    el.bubble.textContent = next.bubble;
    el.bubble.classList.remove('is-pop'); void el.bubble.offsetWidth; el.bubble.classList.add('is-pop');

    // side slots: previous on the left, next on the right (two packs: only the other one, on the right)
    const nb = {l: list[(index - 1 + list.length) % list.length], r: list[(index + 1) % list.length]};
    sides.l.hidden = list.length < 3;
    for (const k of ['l', 'r']) {
      const b = sides[k], it = nb[k];
      b.querySelectorAll('img').forEach(img => img.classList.toggle('is-shown', img.dataset.id === it.id));
      b.dataset.index = list.indexOf(it);
      b.setAttribute('aria-label', `${k === 'l' ? 'Previous' : 'Next'}: ${nameOf(it)}`);
      b.querySelector('small').textContent = it.kind === 'drink' ? it.line.toUpperCase() : 'GUMMY PACK';
      b.querySelector('b').textContent = it.title;
      if (!initial) animate(b, [{opacity: 0, transform: `translateY(14px)`}, {opacity: 1, transform: 'none'}], {duration: 520, delay: 160, easing: 'cubic-bezier(.22,1,.36,1)'});
    }

    // picker
    tabs.forEach(t => { const on = t.dataset.kind === kind; t.setAttribute('aria-selected', on); t.tabIndex = on ? 0 : -1; });
    el.chips.setAttribute('aria-labelledby', `mh-tab-${kind}`);
    for (const k of ['drink', 'gummy']) chipsOf(k).forEach((c, i) => {
      c.setAttribute('aria-pressed', k === kind && i === index);
      c.setAttribute('aria-label', nameOf(byKind(k)[i]));
    });

    // optional background clip per product (set item.video to a URL to use one)
    syncVideo(next);

    if (!initial) el.status.textContent = `${nameOf(next)}, ${index + 1} of ${list.length}`;
    root.dispatchEvent(new CustomEvent('mh:switch', {detail: {item: next, dir, kindChanged, initial}}));
  }

  function syncVideo(it) {
    const vids = [...el.videos.querySelectorAll('video')];
    let v = vids.find(x => x.dataset.id === it.id);
    if (!v && it.video) {
      v = Object.assign(document.createElement('video'), {muted: true, loop: true, playsInline: true, preload: 'auto', src: it.video});
      v.dataset.id = it.id; v.setAttribute('aria-hidden', 'true'); el.videos.append(v);
    }
    vids.concat(v ? [v] : []).forEach(x => {
      const on = x === v;
      x.classList.toggle('is-active', on);
      on ? x.play().catch(() => {}) : x.pause();
    });
  }

  // ── controls ──────────────────────────────────────────────────────────
  for (const k of ['drink', 'gummy']) chipsOf(k).forEach((c, i) => c.addEventListener('click', () => show(k, i, i >= index ? 1 : -1)));
  el.chips.addEventListener('keydown', e => {
    if (!['ArrowLeft', 'ArrowRight'].includes(e.key)) return;
    const list = chipsOf(kind), i = list.indexOf(document.activeElement); if (i < 0) return;
    e.preventDefault(); list[(i + (e.key === 'ArrowRight' ? 1 : -1) + list.length) % list.length].focus();
  });
  for (const k of ['l', 'r']) {
    sides[k].addEventListener('click', () => show(kind, +sides[k].dataset.index, k === 'r' ? 1 : -1));
  }
  tabs.forEach((t, i) => {
    t.addEventListener('click', () => {
      const k = t.dataset.kind; if (k === kind) return;
      show(k, k === 'gummy' ? (index < 3 ? 0 : 1) : index * 3, k === 'gummy' ? 1 : -1);
    });
    t.addEventListener('keydown', e => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
      e.preventDefault(); const o = tabs[(i + 1) % 2]; o.focus(); o.click();
    });
  });
  // swipe the stage on touch screens
  let sx = null, sy = 0, swiped = false;
  const stage = $('.mh-stage');
  stage.addEventListener('pointerdown', e => { swiped = false; if (e.pointerType !== 'mouse') { sx = e.clientX; sy = e.clientY; } }, {passive: true});
  stage.addEventListener('pointerup', e => {
    if (sx === null) return;
    const dx = e.clientX - sx, dy = e.clientY - sy; sx = null;
    if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy) * 1.4) { swiped = true; show(kind, index + (dx < 0 ? 1 : -1), dx < 0 ? 1 : -1); }
  }, {passive: true});
  stage.addEventListener('click', e => { if (swiped) { e.preventDefault(); e.stopPropagation(); swiped = false; } }, true);
  reduced.addEventListener?.('change', () => { if (reduced.matches) { shots.forEach(stop); tidy(); } });

  show('drink', 0, 1, {initial: true});

  // ── entrance (html.anim is added by an inline script in <head>) ─────────
  const html = document.documentElement;
  if (html.classList.contains('anim')) {
    const go = () => requestAnimationFrame(() => requestAnimationFrame(() => {
      html.classList.add('play');
      setTimeout(() => html.classList.remove('anim', 'play'), 2400);
    }));
    Promise.race([document.fonts ? document.fonts.ready : Promise.resolve(), new Promise(r => setTimeout(r, 500))]).then(go);
  }

  // ── Rebu: load three.js + the model only once the hero is on screen ────
  const rebu = $('#mh-rebu');
  let loaded = false;
  const loadRebu = () => {
    if (loaded) return; loaded = true;
    import(root.dataset.rebuModule || '/static/core/js/rebu-3d.js')
      .then(m => m.mount({root, box: rebu, src: root.dataset.rebuSrc || '/images/Rebu/Rebu_3D_web.glb'}))
      .catch(() => {});
  };
  const idle = window.requestIdleCallback || (fn => setTimeout(fn, 600));
  if ('IntersectionObserver' in window) {
    const io = new IntersectionObserver(es => { if (es.some(e => e.isIntersecting)) { io.disconnect(); idle(loadRebu, {timeout: 1500}); } });
    io.observe(rebu);
  } else idle(loadRebu);
  // Rebu reacts to taps even before (or without) 3D
  rebu.querySelector('.mh-rebu-hit').addEventListener('click', () => {
    root.dispatchEvent(new CustomEvent('mh:poke'));
    const lines = ['Lead the way, partner!', 'Right behind you!', 'Where are we going?', current.bubble];
    el.bubble.textContent = lines[Math.floor(Math.random() * lines.length)];
    el.bubble.classList.remove('is-pop'); void el.bubble.offsetWidth; el.bubble.classList.add('is-pop');
  });
})();
