// Spin it: the product page's 3D viewer. The same model we print, lit like the photos, recoloured
// live from the colour picker. Drag to turn it; it turns slowly by itself when left alone.
import * as THREE from 'three';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { MeshoptDecoder } from 'three/examples/jsm/libs/meshopt_decoder.module.js';

export async function startViewer(stage, slug, colorway) {
  const [table, gltf] = await Promise.all([
    fetch(`/models/${slug}.json`).then((r) => r.json()),
    new GLTFLoader().setMeshoptDecoder(MeshoptDecoder).loadAsync(`/models/${slug}.glb`),
  ]);
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const canvas = document.createElement('canvas');
  canvas.className = 'pdp-canvas';
  canvas.setAttribute('aria-label', 'A 3D model of the product. Drag to turn it.');
  canvas.setAttribute('role', 'img');
  stage.appendChild(canvas);

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.NeutralToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  const scene = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.75;

  const model = gltf.scene;
  // three strips dots and other reserved characters from node names, so compare names without them
  const norm = (n) => n.replace(/[^a-z0-9-]/gi, '');
  const tables = Object.fromEntries(Object.entries(table.colorways).map(([cw, parts]) => [cw, Object.fromEntries(Object.entries(parts).map(([k, v]) => [norm(k), v]))]));

  // plain materials: matte plastic for the print, glass and metal for the phone
  model.traverse((o) => {
    if (!o.isMesh) return;
    o.castShadow = true;
    o.receiveShadow = true;
    const old = o.material;
    const plate = /phone-?(screen|back|lenses)/.test(o.name);
    const metal = /phone-?(frame|rings)/.test(o.name);
    o.material = new THREE.MeshStandardMaterial({
      color: old.color,
      roughness: plate ? 0.12 : metal ? 0.35 : 0.62,
      metalness: metal ? 0.9 : 0,
      // the glass plates sit a hair proud of the phone body: draw them on top so they never flicker
      polygonOffset: plate,
      polygonOffsetFactor: plate ? -2 : 0,
      polygonOffsetUnits: plate ? -2 : 0,
    });
    old.dispose();
  });
  const box = new THREE.Box3().setFromObject(model);
  const size = box.getSize(new THREE.Vector3());
  const center = box.getCenter(new THREE.Vector3());
  model.position.set(-center.x, -box.min.y, -center.z);
  const pivot = new THREE.Group();
  pivot.add(model);
  scene.add(pivot);

  const radius = size.length() / 2;
  const key = new THREE.DirectionalLight(0xfff0d8, 2.4);
  key.position.set(-radius * 3, radius * 4, radius * 2.5);
  key.castShadow = true;
  key.shadow.mapSize.set(1024, 1024);
  key.shadow.radius = 6;
  const sc = key.shadow.camera;
  sc.left = sc.bottom = -radius * 1.6;
  sc.right = sc.top = radius * 1.6;
  sc.near = radius;
  sc.far = radius * 10;
  scene.add(key, new THREE.HemisphereLight(0xfff8ec, 0x8a7a66, 0.6));
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(radius * 8, radius * 8), new THREE.ShadowMaterial({ opacity: 0.2 }));
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  scene.add(floor);

  const cam = new THREE.PerspectiveCamera(28, 1, radius / 50, radius * 40);
  const aim = new THREE.Vector3(0, size.y * 0.45, 0);

  function recolor(cw) {
    const colors = tables[cw];
    if (!colors) return;
    model.traverse((o) => {
      const c = o.isMesh && colors[norm(o.name)];
      if (c) o.material.color.set(c);
    });
  }
  recolor(colorway);

  function resize() {
    const r = stage.getBoundingClientRect();
    renderer.setSize(r.width, r.height, false);
    cam.aspect = r.width / r.height;
    const fit = radius / Math.sin(THREE.MathUtils.degToRad(cam.fov / 2)) * (cam.aspect < 1 ? 1.15 / cam.aspect ** 0.5 : 1.05);
    cam.position.set(0, aim.y + fit * 0.32, fit);
    cam.lookAt(aim);
    cam.updateProjectionMatrix();
  }
  const ro = new ResizeObserver(resize);
  ro.observe(stage);
  resize();

  // drag to turn, with a little inertia
  let yaw = -0.5;
  let pitch = 0;
  let vel = reduce ? 0 : 0.25;
  let dragging = false;
  let lastX = 0;
  let lastY = 0;
  let idle = 0;
  canvas.addEventListener('pointerdown', (e) => {
    dragging = true;
    lastX = e.clientX;
    lastY = e.clientY;
    canvas.setPointerCapture(e.pointerId);
  });
  canvas.addEventListener('pointermove', (e) => {
    if (!dragging) return;
    const dx = e.clientX - lastX;
    const dy = e.clientY - lastY;
    lastX = e.clientX;
    lastY = e.clientY;
    vel = dx * 0.012;
    yaw += vel;
    pitch = Math.max(-0.35, Math.min(0.5, pitch + dy * 0.004));
    idle = 0;
  });
  const up = () => (dragging = false);
  canvas.addEventListener('pointerup', up);
  canvas.addEventListener('pointercancel', up);

  let raf = 0;
  let last = performance.now();
  function frame(now) {
    raf = requestAnimationFrame(frame);
    const dt = Math.min((now - last) / 1000, 0.05);
    last = now;
    if (!dragging) {
      idle += dt;
      const cruise = reduce ? 0 : 0.25;
      vel += ((idle > 1.5 ? cruise : 0) * dt - vel) * 0.06;
      yaw += vel;
    }
    pivot.rotation.set(pitch, yaw, 0);
    renderer.render(scene, cam);
  }
  raf = requestAnimationFrame(frame);

  return {
    recolor,
    stop() {
      cancelAnimationFrame(raf);
      ro.disconnect();
      renderer.dispose();
      pmrem.dispose();
      canvas.remove();
    },
  };
}
