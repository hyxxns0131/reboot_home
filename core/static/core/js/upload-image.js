'use strict';
// Shared photo helper for admin uploads (README §34): any photo the browser can open (JPG, PNG, WEBP, GIF, iPhone JPEG, and
// HEIC in Safari) is resized to 2000 px and turned into WEBP *before* it is sent, so big phone photos never hit the size limit.
window.RebootImage = {
  MAX: 2000,
  async prepare(file) {
    if (!file) throw new Error('No file');
    const name = (file.name || 'photo').replace(/\.[^.]+$/, '') + '.webp';
    let bitmap;
    try { bitmap = await createImageBitmap(file); } catch {
      if (/heic|heif/i.test(file.type + file.name)) throw new Error(document.documentElement.lang === 'ko' ? 'HEIC 사진은 이 브라우저에서 열 수 없어요. JPG로 저장해서 올려 주세요.' : 'This browser cannot open HEIC photos. Save it as JPG and try again.');
      return file;  // let the server check it
    }
    const small = bitmap.width <= this.MAX && bitmap.height <= this.MAX && file.size < 4 * 1024 * 1024 && /jpe?g|png|webp/i.test(file.type);
    if (small) { bitmap.close && bitmap.close(); return file; }
    const scale = Math.min(1, this.MAX / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(bitmap.width * scale); canvas.height = Math.round(bitmap.height * scale);
    canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close && bitmap.close();
    const blob = await new Promise(r => canvas.toBlob(r, 'image/webp', 0.9));
    return blob ? new File([blob], name, { type: 'image/webp' }) : file;
  },
  async send(url, file, field = 'image', extra = {}) {
    const ko = document.documentElement.lang === 'ko';
    const ready = await this.prepare(file);
    const data = new FormData(); data.append(field, ready, ready.name || 'photo.webp');
    Object.entries(extra).forEach(([k, v]) => data.append(k, v));
    let r;
    try { r = await fetch(url, { method: 'POST', headers: { 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content, Accept: 'application/json' }, body: data }); }
    catch { throw new Error(ko ? '서버에 연결하지 못했어요. 서버가 켜져 있는지 확인해 주세요.' : 'Could not reach the server.'); }
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.error || (ko ? `업로드에 실패했어요 (HTTP ${r.status}).` : `Upload failed (HTTP ${r.status}).`));
    return body;
  },
};
