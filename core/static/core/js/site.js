'use strict';
const menu = document.querySelector('.menu-toggle');
menu?.addEventListener('click', () => {
  const open = menu.getAttribute('aria-expanded') !== 'true';
  menu.setAttribute('aria-expanded', String(open));
  document.querySelector('#navigation').classList.toggle('open', open);
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && menu?.getAttribute('aria-expanded') === 'true') {
    menu.click(); menu.focus();
  }
});
document.querySelectorAll('[data-password]').forEach(button => button.addEventListener('click', () => {
  const input = document.getElementById(button.dataset.password);
  const show = input.type === 'password';
  input.type = show ? 'text' : 'password'; button.textContent = show ? 'Hide' : 'Show';
  button.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
}));
document.querySelectorAll('[data-filter]').forEach(button => button.addEventListener('click', () => {
  document.querySelectorAll('[data-filter]').forEach(b => { b.classList.toggle('active', b === button); b.setAttribute('aria-pressed', String(b === button)); });
  document.querySelectorAll('[data-product-line]').forEach(card => { card.hidden = button.dataset.filter !== 'all' && card.dataset.productLine !== button.dataset.filter; });
}));
document.querySelectorAll('[data-slide]').forEach(button => button.addEventListener('click', () => {
  const track = document.querySelector('.product-track');
  track?.scrollBy({left: Number(button.dataset.slide) * (track.querySelector('.product-card').offsetWidth + 24), behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
}));
document.querySelectorAll('[data-flavor]').forEach(button => button.addEventListener('click', () => {
  const image = document.querySelector('.detail-cut img');
  image.parentElement.dataset.flavorCut = button.dataset.flavor;
  image.src = image.src.replace(/_(lime|lemon|cherry)_3D/, `_${button.dataset.flavor}_3D`);
  image.alt = image.alt.split(' — ')[0] + ' — ' + button.dataset.flavor + ' concept';
  document.querySelectorAll('[data-flavor]').forEach(b => { b.classList.toggle('active', b === button); b.setAttribute('aria-pressed', String(b === button)); });
}));
// A perspective card scene: the original product artwork stays intact.
const hero = document.querySelector('.hero');
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
if (hero) {
  let scheduled = false, mouseX = 0, mouseY = 0;
  function paint() {
    scheduled = false;
    if (reduced.matches) {
      document.querySelectorAll('.motion-card').forEach(card => card.style.removeProperty('transform'));
      return;
    }
    const bounds = hero.getBoundingClientRect();
    const progress = Math.max(0, Math.min(1, -bounds.top / bounds.height));
    document.querySelectorAll('.motion-card').forEach((card, i) => {
      const depth = Number(card.dataset.depth), base = i === 0 ? -14 : 11;
      card.style.transform = `translate3d(${progress * (i === 0 ? -60 : 45)}px, ${-progress * 110 * depth}px, ${depth * 25}px) rotateX(${progress * 22 + mouseY * -5}deg) rotateY(${progress * (i === 0 ? -22 : 28) + mouseX * 8}deg) rotateZ(${base + progress * (i === 0 ? -12 : 13)}deg)`;
    });
  }
  function schedule() { if (!scheduled) { scheduled = true; requestAnimationFrame(paint); } }
  window.addEventListener('scroll', schedule, {passive:true});
  hero.addEventListener('pointermove', e => {
    if (e.pointerType !== 'mouse') return;
    const rect = hero.getBoundingClientRect();
    mouseX = (e.clientX - rect.left) / rect.width - .5;
    mouseY = (e.clientY - rect.top) / rect.height - .5;
    schedule();
  });
  hero.addEventListener('pointerleave', () => { mouseX = 0; mouseY = 0; schedule(); });
  reduced.addEventListener('change', schedule); schedule();
}
const quiz = document.getElementById('quiz');
if (quiz) {
  const questions = [
    {title:'What’s your ideal change of pace?', answers:['A little adventure, out and about','A calm moment, all to myself']},
    {title:'Pick your everyday sidekick.', answers:['Something small for my bag','A little bottle for my shelf']},
    {title:'Your playlist needs…', answers:['The original favorites','A fresh remix']}
  ];
  let step = 0, answers = [];
  function render() {
    quiz.replaceChildren();
    const progress = document.createElement('div'); progress.className = 'progress';
    const fill = document.createElement('span'); fill.style.width = `${step / 3 * 100}%`; progress.append(fill); quiz.append(progress);
    const label = document.createElement('p'); label.className = 'eyebrow'; label.textContent = `QUESTION ${step + 1} / 3`; quiz.append(label);
    const title = document.createElement('h2'); title.textContent = questions[step].title; title.tabIndex = -1; quiz.append(title);
    const options = document.createElement('div'); options.className = 'quiz-options';
    questions[step].answers.forEach((answer, index) => {
      const button = document.createElement('button'); button.textContent = answer + ' ↗';
      button.addEventListener('click', () => { answers[step] = index; step++; step < questions.length ? render() : result(); }); options.append(button);
    });
    quiz.append(options);
    if (step > 0) { const back = document.createElement('button'); back.className = 'btn'; back.textContent = '← Previous'; back.onclick = () => { step--; render(); }; quiz.append(back); }
    title.focus({preventScroll:true});
  }
  function result() {
    const format = answers[1] === 0 ? 'Jelly' : 'Drink';
    const variant = answers[2] === 0 ? 'Original' : 'Balance';
    const vibe = answers[0] === 0 ? 'THE EVERYDAY EXPLORER' : 'THE SLOW-MOMENT SEEKER';
    quiz.innerHTML = `<p class="eyebrow">${vibe}</p><h2>Your match:<br>Reboot ${format} ${variant}</h2><p>A playful match based on your preferences. No health claims, just your kind of format.</p><a class="btn primary" href="/products/${format.toLowerCase()}-${variant.toLowerCase()}">Meet your Reboot ↗</a><button class="btn" id="quiz-reset">Take it again ↻</button>`;
    quiz.querySelector('#quiz-reset').onclick = () => { step = 0; answers = []; render(); };
    const title = quiz.querySelector('h2'); title.tabIndex = -1; title.focus({preventScroll:true});
  }
  document.getElementById('quiz-start').addEventListener('click', render);
}
