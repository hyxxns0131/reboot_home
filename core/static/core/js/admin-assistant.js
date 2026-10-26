'use strict';
// Admin AI assistant (README §27). History stays in this browser tab (sessionStorage) so it survives moving between admin pages.
(() => {
  const box = document.querySelector('[data-admin-ai]');
  if (!box) return;
  const d = box.dataset, KEY = 'reboot-admin-ai';
  const toggle = box.querySelector('.admin-ai-toggle'), panel = box.querySelector('.admin-ai-panel'), log = box.querySelector('.admin-ai-log');
  const form = box.querySelector('form'), input = form.querySelector('textarea'), send = form.querySelector('button[type=submit]');
  const file = form.querySelector('input[type=file]'), tray = box.querySelector('.admin-ai-attach');
  const csrf = () => document.querySelector('meta[name="csrf-token"]').content;
  let state = { open: false, history: [], items: [] }, pending = [];
  try { state = Object.assign(state, JSON.parse(sessionStorage.getItem(KEY) || '{}')); } catch { /* storage off: start fresh */ }
  const save = () => { try { sessionStorage.setItem(KEY, JSON.stringify({ open: state.open, history: state.history.slice(-30), items: state.items.slice(-60) })); } catch { /* ignore */ } };

  const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
  const scroll = () => { log.scrollTop = log.scrollHeight; };

  function drawMessage(item) {
    const p = el('div', `admin-ai-msg ${item.role}`);
    p.append(el('p', '', item.text));
    (item.images || []).forEach(src => { const img = el('img'); img.src = src; img.alt = ''; p.append(img); });
    log.append(p); return p;
  }
  function drawCard(item) {
    const card = el('div', 'admin-ai-card'); card.dataset.id = item.card.id;
    card.append(el('strong', '', `${d.confirmTitle} · #${item.card.id}`));
    if (item.card.image) { const img = el('img'); img.src = item.card.image; img.alt = ''; card.append(img); }
    const dl = el('dl'); item.card.rows.forEach(([k, v]) => { dl.append(el('dt', '', k), el('dd', '', v)); }); card.append(dl);
    const status = el('p', 'admin-ai-status', item.message || '');
    const buttons = el('div', 'admin-ai-buttons');
    if (item.status === 'pending') {
      const ok = el('button', 'btn primary', d.save), no = el('button', 'btn', d.cancel);
      ok.type = no.type = 'button';
      ok.addEventListener('click', () => decide(item, 'save', card));
      no.addEventListener('click', () => decide(item, 'cancel', card));
      buttons.append(ok, no);
    } else {
      status.textContent = (item.status === 'saved' ? `✓ ${d.saved}` : d.cancelled) + (item.message ? ` — ${item.message}` : '');
      if (item.link) { const a = el('a', 'text-link', d.open); a.href = item.link; status.append(' ', a); }
    }
    card.append(buttons, status); log.append(card);
  }
  function redraw() {
    log.textContent = '';
    if (!state.items.length) drawMessage({ role: 'assistant', text: d.greeting });
    state.items.forEach(item => item.card ? drawCard(item) : drawMessage(item));
    scroll();
  }

  async function decide(item, decision, card) {
    card.querySelectorAll('button').forEach(b => { b.disabled = true; });
    let body = {}, ok = false;
    try {
      const r = await fetch(`/admin/assistant/actions/${item.card.id}/${decision}`, { method: 'POST', headers: { 'X-CSRFToken': csrf() } });
      body = await r.json(); ok = r.ok;
    } catch { body = { error: d.error }; }
    if (!ok) { card.querySelector('.admin-ai-status').textContent = body.error || d.error; card.querySelectorAll('button').forEach(b => { b.disabled = false; }); return; }
    item.status = body.status; item.message = body.message; item.link = body.link || '';
    // Tell the assistant what happened, so the next answer knows it is done.
    state.history.push({ role: 'user', content: decision === 'save' ? `[저장 완료] 확인 카드 #${item.card.id}: ${body.message}` : `[취소] 확인 카드 #${item.card.id}` },
                       { role: 'assistant', content: decision === 'save' ? '저장을 확인했어요.' : '취소를 확인했어요.' });
    save(); redraw();
  }

  function setOpen(open) {
    state.open = open; panel.hidden = !open; toggle.setAttribute('aria-expanded', String(open)); save();
    if (open) { redraw(); input.focus(); }
  }
  toggle.addEventListener('click', () => setOpen(panel.hidden));
  box.querySelector('[data-ai-close]').addEventListener('click', () => { setOpen(false); toggle.focus(); });
  box.querySelector('[data-ai-reset]').addEventListener('click', () => { state.history = []; state.items = []; pending = []; tray.hidden = true; tray.textContent = ''; save(); redraw(); });
  panel.addEventListener('keydown', e => { if (e.key === 'Escape') { e.stopPropagation(); setOpen(false); toggle.focus(); } });
  input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit(); } });

  file.addEventListener('change', async () => {
    const f = file.files[0]; file.value = '';
    if (!f) return;
    const data = new FormData(); data.append('image', f);
    let body = {}, ok = false;
    try { const r = await fetch('/admin/assistant/upload', { method: 'POST', headers: { 'X-CSRFToken': csrf() }, body: data }); body = await r.json(); ok = r.ok; }
    catch { body = { error: d.error }; }
    if (!ok) { state.items.push({ role: 'assistant error', text: body.error || d.error }); save(); redraw(); return; }
    pending.push(body);
    tray.hidden = false; tray.textContent = '';
    pending.forEach(u => { const img = el('img'); img.src = u.url; img.alt = `#${u.id}`; img.title = `#${u.id}`; tray.append(img); });
    input.focus();
  });

  form.addEventListener('submit', async e => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text || send.disabled) return;
    const images = pending.map(u => u.id), urls = pending.map(u => u.url);
    pending = []; tray.hidden = true; tray.textContent = ''; input.value = '';
    state.history.push({ role: 'user', content: text, images });
    state.items.push({ role: 'user', text: images.length ? `${text}\n${images.map(i => `[#${i}]`).join(' ')}` : text, images: urls });
    save(); redraw();
    send.disabled = true;
    const wait = drawMessage({ role: 'assistant pending', text: d.thinking }); scroll();
    let body = {}, status = 0;
    try {
      const r = await fetch('/admin/assistant/chat', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() }, body: JSON.stringify({ messages: state.history.slice(-16) }) });
      status = r.status; body = await r.json().catch(() => ({}));
    } catch { status = 0; }
    wait.remove();
    if (status === 200 && body.reply) {
      state.history.push({ role: 'assistant', content: body.reply });
      state.items.push({ role: 'assistant', text: body.reply });
      (body.actions || []).forEach(card => state.items.push({ card, status: 'pending' }));
    } else {
      state.history.pop();  // keep user / assistant turns alternating
      state.items.push({ role: 'assistant error', text: status === 503 ? d.unavailable : status === 429 ? d.limit : (body.detail || d.error) });
    }
    save(); redraw(); send.disabled = false; input.focus();
  });

  if (state.open) setOpen(true);
})();
