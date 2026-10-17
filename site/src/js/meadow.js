// The hero: our logo as a place. A flat, ink-outlined sky (sun, rays, hills, clouds) behind a
// field of real grass you can push around with a finger or the mouse. Tap and flowers come up.
import * as THREE from 'three';

const HEX = { moss: 0x2f5d3a, mossDeep: 0x24452d, sprout: 0x9bc53d, sun: 0xf2c14e, cream: 0xf6f1e4, ink: 0x2a2420, clay: 0xd9764a, bloom: 0xe9a6a0 };
const col = (h) => new THREE.Color(h);

// ---------------------------------------------------------------- flat backdrop pieces

const flat = (geo, hex, z) => {
  const m = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: hex, depthTest: false, depthWrite: false }));
  m.renderOrder = z;
  return m;
};

function ellipse(rx, ry, seg = 128) {
  const s = new THREE.Shape();
  s.absellipse(0, 0, rx, ry, 0, Math.PI * 2, false, 0);
  return new THREE.ShapeGeometry(s, seg);
}

function pill(w, h) {
  const r = w / 2;
  const s = new THREE.Shape();
  s.moveTo(-r, 0);
  s.lineTo(-r, h - r);
  s.absarc(0, h - r, r, Math.PI, 0, true);
  s.lineTo(r, 0);
  s.absarc(0, 0, r, 0, Math.PI, true);
  return new THREE.ShapeGeometry(s, 12);
}

function outlined(geoFill, geoInk, fill, z) {
  const g = new THREE.Group();
  g.add(flat(geoInk, HEX.ink, z), flat(geoFill, fill, z + 0.5));
  return g;
}

function cloud(scale) {
  const g = new THREE.Group();
  const puffs = [[-0.22, 0, 0.16], [-0.05, 0.07, 0.2], [0.14, 0.02, 0.17], [0.3, -0.02, 0.12]];
  const ink = new THREE.MeshBasicMaterial({ color: HEX.ink, depthTest: false, depthWrite: false });
  const fill = new THREE.MeshBasicMaterial({ color: HEX.cream, depthTest: false, depthWrite: false });
  for (const [x, y, r] of puffs) {
    const a = new THREE.Mesh(new THREE.CircleGeometry(r + 0.022, 48), ink);
    a.position.set(x, y, 0);
    a.renderOrder = 3;
    g.add(a);
  }
  const base = new THREE.Mesh(new THREE.PlaneGeometry(0.62, 0.1), ink);
  base.position.set(0.04, -0.075, 0);
  base.renderOrder = 3;
  g.add(base);
  for (const [x, y, r] of puffs) {
    const b = new THREE.Mesh(new THREE.CircleGeometry(r, 48), fill);
    b.position.set(x, y, 0);
    b.renderOrder = 3.5;
    g.add(b);
  }
  const cut = new THREE.Mesh(new THREE.PlaneGeometry(0.6, 0.12), fill);
  cut.position.set(0.04, -0.05, 0);
  cut.renderOrder = 3.6;
  g.add(cut);
  g.scale.setScalar(scale);
  return g;
}

// ---------------------------------------------------------------- grass

function bladeGeometry(segs = 6) {
  const pos = [];
  const uv = [];
  const idx = [];
  for (let i = 0; i <= segs; i++) {
    const t = i / segs;
    const w = 0.5 * Math.pow(1 - t, 0.85) + 0.015;
    pos.push(-w, t, 0, w, t, 0);
    uv.push(0, t, 1, t);
  }
  for (let i = 0; i < segs; i++) {
    const a = i * 2;
    idx.push(a, a + 1, a + 2, a + 1, a + 3, a + 2);
  }
  const g = new THREE.InstancedBufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  g.setIndex(idx);
  return g;
}

