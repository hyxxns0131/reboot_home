'use strict';
// Products › "Product page photos" (README §34): photos are resized in the browser, sent one by one, then the page reloads.
document.querySelectorAll('[data-gallery-form]').forEach(form => {
  const input = form.querySelector('[data-gallery-file]'), status = form.querySelector('[data-gallery-status]');
  const ko = document.documentElement.lang === 'ko';
  async function upload(files) {
    files = [...files].filter(f => f.type.startsWith('image/') || /heic|heif/i.test(f.name));
    if (!files.length) return;
    form.querySelectorAll('button').forEach(b => { b.disabled = true; });
    let done = 0;
    for (const f of files) {
      status.textContent = ko ? `올리는 중 ${done + 1}/${files.length}…` : `Uploading ${done + 1}/${files.length}…`;
      try { await RebootImage.send(form.action, f, 'photo', { slug: form.slug.value, label: form.label.value }); done++; }
      catch (err) { status.textContent = `${f.name}: ${err.message}`; form.querySelectorAll('button').forEach(b => { b.disabled = false; }); return; }
    }
    location.hash = `p-${form.slug.value}`; location.reload();
  }
  form.addEventListener('submit', e => { e.preventDefault(); upload(input.files); });
  input.addEventListener('change', () => upload(input.files));
  form.addEventListener('dragover', e => { e.preventDefault(); form.classList.add('is-drop'); });
  form.addEventListener('dragleave', () => form.classList.remove('is-drop'));
  form.addEventListener('drop', e => { e.preventDefault(); form.classList.remove('is-drop'); upload(e.dataTransfer.files); });
});
