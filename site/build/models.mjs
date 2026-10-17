// Compresses the viewer models exported from Blender (products/glb, local only) into
// static/models/<slug>.glb with their colour tables. Run after export.py: npm run models
import { execFileSync } from 'node:child_process';
import { copyFileSync, existsSync, mkdirSync, readdirSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const SRC = join(ROOT, '..', 'products', 'glb');
const OUT = join(ROOT, 'static', 'models');
const SLUG = { scroll: 'infinite-scroll', kidstable: 'kids-table', mosshead: 'moss-head', thumbstone: 'thumb-stone' };

mkdirSync(OUT, { recursive: true });
let n = 0;
for (const f of existsSync(SRC) ? readdirSync(SRC).filter((f) => f.endsWith('.glb')) : []) {
  const model = f.replace(/\.glb$/, '');
  const slug = SLUG[model] || model.replace(/_/g, '-');
  const src = join(SRC, f);
  const dst = join(OUT, `${slug}.glb`);
  if (existsSync(dst) && statSync(dst).mtimeMs > statSync(src).mtimeMs) continue;
  execFileSync('npx', ['-y', '@gltf-transform/cli@4.5.1', 'optimize', src, dst, '--compress', 'meshopt', '--texture-compress', 'false', '--simplify', 'false'], { stdio: 'ignore' });
  copyFileSync(join(SRC, `${model}.json`), join(OUT, `${slug}.json`));
  console.log(`models: ${slug} ${Math.round(statSync(dst).size / 1024)} kB`);
  n++;
}
console.log(`models: ${n} compressed`);
