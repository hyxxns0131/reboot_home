'use strict';
// Products › "Product page photos" (README §34): [+ Add photos] opens the file picker (or uploads what is already chosen);
// choosing or dropping photos uploads them right away. Photos are resized in the browser, sent one by one, then the page reloads.
document.querySelectorAll('[data-gallery-form]').forEach(form => {
  const input = form.querySelector('[data-gallery-file]'), status = form.querySelector('[data-gallery-status]');
  const button = form.querySelector('button');
  const ko = document.documentElement.lang === 'ko';
  const say = (text, bad) => { status.textContent = text; status.style.color = bad ? '#ff4da6' : ''; };
  let busy = false;
  async function upload(list) {
    const files = [...(list || [])];
    if (busy) return;
    if (!files.length) { input.click(); return; }  // nothing chosen yet: open the picker
    busy = true; button.disabled = true;
    let done = 0;
    for (const f of files) {
      say(ko ? `올리는 중 ${done + 1}/${files.length}… (${f.name})` : `Uploading ${done + 1}/${files.length}… (${f.name})`);
      try { await RebootImage.send(form.action, f, 'photo', { slug: form.querySelector('[name=slug]').value, label: form.querySelector('[name=label]').value }); done++; }
      catch (err) { say(`${f.name}: ${err.message}`, true); busy = false; button.disabled = false; input.value = ''; return; }
    }
    say(ko ? `${done}장 추가했어요. 새로고침 중…` : `${done} photo(s) added. Reloading…`);
    location.hash = `p-${form.querySelector('[name=slug]').value}`; location.reload();
  }
  form.addEventListener('submit', e => { e.preventDefault(); upload(input.files); });
  input.addEventListener('change', () => upload(input.files));
  form.addEventListener('dragover', e => { e.preventDefault(); form.classList.add('is-drop'); });
  form.addEventListener('dragleave', () => form.classList.remove('is-drop'));
  form.addEventListener('drop', e => { e.preventDefault(); form.classList.remove('is-drop'); upload(e.dataTransfer.files); });
});
