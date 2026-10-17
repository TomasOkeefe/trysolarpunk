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
  external: ['/fonts/*', '/img/*', '/video/*', '/models/*'],
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
/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
`);

if (!existsSync(join(DIST, 'img', 'emblem.svg'))) throw new Error('static/img/emblem.svg missing');
console.log(`built ${all.length} pages, ${live().length} products, in ${Date.now() - t0} ms -> ${assets.js} ${assets.css}`);
