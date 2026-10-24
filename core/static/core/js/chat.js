'use strict';
// Floating support chat. The conversation lives only in this tab; the server adds the product context and calls OpenAI.
const chat = document.querySelector('[data-chat]');
if (chat) {
  const toggle = chat.querySelector('.chat-toggle'), panel = chat.querySelector('.chat-panel'), log = chat.querySelector('.chat-log');
  const form = chat.querySelector('form'), input = form.querySelector('input'), send = form.querySelector('button');
  const history = [];
  const say = (role, text) => {
    const message = document.createElement('p'); message.className = `chat-msg ${role}`; message.textContent = text;
    log.append(message); log.scrollTop = log.scrollHeight; return message;
  };
  const setOpen = open => {
    panel.hidden = !open; toggle.setAttribute('aria-expanded', String(open));
    if (open) { if (!log.childElementCount) say('assistant', chat.dataset.greeting); input.focus(); }
  };
  toggle.addEventListener('click', () => setOpen(panel.hidden));
  chat.querySelector('[data-chat-close]').addEventListener('click', () => { setOpen(false); toggle.focus(); });
  panel.addEventListener('keydown', e => { if (e.key === 'Escape') { e.stopPropagation(); setOpen(false); toggle.focus(); } });
  form.addEventListener('submit', async e => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text || send.disabled) return;
    input.value = ''; say('user', text); history.push({role:'user', content:text});
    send.disabled = true;
    const pending = say('assistant pending', chat.dataset.thinking);
    let reply = null, status = 0;
    try {
      const response = await fetch('/support/chat', {
        method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':document.querySelector('meta[name="csrf-token"]').content},
        body:JSON.stringify({messages:history.slice(-10)})
      });
      status = response.status;
      reply = response.ok ? (await response.json()).reply : null;
    } catch { reply = null; }
    pending.classList.remove('pending');
    if (reply) { pending.textContent = reply; history.push({role:'assistant', content:reply}); }
    else {
      // Drop the unanswered question so the next request still alternates user / assistant.
      history.pop();
      pending.classList.add('error');
      pending.textContent = status === 503 ? chat.dataset.unavailable : status === 429 ? chat.dataset.limit : chat.dataset.error;
    }
    send.disabled = false; input.focus();
  });
}
