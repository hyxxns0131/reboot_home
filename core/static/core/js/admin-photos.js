'use strict';
// Admin photo forms: [data-crop-form] holds a hidden file input. "Upload & crop" picks a file, "Crop current" re-crops
// the photo already on the site; either way the cropped result goes into the input and the form is submitted.
document.querySelectorAll('[data-crop-form]').forEach(form => {
  const input = form.querySelector('[data-crop-file]');
  const aspect = form.dataset.cropAspect ? Number(form.dataset.cropAspect) : null;
  const submitWith = file => {
    if (!file) return;
    RebootCropper.intoInput(input, file);
    if (form.dataset.cropNoSubmit !== undefined) {
      const prev = form.querySelector('[data-crop-preview]');
      if (prev) { prev.src = URL.createObjectURL(file); prev.hidden = false; }
      return;
    }
    form.querySelectorAll('button').forEach(b => { b.disabled = true; });
    form.submit();
  };
  const pick = form.querySelector('[data-crop-pick]');
  if (pick) pick.addEventListener('click', () => {
    const chooser = document.createElement('input'); chooser.type = 'file'; chooser.accept = input.accept || 'image/*';
    chooser.addEventListener('change', () => {
      const f = chooser.files[0]; if (!f) return;
      if (f.size > 25 * 1024 * 1024) { alert('Please choose a photo under 25 MB.'); return; }
      RebootCropper.open({ file: f, aspect }).then(submitWith).catch(err => alert(err.message));
    });
    chooser.click();
  });
  const current = form.querySelector('[data-crop-current]');
  if (current) current.addEventListener('click', () => RebootCropper.open({ src: current.dataset.cropCurrent, aspect }).then(submitWith).catch(err => alert(err.message)));
});
