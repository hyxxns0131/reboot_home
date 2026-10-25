'use strict';
// Per-tab AI workspace (README §30): chat on the left, live draft on the right. History per tab lives in this browser tab.
(() => {
  const root = document.querySelector('[data-ws]');
  if (!root) return;
  const kind = root.dataset.kind, ko = !!root.dataset.ko, KEY = `reboot-ws-${kind}`;
  const L = (en, k) => (ko ? k : en);
  const required = JSON.parse(root.dataset.required);
  const log = root.querySelector('.studio-log'), form = root.querySelector('form'), input = form.querySelector('textarea'), send = form.querySelector('button[type=submit]');
  const file = form.querySelector('input[type=file]'), tray = root.querySelector('.admin-ai-attach');
  const $ = s => root.querySelector(s);
  const csrf = () => document.querySelector('meta[name="csrf-token"]').content;
  const el = (t, c, x) => { const n = document.createElement(t); if (c) n.className = c; if (x != null) n.textContent = x; return n; };
  let chat = { history: [], items: [] }, pending = [], current = JSON.parse(root.dataset.state);
  try { chat = Object.assign(chat, JSON.parse(sessionStorage.getItem(KEY) || '{}')); } catch { /* fresh */ }
  const keep = () => { try { sessionStorage.setItem(KEY, JSON.stringify({ history: chat.history.slice(-30), items: chat.items.slice(-60) })); } catch { /* ignore */ } };
  const GREET = {
    product: L('Hi! I’m Rebu Merchandiser. Tell me about the product you want to add — rough notes are fine — and attach a photo with 📎. We’ll decide the name, flavors, options and prices together, and you’ll see each one land in the draft on the right.',
               '안녕하세요, 상품 등록 AI 리부 머천다이저예요. 등록하고 싶은 상품을 대충 말씀해 주시고 📎로 사진을 붙여 주세요. 상품명·맛·옵션·가격을 함께 정하고, 정해지는 대로 오른쪽 초안에 바로 보여 드릴게요.'),
    popup: L('Hi! I’m Rebu Promoter. What should the popup announce, and for which dates? Attach a photo with 📎 if you have one.',
             '안녕하세요, 팝업 AI 리부 프로모터예요. 어떤 내용을 언제부터 언제까지 알릴까요? 사진이 있으면 📎로 붙여 주세요.'),
    creator: L('Hi! I’m Rebu Partnerships. Which creator and platform is this link for?',
               '안녕하세요, 크리에이터 링크 AI예요. 어떤 크리에이터, 어떤 플랫폼(Instagram/TikTok)용 링크인가요?'),
  }[kind];

  // ---------- live draft ----------
  const row = (k, v) => { const r = el('div', 'ws-row'); r.append(el('span', '', k), el('b', '', v == null || v === '' ? '—' : String(v))); return r; };
  function mock(f) {
    const box = $('[data-ws-mock]'); box.textContent = '';
    if (kind === 'product') {
      const card = el('div', 'ws-product');
      if (current.image) { const i = el('img'); i.src = current.image; card.append(i); } else card.append(el('div', 'ws-ph', L('Photo', '상품 사진')));
      if (f.badge) card.append(el('span', 'ws-badge', f.badge));
      card.append(el('h4', '', f.name || L('Product name', '상품명')));
      card.append(el('p', 'ws-sub', [f.line, f.version && (f.version === 'balance' ? 'Balance · Zero Sugar' : 'Original')].filter(Boolean).join(' · ') || '—'));
      if (f.tagline) card.append(el('p', 'ws-tag', f.tagline));
      const flv = el('div', 'ws-chips'); String(Array.isArray(f.flavors) ? f.flavors.join(',') : (f.flavors || '')).split(',').filter(x => x.trim()).forEach(x => flv.append(el('span', '', x.trim()))); card.append(flv);
      card.append(row(L('Format', '형태'), f.format), row(L('Pack', '포장'), f.pack), row(L('Volume', '용량'), f.volume));
      const opts = el('table', 'ws-opts'); (f.options || []).forEach(o => { const tr = el('tr'); tr.append(el('td', '', o.label), el('td', '', o.price != null ? `$${Number(o.price).toFixed(2)}` : '—'), el('td', '', `×${o.pieces || 1}`), el('td', '', `${L('stock', '재고')} ${o.stock ?? 0}`)); opts.append(tr); });
      if ((f.options || []).length) card.append(opts); else card.append(row(L('Options', '판매 옵션'), ''));
      card.append(row(L('Status', '공개'), 'publish' in f ? (f.publish ? L('Live now', '바로 공개') : L('Hidden', '숨김')) : ''));
      box.append(card);
    } else if (kind === 'popup') {
      const p = el('div', 'ws-popup');
      if (current.image) { const i = el('img'); i.src = current.image; p.append(i); }
      p.append(el('h4', '', f.title || L('Popup title', '팝업 제목')));
      if (f.body) p.append(el('p', '', f.body));
      if (f.button_label) p.append(el('span', 'btn primary', f.button_label));
      box.append(p, row(L('Button link', '버튼 링크'), f.button_link), row(L('Show on', '노출 위치'), f.placement === 'all' ? L('Every page', '모든 페이지') : f.placement ? L('Home page only', '홈페이지만') : ''),
                 row(L('Period', '기간'), f.no_period ? L('No end (always)', '기간 없이 계속') : (f.starts_on ? `${f.starts_on} → ${f.ends_on || L('no end', '종료일 없음')}` : '')));
    } else {
      const c = el('div', 'ws-creator');
      c.append(el('span', 'ws-badge', f.platform || L('Platform', '플랫폼')), el('h4', '', f.name || L('Creator', '크리에이터')), el('p', 'ws-code', f.code ? `/r/${f.code}` : L('/r/CODE (auto if empty)', '/r/코드 (비우면 자동)')));
      box.append(c, row(L('Customer discount', '고객 할인'), f.discount != null ? `${f.discount}%` : ''), row(L('Commission', '수수료'), f.commission != null ? `${f.commission}%` : ''),
                 row(L('Opens', '도착 페이지'), f.landing || (('name' in f) ? L('Home', '홈') : '')));
    }
  }
  function render(st) {
    current = st;
    mock(st.fields || {});
    const check = $('[data-ws-check]'); check.textContent = '';
    required.forEach(([key, k, en]) => { const label = ko ? k : en; const done = !st.missing.includes(label); const li = el('li', done ? 'done' : '', `${done ? '✓' : '○'} ${label}`); check.append(li); });
    const pr = $('[data-ws-problems]'); pr.textContent = '';
    if (st.problems.length) { const b = el('div', 'admin-alert'); b.textContent = st.problems.join('\n'); pr.append(b); }
    const s = $('[data-ws-status]'); s.textContent = st.ready ? L('Ready to save', '저장 가능') : L('In progress', '작성 중'); s.classList.toggle('ok', st.ready);
    $('[data-ws-save]').disabled = !st.ready;
    root.querySelector('.ws-live').classList.remove('flash'); void root.offsetWidth; root.querySelector('.ws-live').classList.add('flash');
  }

  // ---------- chat ----------
  function draw() {
    log.textContent = '';
    const msg = (role, text, images) => { const m = el('div', `admin-ai-msg ${role}`); m.append(el('p', '', text)); (images || []).forEach(u => { const i = el('img'); i.src = u; m.append(i); }); log.append(m); };
    if (!chat.items.length) msg('assistant', GREET);
    chat.items.forEach(it => msg(it.role, it.text, it.images));
    log.scrollTop = log.scrollHeight;
  }
  // Photo: resized in the browser, saved, and put into the draft right away (README §34). Also drag & drop or paste.
  async function attach(f) {
    if (!f) return;
    const note = el('div', 'admin-ai-msg assistant pending'); note.append(el('p', '', L('Uploading the photo…', '사진 올리는 중…'))); log.append(note); log.scrollTop = log.scrollHeight;
    try {
      const body = await RebootImage.send(`/admin/ai/${kind}/upload`, f);
      pending.push(body); tray.hidden = false; tray.textContent = '';
      pending.forEach(u => { const i = el('img'); i.src = u.url; i.title = `#${u.id}`; tray.append(i); });
      if (body.state) render(body.state);
      chat.items.push({ role: 'assistant', text: L(`Photo #${body.id} is in the draft on the right. Tell me about the product and I’ll fill in the rest.`, `사진 #${body.id}를 오른쪽 초안에 넣었어요. 상품 설명을 보내 주시면 나머지도 채울게요.`), images: [body.url] });
    } catch (err) {
      chat.items.push({ role: 'assistant error', text: err.message || L('Upload failed.', '업로드에 실패했어요.') });
    }
    keep(); draw();
  }
  file.addEventListener('change', () => { const f = file.files[0]; file.value = ''; attach(f); });
  root.addEventListener('dragover', e => { if ([...e.dataTransfer.types].includes('Files')) { e.preventDefault(); root.classList.add('is-drop'); } });
  root.addEventListener('dragleave', () => root.classList.remove('is-drop'));
  root.addEventListener('drop', e => { root.classList.remove('is-drop'); const f = [...(e.dataTransfer.files || [])].find(x => x.type.startsWith('image/') || /heic/i.test(x.name)); if (f) { e.preventDefault(); attach(f); } });
  input.addEventListener('paste', e => { const f = [...(e.clipboardData.files || [])].find(x => x.type.startsWith('image/')); if (f) { e.preventDefault(); attach(f); } });
  input.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); form.requestSubmit(); } });
  form.addEventListener('submit', async e => {
    e.preventDefault();
    const text = input.value.trim(); if (!text || send.disabled) return;
    const images = pending.map(u => u.id), urls = pending.map(u => u.url);
    pending = []; tray.hidden = true; tray.textContent = ''; input.value = '';
    chat.history.push({ role: 'user', content: text, images }); chat.items.push({ role: 'user', text, images: urls }); keep(); draw();
    send.disabled = true; const wait = el('div', 'admin-ai-msg assistant pending'); wait.append(el('p', '', L('Working on it…', '작성 중…'))); log.append(wait); log.scrollTop = log.scrollHeight;
    let body = {}, status = 0;
    try {
      const r = await fetch(`/admin/ai/${kind}/chat`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf() }, body: JSON.stringify({ messages: chat.history.slice(-16) }) });
      status = r.status; body = await r.json().catch(() => ({}));
    } catch { status = 0; }
    if (status === 200 && body.reply) {
      chat.history.push({ role: 'assistant', content: body.reply }); chat.items.push({ role: 'assistant', text: body.reply });
      if (body.state) render(body.state);
    } else {
      chat.history.pop();
      chat.items.push({ role: 'assistant error', text: status === 503 ? L('An OpenAI key is needed (Settings › API connections).', 'OpenAI 키가 필요해요 (설정 › API 연결).') : status === 429 ? L('Too many messages. Try again soon.', '메시지가 너무 많아요. 잠시 후 다시.') : (body.detail || L('Something went wrong.', '문제가 생겼어요.')) });
    }
    keep(); draw(); send.disabled = false; input.focus();
  });
  $('[data-ws-newchat]').addEventListener('click', () => { chat = { history: [], items: [] }; keep(); draw(); });
  $('[data-ws-reset]').addEventListener('click', async () => {
    const r = await fetch(`/admin/ai/${kind}/reset`, { method: 'POST', headers: { 'X-CSRFToken': csrf() } }); const b = await r.json(); render(b.state); $('[data-ws-result]').textContent = '';
  });
  $('[data-ws-save]').addEventListener('click', async () => {
    const btn = $('[data-ws-save]'); btn.disabled = true;
    let b = {}, ok = false;
    try { const r = await fetch(`/admin/ai/${kind}/save`, { method: 'POST', headers: { 'X-CSRFToken': csrf() } }); b = await r.json(); ok = r.ok; } catch { b = {}; }
    const out = $('[data-ws-result]'); out.textContent = ok ? `✓ ${b.message} ` : (b.error || L('Could not save.', '저장하지 못했어요.'));
    if (ok) {
      if (b.link) { const a = el('a', 'text-link', L('Open →', '열기 →')); a.href = b.link; out.append(a); }
      chat.history.push({ role: 'user', content: `[저장 완료] ${b.message}` }, { role: 'assistant', content: L('Saved. Want to make another one?', '저장됐어요. 하나 더 만들까요?') });
      chat.items.push({ role: 'assistant', text: L('Saved. Want to make another one?', '저장됐어요. 하나 더 만들까요?') }); keep(); draw();
      const r = await fetch(`/admin/ai/${kind}/state`); render((await r.json()).state);
    } else btn.disabled = false;
  });
  draw(); render(current);
})();