const GRASS_VS = /* glsl */ `
uniform float uTime;
uniform float uGrow;
uniform vec3 uPointer;
uniform float uPush;
uniform float uWind;
attribute vec4 aOffset;
attribute vec3 aParams;
varying float vH;
varying float vVar;
varying float vEdge;
varying float vFar;
varying float vShade;
void main() {
  float h = position.y;
  float s = aParams.x * uGrow;
  vec3 p = vec3(position.x * 0.11 * (0.8 + aParams.y * 0.5), h * 0.62 * s, 0.0);
  float c = cos(aOffset.w), sn = sin(aOffset.w);
  p = vec3(c * p.x, p.y, sn * p.x);
  vec3 w = aOffset.xyz + p;
  float t = uTime;
  float gust = sin(t * 0.55 + aOffset.x * 0.18) * 0.5 + 0.5;
  float sway = sin(t * 1.7 + aOffset.x * 0.55 + aOffset.z * 0.35 + aParams.z) * (0.35 + gust * 0.45)
             + sin(t * 3.1 + aOffset.z * 1.7 + aParams.z * 3.0) * 0.12;
  vec2 bend = vec2(0.9, 0.3) * sway * 0.22 * uWind;
  vec2 d = aOffset.xz - uPointer.xz;
  float dist = length(d);
  float f = smoothstep(0.95, 0.0, dist) * uPush;
  bend += (d / max(dist, 0.001)) * f * 0.95;
  float k = h * h;
  w.xz += bend * k * s;
  w.y -= length(bend) * k * 0.32 * s;
  vec4 mv = viewMatrix * vec4(w, 1.0);
  vH = h;
  vVar = aParams.y;
  vEdge = uv.x;
  vFar = smoothstep(3.0, 22.0, -mv.z);
  vShade = 0.86 + 0.14 * sin(aOffset.w * 2.0 + 1.3);
  gl_Position = projectionMatrix * mv;
}`;

const GRASS_FS = /* glsl */ `
uniform vec3 uBase;
uniform vec3 uTip;
uniform vec3 uTip2;
uniform vec3 uInk;
uniform vec3 uFar;
varying float vH;
varying float vVar;
varying float vEdge;
varying float vFar;
varying float vShade;
void main() {
  vec3 tip = mix(uTip, uTip2, step(0.78, vVar));
  vec3 c = mix(uBase, tip, smoothstep(0.0, 0.95, vH));
  c *= vShade * (0.9 + vVar * 0.22);
  float e = min(vEdge, 1.0 - vEdge);
  float ink = (1.0 - smoothstep(0.0, 0.2, e)) * (1.0 - vFar) * 0.55;
  c = mix(c, uInk, ink);
  c = mix(c, uFar, vFar * 0.6);
  gl_FragColor = vec4(c, 1.0);
  #include <colorspace_fragment>
}`;

// ---------------------------------------------------------------- flowers

const FLOWER_VS = /* glsl */ `
uniform float uTime;
attribute vec4 aFlower;
attribute vec3 aPetal;
attribute float aPart;
varying vec2 vUv;
varying float vPart;
varying vec3 vPetal;
float elastic(float t) { return t >= 1.0 ? 1.0 : 1.0 - pow(2.0, -9.0 * t) * cos(t * 11.0); }
void main() {
  float age = uTime - aFlower.w;
  float grow = 1.0 - pow(1.0 - clamp(age / 0.8, 0.0, 1.0), 3.0);
  float pop = elastic(clamp((age - 0.25) / 0.9, 0.0, 1.0));
  vec3 base = aFlower.xyz;
  float sway = sin(uTime * 1.6 + base.x * 0.55 + base.z * 0.35) * 0.05;
  vec3 top = base + vec3(sway, 0.5 * grow, 0.0);
  vec4 mv;
  if (aPart < 0.5) {
    vec3 p = mix(base, top, position.y) + vec3(position.x, 0.0, 0.0);
    mv = viewMatrix * vec4(p, 1.0);
  } else {
    mv = viewMatrix * vec4(top, 1.0);
    mv.xy += position.xy * 0.13 * pop;
  }
  vUv = position.xy;
  vPart = aPart;
  vPetal = aPetal;
  gl_Position = projectionMatrix * mv;
}`;

const FLOWER_FS = /* glsl */ `
uniform vec3 uInk;
uniform vec3 uSun;
uniform vec3 uStem;
varying vec2 vUv;
varying float vPart;
varying vec3 vPetal;
void main() {
  vec3 c = uStem;
  if (vPart > 0.5) {
    float r = length(vUv);
    float a = atan(vUv.y, vUv.x);
    float petal = 0.58 + 0.42 * pow(abs(cos(a * 3.0)), 0.7);
    float edge = r - petal * 0.94;
    if (edge > 0.0) discard;
    c = vPetal;
    if (edge > -0.13) c = uInk;
    if (r < 0.36) c = uInk;
    if (r < 0.27) c = uSun;
  }
  gl_FragColor = vec4(c, 1.0);
  #include <colorspace_fragment>
}`;

