'use strict';
// Rebu Studio — the detail-page chatbot (README §28). History stays in this tab per product. Image cards need the admin's Allow.
(() => {
  const box = document.querySelector('[data-studio]');
  if (!box) return;
  const d = box.dataset, KEY = `reboot-studio-${d.slug}`;
  const log = box.querySelector('.studio-log'), form = box.querySelector('form'), input = form.querySelector('textarea'), send = form.querySelector('button');
  const frame = document.querySelector('[data-preview]');
  const csrf = () => document.querySelector('meta[name="csrf-token"]').content;
  let state = { history: [], items: [] };
  try { state = Object.assign(state, JSON.parse(sessionStorage.getItem(KEY) || '{}')); } catch { /* fresh */ }
  const save = () => { try { sessionStorage.setItem(KEY, JSON.stringify({ history: state.history.slice(-30), items: state.items.slice(-60) })); } catch { /* ignore */ } };
  const el = (t, c, x) => { const n = document.createElement(t); if (c) n.className = c; if (x != null) n.textContent = x; return n; };

  async function decide(item, decision, card) {
    card.querySelectorAll('button').forEach(b => { b.disabled = true; });
    let body = {};
    try {
      const r = await fetch(`/admin/products/story/${d.slug}/images/${item.event.id}/${decision}`, { method: 'POST', headers: { 'X-CSRFToken': csrf(), 'Accept': 'application/json' } });
      body = await r.json();
    } catch { body = { message: d.error }; }
    item.status = body.status || 'failed'; item.message = body.message || ''; item.url = body.url || '';
    state.history.push({ role: 'user', content: decision === 'allow' ? `[이미지 #${item.event.id} 허락 → ${item.status}] ${item.message}` : `[이미지 #${item.event.id} 취소]` },
                       { role: 'assistant', content: '확인했어요.' });
    save(); draw();
    if (item.status === 'running') setTimeout(() => location.reload(), 6000);
  }
  function card(item) {
    const e = item.event, c = el('div', 'admin-ai-card');
    if (e.type === 'draft') {
      c.append(el('strong', '', d.draftSaved));
      c.append(el('p', 'admin-ai-status', e.problems ? `${d.mustFix}: ${e.problems}` : d.draftOk));
      return c;
    }
    c.append(el('strong', '', `${d.imagePlan} #${e.id} · ${e.slot || ''}`));
    const dl = el('dl');
    [[d.provider, `${e.provider} · ${e.model}`], [d.cost, e.cost], [d.size, e.size], [d.source, e.source || '—'], [d.plan, e.plan]].forEach(([k, v]) => dl.append(el('dt', '', k), el('dd', '', v)));
    c.append(dl);
    if (item.url) { const img = el('img'); img.src = item.url; c.append(img); }
    const status = el('p', 'admin-ai-status', item.message || '');
    if (!item.status || item.status === 'proposed') {
      const row = el('div', 'admin-ai-buttons'), ok = el('button', 'btn primary', d.allow), no = el('button', 'btn', d.cancel);
      ok.type = no.type = 'button';
      ok.addEventListener('click', () => decide(item, 'allow', c)); no.addEventListener('click', () => decide(item, 'cancel', c));
      row.append(ok, no); c.append(row);
    } else status.textContent = `${item.status}${item.message ? ' — ' + item.message : ''}`;
    c.append(status); return c;
  }
  function draw() {
    log.textContent = '';
    const msg = (role, text) => { const m = el('div', `admin-ai-msg ${role}`); m.append(el('p', '', text)); log.append(m); };
    if (!state.items.length) msg('assistant', d.greeting);
    state.items.forEach(item => item.event ? log.append(card(item)) : msg(item.role, item.text));
    log.scrollTop = log.scrollHeight;
  }
  box.querySelector('[data-reset]').addEventListener('click', () => { state = { history: [], items: [] }; save(); draw(); });
  input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit(); } });
  form.addEventListener('submit', async e => {
    e.preventDefault();
    const text = input.value.trim(); if (!text || send.disabled) return;
    input.value = ''; state.history.push({ role: 'user', content: text }); state.items.push({ role: 'user', text }); save(); draw();
    send.disabled = true; const wait = el('div', 'admin-ai-msg assistant pending'); wait.append(el('p', '', d.thinking)); log.append(wait); log.scrollTop = log.scrollHeight;
    let body = {}, status = 0;
    try {
      const r = await fetch(`/admin/products/story/${d.slug}/chat`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() }, body: JSON.stringify({ messages: state.history.slice(-16) }) });
      status = r.status; body = await r.json().catch(() => ({}));
    } catch { status = 0; }
    if (status === 200 && body.reply) {
      (body.events || []).forEach(ev => state.items.push({ event: ev }));
      if (frame && (body.events || []).some(ev => ev.type === 'draft')) frame.src = frame.src;  // show the new draft
      state.history.push({ role: 'assistant', content: body.reply }); state.items.push({ role: 'assistant', text: body.reply });
    } else {
      state.history.pop();
      state.items.push({ role: 'assistant error', text: status === 503 ? d.unavailable : status === 429 ? d.limit : (body.detail || d.error) });
    }
    save(); draw(); send.disabled = false; input.focus();
  });
  draw();
})();
