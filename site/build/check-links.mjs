// Every internal link and asset on every built page points at a file that exists in dist/.
// Run after a build: npm run check
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const DIST = join(dirname(fileURLToPath(import.meta.url)), '..', 'dist');
if (!existsSync(DIST)) {
  console.error('FAIL no dist/, run npm run build');
  process.exit(1);
}

const pages = [];
(function walk(dir) {
  for (const f of readdirSync(dir)) {
    const p = join(dir, f);
    if (statSync(p).isDirectory()) walk(p);
    else if (f.endsWith('.html')) pages.push(p);
  }
})(DIST);

// How Cloudflare Pages resolves a path: /x is x.html or x/index.html, / is index.html
function resolves(path) {
  const clean = decodeURI(path.split(/[?#]/)[0]);
  if (clean === '/' || clean === '') return existsSync(join(DIST, 'index.html'));
  if (clean.startsWith('/api/')) return true;
  const file = join(DIST, clean);
  return existsSync(file) && statSync(file).isFile() ? true : existsSync(`${file}.html`) || existsSync(join(file, 'index.html'));
}

let bad = 0;
let checked = 0;
for (const page of pages) {
  const htmlText = readFileSync(page, 'utf8');
  const refs = new Set();
  for (const m of htmlText.matchAll(/(?:href|src|poster|data-src)="(\/[^"]*)"/g)) refs.add(m[1]);
  for (const m of htmlText.matchAll(/srcset="([^"]+)"/g)) for (const part of m[1].split(',')) refs.add(part.trim().split(/\s+/)[0]);
  for (const ref of refs) {
    if (!ref.startsWith('/') || ref.startsWith('//')) continue;
    checked++;
    if (!resolves(ref)) {
      bad++;
      console.log(`FAIL ${page.replace(DIST, '')} -> ${ref}`);
    }
  }
}
console.log(`${bad ? 'FAIL' : 'ok  '} ${checked} internal links and assets on ${pages.length} pages, ${bad} broken`);
process.exit(bad ? 1 : 0);
