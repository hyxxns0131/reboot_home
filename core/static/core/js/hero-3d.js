// Hero → company scroll scene: the product models spin in, then follow the scroll down into the ALDICOM intro.
// Without WebGL or models, nothing is added and the static hero cards stay visible.
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {MeshoptDecoder} from 'three/addons/libs/meshopt_decoder.module.js';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';

const root = document.querySelector('[data-scene-3d]');
const data = document.getElementById('scene-3d-models');
if (root && data) start(JSON.parse(data.textContent));

const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const easeOut = x => 1 - (1 - x) ** 3;
const easeInOut = x => x < .5 ? 4 * x ** 3 : 1 - (-2 * x + 2) ** 3 / 2;
const backOut = x => 1 + 2.7 * (x - 1) ** 3 + 1.7 * (x - 1) ** 2;

function start(items) {
  const canvas = root.querySelector('canvas');
  let renderer;
  try { renderer = new THREE.WebGLRenderer({canvas, antialias: true, alpha: true}); } catch { return; }
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  // Neutral tone mapping and a dim environment keep the flavor colors saturated on these very glossy scans.
  renderer.toneMapping = THREE.NeutralToneMapping;
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  const scene = new THREE.Scene();
  scene.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), .04).texture;
  scene.environmentIntensity = .35;
  scene.add(new THREE.HemisphereLight(0xffffff, 0x1c1e18, 1.2));
  const key = new THREE.DirectionalLight(0xffffff, 1.8); key.position.set(3, 5, 6); scene.add(key);
  const rim = new THREE.DirectionalLight(0xb1ff3b, 1.1); rim.position.set(-5, 2, -4); scene.add(rim);
  const camera = new THREE.PerspectiveCamera(30, 1, .1, 100); camera.position.z = 10;

  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
  const view = {w: 1, h: 1};
  let pieces = [], startedAt = 0, running = false, visible = true;

  Promise.allSettled(items.map((item, index) => loader.loadAsync(item.src).then(gltf => {
    const model = gltf.scene, box = new THREE.Box3().setFromObject(model);
    const size = box.getSize(new THREE.Vector3());
    model.position.sub(box.getCenter(new THREE.Vector3()));
    // Jelly scans come back mirror-smooth; a soft satin finish reads more like gummy.
    if (item.kind === 'jelly') model.traverse(o => { if (o.material) { o.material.roughnessMap = null; o.material.roughness = .35; o.material.metalnessMap = null; o.material.metalness = 0; } });
    const spinner = new THREE.Group(), holder = new THREE.Group();
    spinner.add(model); spinner.scale.setScalar(1 / Math.max(size.x, size.y, size.z));
    holder.add(spinner); holder.visible = false; scene.add(holder);
    pieces.push({item, index, holder, spinner, phase: index * 2.4});
  }))).then(() => {
    if (!pieces.length) return;
    pieces.sort((a, b) => a.index - b.index);
    root.classList.add('is-3d');
    resize(); startedAt = performance.now(); run();
  });

  // Hero: a slowly turning carousel beside the headline (below it on narrow screens).
  function ringPos(k, n, t) {
    const wide = view.w > view.h, angle = k / n * Math.PI * 2 + t * .15;
    const r = wide ? Math.min(view.w * .17, view.h * .3) : view.w * .34;
    return new THREE.Vector3((wide ? view.w * .2 : 0) + Math.sin(angle) * r, (wide ? -.04 : -.24) * view.h + Math.cos(angle) * r * .18, Math.cos(angle) * r);
  }
  // Company intro: jellies gather on one side of the copy and drinks on the other (top/bottom rows on narrow screens).
  function gridPos(k, n) {
    const half = Math.ceil(n / 2), side = k < half ? -1 : 1, j = k % half;
    if (view.w > view.h) {
      const rows = Math.ceil(half / 2), row = Math.floor(j / 2);
      return new THREE.Vector3(side * view.w * (.3 + (j % 2) * .11), view.h * (.24 - row * .5 / Math.max(rows - 1, 1)), 0);
    }
    return new THREE.Vector3((j / Math.max(half - 1, 1) - .5) * view.w * .8, view.h * (side < 0 ? .3 : -.38), 0);
  }

  function frame(now) {
    if (!visible) { running = false; return; }
    const t = reduced.matches ? 0 : (now - startedAt) / 1000;
    const rect = root.getBoundingClientRect();
    const p = clamp(-rect.top / Math.max(rect.height - innerHeight, 1));
    const n = pieces.length, unit = Math.min(view.w, view.h);
    pieces.forEach((piece, k) => {
      const e = easeInOut(clamp((p - .04 - k * .012) / .75));
      const intro = reduced.matches ? 1 : clamp((t - k * .09) / 1.4);
      const pos = ringPos(k, n, t).lerp(gridPos(k, n), e), arc = Math.sin(e * Math.PI);
      pos.y += (1 - easeOut(intro)) * view.h * .6 - arc * view.h * .12 + Math.sin(t * 1.2 + piece.phase) * view.h * .008;
      pos.z += arc * 1.2;
      piece.holder.position.copy(pos);
      piece.holder.rotation.set(.12, 0, arc * .3 * (k % 2 ? 1 : -1));
      piece.holder.scale.setScalar((piece.item.kind === 'drink' ? .27 : .17) * unit * backOut(intro));
      piece.holder.visible = intro > 0;
      piece.spinner.rotation.y = piece.phase + t * .5 + e * Math.PI * 2 + (1 - easeOut(intro)) * Math.PI * 4;
    });
    renderer.render(scene, camera);
    requestAnimationFrame(frame);
  }
  function run() { if (!running && pieces.length) { running = true; requestAnimationFrame(frame); } }

  function resize() {
    const {clientWidth: w, clientHeight: h} = canvas;
    renderer.setSize(w, h, false);
    camera.aspect = w / h; camera.updateProjectionMatrix();
    view.h = 2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * camera.position.z;
    view.w = view.h * camera.aspect;
  }
  addEventListener('resize', resize);
  new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; if (visible) run(); }).observe(root);
}
