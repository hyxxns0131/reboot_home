// Rebu in 3D for the motion hero. The model is a static mesh (body + hat), so every
// move here is procedural.
//  • Play mode (default): Rebu wanders around on his own, looks about, and plays —
//    happy hops, spins, little dances and hat tips, with the odd "Hehe!" bubble.
//  • Follow mode: only after Rebu is clicked. He turns to the pointer and scoots after it
//    for a few seconds (each click restarts the timer), then goes back to playing.
//  • A hop (with a spin when the product type changes) on every product switch.
// If WebGL or the model fails, nothing changes and the poster image stays.
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';

const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const ease = x => 1 - (1 - x) ** 3;
const lerp = (a, b, k) => a + (b - a) * k;

export async function mount({root, box, src}) {
  const canvas = box.querySelector('canvas');
  let renderer;
  try { renderer = new THREE.WebGLRenderer({canvas, antialias: true, alpha: true, powerPreference: 'low-power'}); }
  catch { return; }
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.NeutralToneMapping;
  renderer.toneMappingExposure = 1.05;

  const scene = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), .04).texture;
  scene.environmentIntensity = .55;
  scene.add(new THREE.HemisphereLight(0xffffff, 0x20241a, 1.1));
  const key = new THREE.DirectionalLight(0xffffff, 2.2); key.position.set(2.5, 4, 5); scene.add(key);
  const rim = new THREE.DirectionalLight(0xb0ef38, 2.4); rim.position.set(-3.5, 2.5, -3); scene.add(rim);
  const rim2 = new THREE.DirectionalLight(0xb0ef38, 1.2); rim2.position.set(3.5, 1, -2.5); scene.add(rim2);

  const camera = new THREE.PerspectiveCamera(26, 1, .05, 50);

  const gltf = await new GLTFLoader().loadAsync(src);
  const model = gltf.scene;
  const bbox = new THREE.Box3().setFromObject(model);
  const size = bbox.getSize(new THREE.Vector3()), center = bbox.getCenter(new THREE.Vector3());
  model.position.set(-center.x, -bbox.min.y, -center.z);           // feet on y=0, centred
  const fit = new THREE.Group(); fit.add(model); fit.scale.setScalar(1 / size.y); // 1 unit tall

  // Re-pivot the hat at its brim so it can tip.
  const hat = model.getObjectByName('Rebu_hat');
  const hatPivot = new THREE.Group();
  if (hat) {
    const hb = new THREE.Box3().setFromObject(hat);
    const pivot = new THREE.Vector3((hb.min.x + hb.max.x) / 2, hb.min.y, (hb.min.z + hb.max.z) / 2);
    model.add(hatPivot); hatPivot.position.copy(model.worldToLocal(pivot.clone()));
    hatPivot.attach(hat);
  }

  const squash = new THREE.Group(); squash.add(fit);     // scale (breathing / squash & stretch)
  const rig = new THREE.Group(); rig.add(squash);         // position + yaw (hops, spins, look)
  scene.add(rig);

  // shadow blob
  const shadowTex = (() => {
    const c = document.createElement('canvas'); c.width = c.height = 128;
    const g = c.getContext('2d'), gr = g.createRadialGradient(64, 64, 0, 64, 64, 64);
    gr.addColorStop(0, 'rgba(0,0,0,.55)'); gr.addColorStop(1, 'rgba(0,0,0,0)');
    g.fillStyle = gr; g.fillRect(0, 0, 128, 128); return new THREE.CanvasTexture(c);
  })();
  const shadow = new THREE.Mesh(new THREE.PlaneGeometry(.75, .75), new THREE.MeshBasicMaterial({map: shadowTex, transparent: true, depthWrite: false}));
  shadow.rotation.x = -Math.PI / 2; shadow.position.y = .001; scene.add(shadow);

  function resize() {
    const w = box.clientWidth, h = box.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    // keep the whole figure (plus hop headroom) in frame
    const dist = 1.62 / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2))) / Math.min(1, camera.aspect * 1.25);
    camera.position.set(0, .62, dist); camera.lookAt(0, .55, 0);
    camera.updateProjectionMatrix();
    dirty = true;
  }

  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const look = {x: 0, y: 0, tx: 0, ty: 0};
  const startColor = getComputedStyle(root).getPropertyValue('--flavor').trim() || '#b0ef38';
  const rimColor = new THREE.Color(startColor), rimTarget = rimColor.clone();
  let hop = null, poke = null, dance = null, dirty = true, visible = true, raf = 0, last = performance.now(), t = 0;
  // play / follow state. RANGE = how far Rebu may walk left/right of centre (model units).
  const RANGE = .25, FOLLOW_MS = 8000;
  let mode = 'play', followUntil = 0;
  const pointer = {x: 0, y: 0};
  const walk = {x: 0, tx: 0, face: 0, next: performance.now() + 1200};
  const bubble = root.querySelector('#mh-bubble');
  const say = (lines, chance = 1) => {
    if (!bubble || Math.random() > chance) return;
    bubble.textContent = lines[Math.floor(Math.random() * lines.length)];
    bubble.classList.remove('is-pop'); void bubble.offsetWidth; bubble.classList.add('is-pop');
  };

  addEventListener('pointermove', e => {
    const r = box.getBoundingClientRect();
    pointer.x = clamp((e.clientX - (r.left + r.width / 2)) / (innerWidth * .5), -1, 1);
    pointer.y = clamp((e.clientY - (r.top + r.height * .35)) / (innerHeight * .5), -1, 1);
  }, {passive: true});

  root.addEventListener('mh:switch', e => {
    const {item, dir, kindChanged} = e.detail;
    rimTarget.set(item.color);
    if (reduced.matches) { rimColor.copy(rimTarget); dirty = true; return; }
    hop = {t0: performance.now(), dur: kindChanged ? 1100 : 820, spin: kindChanged ? Math.PI * 2 * dir : 0, lean: dir, height: kindChanged ? .34 : .2};
    kick();
  });
  root.addEventListener('mh:poke', () => {
    mode = 'follow'; followUntil = performance.now() + FOLLOW_MS;   // click = "follow me"
    if (reduced.matches) return;
    poke = {t0: performance.now()}; if (!hop) hop = {t0: performance.now(), dur: 650, spin: 0, lean: 0, height: .12};
    kick();
  });

  // Decide what Rebu does next while nobody is asking him to follow.
  function play(now) {
    if (now < walk.next || hop || dance) return;
    const r = Math.random();
    if (r < .5) {                                   // stroll somewhere new
      let x; do { x = (Math.random() * 2 - 1) * RANGE; } while (Math.abs(x - walk.x) < .12);
      walk.tx = x; walk.next = now + 2400 + Math.random() * 2400;
    } else if (r < .68) {                           // happy hop with a spin
      hop = {t0: now, dur: 950, spin: Math.PI * 2 * (Math.random() < .5 ? -1 : 1), lean: 0, height: .2};
      say(['Wheee!', 'Yeehaw!', 'Hehe!'], .6); walk.next = now + 1900;
    } else if (r < .84) {                           // little dance
      dance = {t0: now, dur: 1800}; say(['La-la-la ♪', 'Hehe!', 'Dance with me!'], .5); walk.next = now + 2400;
    } else {                                        // tip the hat
      poke = {t0: now}; say(['Howdy!', 'Restart your day!'], .4); walk.next = now + 1700;
    }
  }

  function pose(now, dt) {
    if (mode === 'follow' && now > followUntil) { mode = 'play'; walk.next = now + 600; }
    if (!reduced.matches) {
      if (mode === 'follow') {
        look.tx = pointer.x; look.ty = pointer.y;
        walk.tx = clamp(pointer.x * RANGE * 1.4, -RANGE, RANGE);
      } else {
        play(now);
        look.tx = Math.sin(t * .8) * .35 + Math.sin(t * 2.3) * .08;   // looking around while playing
        look.ty = Math.sin(t * .6) * .15;
      }
    }
    const dx = walk.tx - walk.x, moving = !reduced.matches && Math.abs(dx) > .01;
    if (moving) walk.x += clamp(dx, -.32 * dt, .32 * dt);
    walk.face = lerp(walk.face, moving ? Math.sign(dx) * (mode === 'follow' ? .35 : .95) : 0, .08);

    // idle
    const bob = reduced.matches ? 0 : Math.sin(t * 2.1) * .012;
    const breathe = reduced.matches ? 0 : Math.sin(t * 4.2) * .012;
    let y = bob, sy = 1 + breathe, sxz = 1 - breathe * .6, yaw = 0, roll = reduced.matches ? 0 : Math.sin(t * 1.3) * .035, pitch = 0;

    if (hop) {
      const p = clamp((now - hop.t0) / hop.dur);
      // anticipation 0-.18, air .18-.78, land .78-1
      if (p < .18) { const k = Math.sin(p / .18 * Math.PI / 2); sy *= 1 - .16 * k; sxz *= 1 + .1 * k; }
      else if (p < .78) {
        const a = (p - .18) / .6; y += Math.sin(a * Math.PI) * hop.height;
        sy *= 1 + .08 * Math.sin(a * Math.PI); sxz *= 1 - .05 * Math.sin(a * Math.PI);
        yaw += hop.spin * ease(a); roll += -hop.lean * .18 * Math.sin(a * Math.PI);
      } else { const k = Math.sin((p - .78) / .22 * Math.PI); sy *= 1 - .12 * k; sxz *= 1 + .08 * k; yaw += hop.spin; }
      if (p >= 1) hop = null;
    }
    if (moving) {                                   // waddle while walking
      y += Math.abs(Math.sin(t * 9)) * .035; roll += Math.sin(t * 9) * .07;
    }
    if (dance) {
      const p = clamp((now - dance.t0) / dance.dur), k = Math.sin(p * Math.PI);
      roll += Math.sin(p * Math.PI * 6) * .2 * k; yaw += Math.sin(p * Math.PI * 3) * .5 * k;
      y += Math.abs(Math.sin(p * Math.PI * 6)) * .05 * k; sy *= 1 + Math.sin(p * Math.PI * 12) * .04 * k;
      if (p >= 1) dance = null;
    }
    if (poke && hatPivot) {
      const p = clamp((now - poke.t0) / 900);
      hatPivot.rotation.x = -Math.sin(p * Math.PI) * .55;
      if (p >= 1) { poke = null; hatPivot.rotation.x = 0; }
    }
    look.x = lerp(look.x, look.tx, .06); look.y = lerp(look.y, look.ty, .06);
    rig.position.set(walk.x, y, 0);
    rig.rotation.set(pitch + look.y * .12, yaw + walk.face + look.x * (moving && mode === 'play' ? .15 : .55), roll);
    shadow.position.x = walk.x;
    squash.scale.set(sxz, sy, sxz);
    shadow.scale.setScalar(1 - y * 1.2); shadow.material.opacity = 1 - y * 1.8;
    rimColor.lerp(rimTarget, .08); rim.color.copy(rimColor); rim2.color.copy(rimColor);
  }

  function frame(now) {
    raf = 0;
    const dt = Math.min(.05, (now - last) / 1000); last = now; t += dt;
    pose(now, dt);
    renderer.render(scene, camera);
    dirty = false;
    if (visible && !document.hidden && (!reduced.matches || hop || poke || dance || rimColor.getHex() !== rimTarget.getHex())) raf = requestAnimationFrame(frame);
  }
  function kick() { if (!raf) { last = performance.now(); raf = requestAnimationFrame(frame); } }

  new ResizeObserver(() => { resize(); kick(); }).observe(box);
  new IntersectionObserver(es => { visible = es.some(e => e.isIntersecting); if (visible) kick(); }).observe(box);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) kick(); });
  reduced.addEventListener?.('change', kick);

  resize();
  renderer.compile(scene, camera);
  box.classList.add('is-3d');
  kick();
}
