// Builds the site into dist/: static files, bundled CSS and JS, every page, share images, sitemap.
//   node build/build.mjs          production build
//   node build/build.mjs --dev    unminified, with sourcemaps
import { cpSync, existsSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as esbuild from 'esbuild';
import sharp from 'sharp';
import { pages } from './pages.mjs';
import { SITE, heroKey, img, live } from './parts.mjs';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const DIST = join(ROOT, 'dist');
const dev = process.argv.includes('--dev');
const t0 = Date.now();

rmSync(DIST, { recursive: true, force: true });
mkdirSync(DIST, { recursive: true });
cpSync(join(ROOT, 'static'), DIST, { recursive: true });

const result = await esbuild.build({
  entryPoints: { main: join(ROOT, 'src/js/main.js'), style: join(ROOT, 'src/css/main.css') },
  bundle: true,
  splitting: true,
  format: 'esm',
  minify: !dev,
  sourcemap: dev,
  target: ['es2020', 'safari15', 'chrome100'],
  outdir: join(DIST, 'assets'),
  entryNames: '[name]-[hash]',
  chunkNames: 'c-[hash]',
  external: ['/fonts/*', '/img/*', '/video/*', '/models/*', '/ar/*'],
  metafile: true,
  legalComments: 'none',
  logLevel: 'warning',
});

const outputs = Object.entries(result.metafile.outputs);
const entry = (name, ext) => '/' + outputs.find(([f, o]) => o.entryPoint?.endsWith(name) && f.endsWith(ext))[0].replace(/^dist\//, '').replace(/.*dist\//, '');
const assets = { js: entry('src/js/main.js', '.js'), css: entry('src/css/main.css', '.css') };

const all = pages(assets);
for (const p of all) {
  const file = join(DIST, p.file);
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(file, p.html);
}

// share cards: the hero render on its own backdrop colour, 1200 x 630
mkdirSync(join(DIST, 'og'), { recursive: true });
for (const p of live()) {
  const m = img(p.slug, heroKey(p));
  const src = join(ROOT, 'static', 'img', 'p', p.slug, `${heroKey(p)}-${m.w[m.w.length - 1]}.webp`);
  const shot = await sharp(src).resize({ height: 630 }).toBuffer();
  const meta = await sharp(shot).metadata();
  await sharp({ create: { width: 1200, height: 630, channels: 3, background: m.bg } })
    .composite([{ input: shot, left: Math.round((1200 - meta.width) / 2), top: 0 }])
    .jpeg({ quality: 82, mozjpeg: true })
    .toFile(join(DIST, 'og', `${p.slug}.jpg`));
}

// the home share card: logo and tagline on the left, four products on the right
{
  const BRAND = join(ROOT, '..', 'brand');
  const card = async (slug, key, w, h) => {
    const m = img(slug, key);
    const src = join(ROOT, 'static', 'img', 'p', slug, `${key}-${m.w[m.w.length - 1]}.webp`);
    const photo = await sharp(src).resize(w - 8, h - 8, { fit: 'cover', position: 'attention' }).png().toBuffer();
    const round = Buffer.from(`<svg width="${w - 8}" height="${h - 8}"><rect width="${w - 8}" height="${h - 8}" rx="18" fill="#fff"/></svg>`);
    const inner = await sharp(photo).composite([{ input: round, blend: 'dest-in' }]).png().toBuffer();
    const frame = Buffer.from(`<svg width="${w}" height="${h}"><rect x="2" y="2" width="${w - 4}" height="${h - 4}" rx="22" fill="#2A2420"/></svg>`);
    return sharp(frame).composite([{ input: inner, left: 4, top: 4 }]).png().toBuffer();
  };
  const picks = [['hibernator', 'hero-moss'], ['eyelid', 'hero-clay'], ['sunup', 'hero-morning'], ['sundial', 'hero-sun']].filter(([s, k]) => img(s, k));
  const cards = await Promise.all(picks.map(([s, k]) => card(s, k, 255, 285)));
  const emblem = await sharp(join(BRAND, 'emblem.png')).resize(250, 250).toBuffer();
  const word = await sharp(join(BRAND, 'wordmark.png')).resize(500).toBuffer();
  const tagline = await sharp(join(BRAND, 'banner.png')).extract({ left: 805, top: 535, width: 860, height: 60 }).resize(470).toBuffer();
  await sharp({ create: { width: 1200, height: 630, channels: 3, background: '#F6F1E4' } })
    .composite([
      { input: emblem, left: 64, top: 70 },
      { input: word, left: 64, top: 360 },
      { input: tagline, left: 66, top: 470 },
      ...cards.map((input, i) => ({ input, left: 640 + (i % 2) * 267, top: 24 + Math.floor(i / 2) * 297 })),
    ])
    .jpeg({ quality: 84, mozjpeg: true })
    .toFile(join(DIST, 'img', 'og.jpg'));
}

writeFileSync(join(DIST, 'sitemap.xml'), `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${all.filter((p) => p.path !== '/404').map((p) => `  <url><loc>${SITE}${p.path}</loc></url>`).join('\n')}
</urlset>
`);
writeFileSync(join(DIST, 'robots.txt'), `User-agent: *\nAllow: /\nSitemap: ${SITE}/sitemap.xml\n`);
writeFileSync(join(DIST, '_headers'), `/assets/*
  Cache-Control: public, max-age=31536000, immutable
/fonts/*
  Cache-Control: public, max-age=31536000, immutable
/img/p/*
  Cache-Control: public, max-age=604800
/video/*
  Cache-Control: public, max-age=604800
/ar/*
  Content-Type: model/vnd.usdz+zip
  Cache-Control: public, max-age=604800
/models/*
  Cache-Control: public, max-age=604800
/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
`);

if (!existsSync(join(DIST, 'img', 'emblem.svg'))) throw new Error('static/img/emblem.svg missing');
console.log(`built ${all.length} pages, ${live().length} products, in ${Date.now() - t0} ms -> ${assets.js} ${assets.css}`);
