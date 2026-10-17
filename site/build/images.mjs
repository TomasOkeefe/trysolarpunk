// Turns the full-size product renders (products/renders, local only) into web images in
// static/img/p/<slug>/<shot>-<colorway>-<width>.{avif,webp} plus a manifest the build reads.
// Run after a render batch: npm run images
import { existsSync, mkdirSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const RENDERS = join(ROOT, '..', 'products', 'renders');
const OUT = join(ROOT, 'static', 'img', 'p');
const MANIFEST = join(OUT, 'manifest.json');
const WIDTHS = [400, 800, 1200];

// Blender model name -> catalog slug, where they differ
const SLUG = { scroll: 'infinite-scroll', kidstable: 'kids-table', mosshead: 'moss-head', thumbstone: 'thumb-stone' };

const manifest = existsSync(MANIFEST) ? JSON.parse(readFileSync(MANIFEST, 'utf8')) : {};
let made = 0;

const hex = (r, g, b) => '#' + [r, g, b].map((v) => Math.round(v).toString(16).padStart(2, '0')).join('');

for (const model of existsSync(RENDERS) ? readdirSync(RENDERS) : []) {
  const dir = join(RENDERS, model);
  if (!statSync(dir).isDirectory()) continue;
  const slug = SLUG[model] || model;
  for (const file of readdirSync(dir).filter((f) => f.endsWith('.png'))) {
    const key = file.replace(/\.png$/, '');
    if (key.includes('-test') || key.includes('-wip')) continue;
    const src = join(dir, file);
    const outDir = join(OUT, slug);
    mkdirSync(outDir, { recursive: true });
    const newest = statSync(src).mtimeMs;
    const meta = await sharp(src).metadata();
    const widths = WIDTHS.filter((w) => w <= meta.width);
    const fresh = widths.every((w) =>
      ['avif', 'webp'].every((ext) => {
        const f = join(outDir, `${key}-${w}.${ext}`);
        return existsSync(f) && statSync(f).mtimeMs > newest;
      }),
    );
    if (!fresh) {
      for (const w of widths) {
        const img = sharp(src).resize({ width: w });
        await img.clone().avif({ quality: 52, effort: 6 }).toFile(join(outDir, `${key}-${w}.avif`));
        await img.clone().webp({ quality: 80 }).toFile(join(outDir, `${key}-${w}.webp`));
      }
      made++;
    }
    // backdrop colour from the left and right edges (the brighter 60%, so leaf shadows don't
    // count), used behind the image while it loads and to pad it where it doesn't fill the frame
    const { data, info } = await sharp(src).removeAlpha().resize(60, 75, { fit: 'fill' }).raw().toBuffer({ resolveWithObject: true });
    const px = [];
    for (let y = 0; y < info.height; y++) {
      for (const x of [0, 1, 2, info.width - 3, info.width - 2, info.width - 1]) {
        const i = (y * info.width + x) * 3;
        px.push([data[i], data[i + 1], data[i + 2]]);
      }
    }
    px.sort((a, b) => b[0] + b[1] + b[2] - (a[0] + a[1] + a[2]));
    const top = px.slice(0, Math.ceil(px.length * 0.6));
    const [r, g, b] = [0, 1, 2].map((k) => top.reduce((s, p) => s + p[k], 0) / top.length);
    manifest[slug] ??= {};
    manifest[slug][key] = { w: widths, ratio: +(meta.height / meta.width).toFixed(4), bg: hex(r, g, b) };
  }
}

writeFileSync(MANIFEST, JSON.stringify(manifest, null, 1));
console.log(`images: ${made} renders converted, manifest has ${Object.keys(manifest).length} products`);
