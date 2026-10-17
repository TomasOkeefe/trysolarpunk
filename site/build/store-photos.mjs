// Listing photos for the Fourthwall store: 3:4 JPGs cut from the renders, into ../store-photos/v2/.
// Only the products already on Fourthwall. Run after renders: npm run store-photos
import { existsSync, mkdirSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const RENDERS = join(ROOT, 'products', 'renders');
const OUT = join(ROOT, 'store-photos', 'v2');
// model folder -> slug, in the order photos should appear on the listing
const PRODUCTS = { hibernator: 'hibernator', eyelid: 'eyelid', stroll_tee: 'stroll-tee', grass_tee: 'grass-tee', stroll_tote: 'stroll-tote', stickers: 'stickers' };
const ORDER = ['hero', 'fridge', 'table', 'detail'];

let n = 0;
for (const [model, slug] of Object.entries(PRODUCTS)) {
  const dir = join(RENDERS, model);
  if (!existsSync(dir)) continue;
  const files = readdirSync(dir).filter((f) => f.endsWith('.png') && !f.includes('-test') && !/wide|video/.test(f));
  files.sort((a, b) => ORDER.indexOf(a.split('-')[0]) - ORDER.indexOf(b.split('-')[0]) || a.localeCompare(b));
  mkdirSync(join(OUT, slug), { recursive: true });
  let i = 1;
  for (const f of files) {
    const meta = await sharp(join(dir, f)).metadata();
    if (meta.width < 1000) continue; // previews
    const w = Math.round((meta.height * 3) / 4);
    await sharp(join(dir, f))
      .extract({ left: Math.round((meta.width - w) / 2), top: 0, width: w, height: meta.height })
      .jpeg({ quality: 88, mozjpeg: true })
      .toFile(join(OUT, slug, `${String(i).padStart(2, '0')}_${f.replace('.png', '.jpg')}`));
    i++;
    n++;
  }
}
console.log(`store photos: ${n} written to store-photos/v2/`);