function flowerGeometry(n) {
  const base = new THREE.BufferGeometry();
  const pos = [-0.012, 0, 0, 0.012, 0, 0, -0.012, 1, 0, 0.012, 1, 0, -1, -1, 0, 1, -1, 0, -1, 1, 0, 1, 1, 0];
  const part = [0, 0, 0, 0, 1, 1, 1, 1];
  const g = new THREE.InstancedBufferGeometry();
  g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  g.setAttribute('aPart', new THREE.Float32BufferAttribute(part, 1));
  g.setIndex([0, 1, 2, 1, 3, 2, 4, 5, 6, 5, 7, 6]);
  const flower = new Float32Array(n * 4);
  for (let i = 0; i < n; i++) flower.set([0, -50, 0, -100], i * 4);
  g.setAttribute('aFlower', new THREE.InstancedBufferAttribute(flower, 4).setUsage(THREE.DynamicDrawUsage));
  g.setAttribute('aPetal', new THREE.InstancedBufferAttribute(new Float32Array(n * 3), 3).setUsage(THREE.DynamicDrawUsage));
  g.instanceCount = n;
  base.dispose();
  return g;
}

// ---------------------------------------------------------------- the scene

export function startMeadow(canvas, hero) {
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const coarse = matchMedia('(pointer: coarse)').matches;
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'high-performance' });
  renderer.setClearColor(0x000000, 0);
  renderer.autoClear = false;
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  // flat sky
  const back = new THREE.Scene();
  const ortho = new THREE.OrthographicCamera(-1, 1, 1, -1, -10, 10);
  const sun = new THREE.Group();
  const SUN_R = 1;
  sun.add(outlined(new THREE.CircleGeometry(SUN_R, 128), new THREE.CircleGeometry(SUN_R + 0.075, 128), HEX.sun, 2));
  const rays = new THREE.Group();
  for (let i = 0; i < 9; i++) {
    const a = THREE.MathUtils.degToRad(12 + i * 19.5);
    const r = flat(pill(0.085, 0.3), HEX.ink, 1.5);
    r.position.set(Math.cos(a) * 1.28, Math.sin(a) * 1.28, 0);
    r.rotation.z = a - Math.PI / 2;
    rays.add(r);
  }
  sun.add(rays);
  back.add(sun);
  const farHill = outlined(ellipse(1, 1), ellipse(1, 1), HEX.sprout, 4);
  const nearHill = outlined(ellipse(1, 1), ellipse(1, 1), HEX.moss, 6);
  back.add(farHill, nearHill);
  const clouds = [cloud(0.55), cloud(0.42), cloud(0.34)];
  clouds.forEach((c) => back.add(c));

  // the meadow
  const scene = new THREE.Scene();
  const cam = new THREE.PerspectiveCamera(32, 1, 0.1, 140);
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(200, 200), new THREE.MeshBasicMaterial({ color: HEX.moss }));
  ground.rotation.x = -Math.PI / 2;
  scene.add(ground);

  const N = coarse || innerWidth < 800 ? 12000 : 26000;
  const box = hero.getBoundingClientRect();
  const startAspect = Math.max(0.4, box.width / Math.max(1, box.height));
  const tanH = Math.tan(THREE.MathUtils.degToRad(startAspect < 0.9 ? 22 : 15)) * Math.max(startAspect, 1.25);
  const grassGeo = bladeGeometry();
  const offs = new Float32Array(N * 4);
  const params = new Float32Array(N * 3);
  for (let i = 0; i < N; i++) {
    const z = 4.4 - Math.pow(Math.random(), 0.8) * 26;
    const spread = (6.4 - z) * tanH * 1.12 + 0.7;
    offs.set([(Math.random() * 2 - 1) * spread, 0, z, Math.random() * Math.PI], i * 4);
    params.set([0.65 + Math.random() * 0.75, Math.random(), Math.random() * 6.28], i * 3);
  }
  grassGeo.setAttribute('aOffset', new THREE.InstancedBufferAttribute(offs, 4));
  grassGeo.setAttribute('aParams', new THREE.InstancedBufferAttribute(params, 3));
  grassGeo.instanceCount = N;
  const grassMat = new THREE.ShaderMaterial({
    vertexShader: GRASS_VS,
    fragmentShader: GRASS_FS,
    side: THREE.DoubleSide,
    uniforms: {
      uTime: { value: 0 },
      uGrow: { value: reduce ? 1 : 0 },
      uPointer: { value: new THREE.Vector3(0, 0, 100) },
      uPush: { value: 0 },
      uWind: { value: reduce ? 0 : 1 },
      uBase: { value: col(HEX.mossDeep) },
      uTip: { value: col(HEX.sprout) },
      uTip2: { value: col(0xc4dc6a) },
      uInk: { value: col(HEX.ink) },
      uFar: { value: col(HEX.moss) },
    },
  });
  const grass = new THREE.Mesh(grassGeo, grassMat);
  grass.frustumCulled = false;
  scene.add(grass);

  const F = 260;
  const flowerGeo = flowerGeometry(F);
  const flowerMat = new THREE.ShaderMaterial({
    vertexShader: FLOWER_VS,
    fragmentShader: FLOWER_FS,
    side: THREE.DoubleSide,
    uniforms: { uTime: grassMat.uniforms.uTime, uInk: { value: col(HEX.ink) }, uSun: { value: col(HEX.sun) }, uStem: { value: col(HEX.mossDeep) } },
  });
  const flowers = new THREE.Mesh(flowerGeo, flowerMat);
  flowers.frustumCulled = false;
  scene.add(flowers);
  const petals = [HEX.cream, HEX.cream, HEX.bloom, 0xffffff, HEX.clay].map(col);

  // pollen: soft specks drifting up through the light
  const P = coarse ? 90 : 180;
  const pollenPos = new Float32Array(P * 3);
  const pollenSeed = new Float32Array(P);
  for (let i = 0; i < P; i++) {
    pollenPos.set([(Math.random() * 2 - 1) * 6, Math.random() * 1.6, 4 - Math.random() * 12], i * 3);
    pollenSeed[i] = Math.random() * 100;
  }
  const pollenGeo = new THREE.BufferGeometry();
  pollenGeo.setAttribute('position', new THREE.BufferAttribute(pollenPos, 3));
  pollenGeo.setAttribute('aSeed', new THREE.BufferAttribute(pollenSeed, 1));
  const pollenMat = new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    uniforms: { uTime: grassMat.uniforms.uTime, uWind: grassMat.uniforms.uWind, uPx: { value: renderer.getPixelRatio() }, uColor: { value: col(0xfff2c4) } },
    vertexShader: /* glsl */ `
      uniform float uTime; uniform float uWind; uniform float uPx;
      attribute float aSeed;
      varying float vA;
      void main() {
        vec3 p = position;
        float t = uTime * uWind;
        p.y = mod(p.y + t * (0.05 + fract(aSeed) * 0.06), 1.8);
        p.x += sin(t * 0.4 + aSeed) * 0.25;
        p.z += cos(t * 0.3 + aSeed * 1.7) * 0.2;
        vec4 mv = viewMatrix * vec4(p, 1.0);
        gl_Position = projectionMatrix * mv;
        gl_PointSize = uPx * (2.0 + fract(aSeed * 3.1) * 3.0) * (6.0 / -mv.z);
        vA = smoothstep(0.0, 0.3, p.y) * smoothstep(1.8, 1.2, p.y) * (0.35 + 0.65 * fract(aSeed * 7.3));
      }`,
    fragmentShader: /* glsl */ `
      uniform vec3 uColor;
      varying float vA;
      void main() {
        float d = length(gl_PointCoord - 0.5);
        float a = smoothstep(0.5, 0.0, d) * vA * 0.75;
        gl_FragColor = vec4(uColor, a);
        #include <colorspace_fragment>
      }`,
  });
  const pollen = new THREE.Points(pollenGeo, pollenMat);
  pollen.frustumCulled = false;
  scene.add(pollen);
  let next = 0;

  function bloom(x, z, t) {
    const fa = flowerGeo.attributes.aFlower;
    const pa = flowerGeo.attributes.aPetal;
    fa.array.set([x, 0, z, t], next * 4);
    const c = petals[(Math.random() * petals.length) | 0];
    pa.array.set([c.r, c.g, c.b], next * 3);
    next = (next + 1) % F;
    fa.needsUpdate = true;
    pa.needsUpdate = true;
  }

  // ------------------------------------------------------------ layout

  const view = { w: 1, h: 1, aspect: 1, horizon: 0 };
  let dprCap = coarse ? 1.6 : 1.75;
  function layout() {
    const r = hero.getBoundingClientRect();
    view.w = Math.max(1, r.width);
    view.h = Math.max(1, r.height);
    view.aspect = view.w / view.h;
    const narrow = view.aspect < 0.9;
    renderer.setPixelRatio(Math.min(devicePixelRatio, dprCap));
    renderer.setSize(view.w, view.h, false);
    pollenMat.uniforms.uPx.value = renderer.getPixelRatio();
    cam.aspect = view.aspect;
    cam.fov = narrow ? 44 : 30;
    cam.position.set(0, narrow ? 1.2 : 1.05, 6.4);
    cam.lookAt(0, narrow ? 2.0 : 2.3, -6);
    cam.updateProjectionMatrix();
    cam.updateMatrixWorld();
    view.horizon = new THREE.Vector3(0, 0, -95).project(cam).y;
    const a = view.aspect;
    ortho.left = -a;
    ortho.right = a;
    ortho.updateProjectionMatrix();
    const H = view.horizon;
    const sunR = narrow ? 0.17 : 0.34;
    sun.scale.setScalar(sunR);
    sun.userData.home = new THREE.Vector2(narrow ? a * 0.5 : a * 0.5, H + (narrow ? 0.1 : 0.2));
    farHill.scale.set(narrow ? a * 2.1 : a * 1.05, narrow ? 0.34 : 0.62, 1);
    farHill.position.set(narrow ? a * 0.6 : a * 0.42, H - (narrow ? 0.24 : 0.5), 0);
    farHill.children[0].scale.set(1 + 0.012 / farHill.scale.x * 1.6, 1 + 0.012 / farHill.scale.y * 1.6, 1);
    nearHill.scale.set(narrow ? a * 2 : a * 0.95, narrow ? 0.3 : 0.55, 1);
    nearHill.position.set(narrow ? -a * 0.7 : -a * 0.55, H - (narrow ? 0.22 : 0.46), 0);
    nearHill.children[0].scale.set(1 + 0.012 / nearHill.scale.x * 1.6, 1 + 0.012 / nearHill.scale.y * 1.6, 1);
    clouds[0].position.set(narrow ? a * 0.05 : a * 0.12, H + (narrow ? 0.5 : 0.8), 0);
    clouds[1].position.set(a * 0.9, H + (narrow ? 0.72 : 1.05), 0);
    clouds[2].position.set(narrow ? -a * 0.9 : a * 0.62, H + (narrow ? 0.3 : 1.2), 0);
    clouds.forEach((c, i) => c.scale.setScalar((narrow ? 0.62 : 1) * [0.55, 0.42, 0.34][i]));
    clouds.forEach((c) => (c.userData.y = c.position.y));
    farHill.userData.x = farHill.position.x;
    nearHill.userData.x = nearHill.position.x;
  }

  // ------------------------------------------------------------ input

  const ray = new THREE.Raycaster();
  const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  const hit = new THREE.Vector3();
  const target = new THREE.Vector3(0, 0, 100);
  let push = 0;
  let pushTarget = 0;
  const parallax = new THREE.Vector2();
  const smooth = new THREE.Vector2();
  let lastBloom = null;
  let touched = false;

  function groundAt(e) {
    const r = canvas.getBoundingClientRect();
    const p = new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(p, cam);
    if (!ray.ray.intersectPlane(plane, hit)) return null;
    return { p, world: hit.clone() };
  }

  function onMove(e) {
    const g = groundAt(e);
    if (!g) return;
    parallax.copy(g.p);
    if (g.p.y > view.horizon - 0.02) {
      pushTarget = 0;
      return;
    }
    target.copy(g.world);
    pushTarget = 1;
    if (e.buttons === 1 || e.pointerType === 'touch') {
      if (!lastBloom || lastBloom.distanceTo(g.world) > 0.45) {
        bloom(g.world.x, g.world.z, now());
        lastBloom = g.world.clone();
      }
    }
    if (!touched) {
      touched = true;
      hero.classList.add('touched');
    }
  }

  function onDown(e) {
    const g = groundAt(e);
    if (!g || g.p.y > view.horizon - 0.02) return;
    target.copy(g.world);
    pushTarget = 1;
    const t = now();
    for (let i = 0; i < 5; i++) {
      const a = Math.random() * Math.PI * 2;
      const r = Math.random() * 0.45;
      bloom(g.world.x + Math.cos(a) * r, g.world.z + Math.sin(a) * r * 0.7, t + i * 0.06);
    }
    lastBloom = g.world.clone();
    touched = true;
    hero.classList.add('touched');
  }

  canvas.addEventListener('pointermove', onMove);
  canvas.addEventListener('pointerdown', onDown);
  canvas.addEventListener('pointerleave', () => (pushTarget = 0));
  canvas.addEventListener('pointercancel', () => (pushTarget = 0));

  // ------------------------------------------------------------ loop

  const t0 = performance.now();
  const now = () => (performance.now() - t0) / 1000;
  let running = false;
  let raf = 0;
  let scrollP = 0;

  // a few flowers to start with
  for (let i = 0; i < 26; i++) bloom((Math.random() * 2 - 1) * 5, -Math.random() * 9 + 1.5, 0.4 + Math.random() * 1.6);

  let lastT = 0;
  // slow phones: if the first couple of seconds average under ~30 fps, halve the grass and the
  // resolution once, quietly
  let probeFrames = 0;
  let probeTime = 0;
  let downgraded = false;
  function frame() {
    raf = requestAnimationFrame(frame);
    const t = now();
    const raw = t - lastT;
    const dt = Math.min(raw, 0.05);
    lastT = t;
    if (!downgraded && t > 0.8 && raw < 0.5) {
      probeFrames++;
      probeTime += raw;
      if (probeFrames === 45) {
        if (probeTime / probeFrames > 1 / 30) {
          downgraded = true;
          dprCap = 1;
          grassGeo.instanceCount = Math.floor(N / 2);
          layout();
        }
      }
    }
    grassMat.uniforms.uTime.value = t;
    if (!reduce) grassMat.uniforms.uGrow.value = Math.min(1, 1 - Math.pow(1 - Math.min(t / 1.6, 1), 3));
    push += (pushTarget - push) * 0.08;
    pushTarget *= 0.985;
    grassMat.uniforms.uPush.value = push;
    grassMat.uniforms.uPointer.value.lerp(target, 0.18);

    // sky
    const rise = reduce ? 1 : 1 - Math.pow(1 - Math.min(t / 2.4, 1), 3);
    const home = sun.userData.home;
    sun.position.set(home.x - smooth.x * 0.01, home.y - 0.55 * (1 - rise) - scrollP * 0.35, 0);
    rays.rotation.z = reduce ? 0 : Math.sin(t * 0.25) * 0.06;
    clouds.forEach((c, i) => {
      if (reduce) return;
      c.position.x += dt * (0.008 + i * 0.004);
      if (c.position.x > view.aspect + 0.5) c.position.x = -view.aspect - 0.5;
      c.position.y = c.userData.y + Math.sin(t * 0.3 + i) * 0.01;
    });
    smooth.lerp(parallax, 0.04);
    farHill.position.x = farHill.userData.x - smooth.x * 0.02;
    nearHill.position.x = nearHill.userData.x - smooth.x * 0.045;

    cam.position.x = smooth.x * 0.22;

    renderer.clear();
    renderer.render(back, ortho);
    renderer.clearDepth();
    renderer.render(scene, cam);
  }

  function setRunning(on) {
    if (on === running) return;
    running = on;
    if (on) frame();
    else cancelAnimationFrame(raf);
  }

  layout();
  new ResizeObserver(() => {
    layout();
    if (!running) renderer.render(back, ortho);
  }).observe(hero);
  const io = new IntersectionObserver(([e]) => setRunning(e.isIntersecting && !document.hidden), { threshold: 0 });
  io.observe(hero);
  document.addEventListener('visibilitychange', () => setRunning(!document.hidden && hero.getBoundingClientRect().bottom > 0));
  addEventListener(
    'scroll',
    () => {
      scrollP = Math.min(1, Math.max(0, scrollY / view.h));
    },
    { passive: true },
  );

  requestAnimationFrame(() => hero.classList.add('has-gl'));
  setRunning(true);
}
