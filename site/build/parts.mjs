// Shared page parts: the shell, header, footer, bag, product pictures and cards.
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { CATEGORIES, PRODUCTS } from '../lib/catalog.js';
import { html, money, raw } from './html.mjs';

export const SITE = 'https://trysolarpunk.pages.dev';
export const TIKTOK = 'https://www.tiktok.com/@trysolarpunk';
const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..');
const MANIFEST = join(ROOT, 'static', 'img', 'p', 'manifest.json');
const manifest = existsSync(MANIFEST) ? JSON.parse(readFileSync(MANIFEST, 'utf8')) : {};

export const img = (slug, key) => manifest[slug]?.[key];
// Extra shots of a product (not the colourway heroes, not the wide crops): { shot: [colourway ids] }
const SHOT_ORDER = ['fridge', 'wall', 'table', 'detail', 'closeup'];
export function shots(slug) {
  const out = {};
  for (const key of Object.keys(manifest[slug] || {})) {
    const [shot, ...rest] = key.split('-');
    if (shot === 'hero' || shot.endsWith('wide')) continue;
    (out[shot] ??= []).push(rest.join('-'));
  }
  const rank = (s) => (SHOT_ORDER.includes(s) ? SHOT_ORDER.indexOf(s) : 99);
  return Object.fromEntries(Object.entries(out).sort(([a], [b]) => rank(a) - rank(b)));
}
export const hasModel = (slug) => existsSync(join(ROOT, 'static', 'models', `${slug}.glb`));
export const hasAR = (slug) => existsSync(join(ROOT, 'static', 'ar', `${slug}.usdz`));
export const heroKey = (p, cw = p.colorways[0].id) => `hero-${cw}`;
export const ready = (p) => Boolean(img(p.slug, heroKey(p)));
export const live = () => PRODUCTS.filter(ready);
export const category = (id) => CATEGORIES.find((c) => c.id === id);
export const inCategory = (id) => live().filter((p) => p.category === id);

const src = (slug, key, w, ext) => `/img/p/${slug}/${key}-${w}.${ext}`;

export function imageUrl(slug, key, w = 800, ext = 'webp') {
  const m = img(slug, key);
  if (!m) return null;
  const best = m.w.includes(w) ? w : m.w[m.w.length - 1];
  return src(slug, key, best, ext);
}

// <picture> with AVIF and WebP at every rendered width.
export function pic(slug, key, { alt = '', sizes = '(min-width: 1100px) 25vw, (min-width: 700px) 33vw, 50vw', cls = '', eager = false, attrs = '' } = {}) {
  const m = img(slug, key);
  if (!m) return '';
  const set = (ext) => m.w.map((w) => `${src(slug, key, w, ext)} ${w}w`).join(', ');
  const w0 = m.w[m.w.length - 1];
  return html`<picture class="${cls}" ${raw(attrs)}><source type="image/avif" srcset="${set('avif')}" sizes="${sizes}"><img src="${src(slug, key, m.w[Math.min(1, m.w.length - 1)], 'webp')}" srcset="${set('webp')}" sizes="${sizes}" width="${w0}" height="${Math.round(w0 * m.ratio)}" alt="${alt}" ${eager ? raw('fetchpriority="high"') : raw('loading="lazy" decoding="async"')}></picture>`;
}

export const bg = (p, cw = p.colorways[0].id) => img(p.slug, heroKey(p, cw))?.bg || '#EFE8D8';

export function swatch(c) {
  const [a, b, d] = c.swatch;
  return b
    ? `background: conic-gradient(from 225deg, ${a} 0 50%, ${b} 50% ${d ? '75%' : '100%'}${d ? `, ${d} 75% 100%` : ''})`
    : `background: ${a}`;
}

// ------------------------------------------------------------------ cards

export function card(p, { eager = false, sizes } = {}) {
  const cws = p.colorways.filter((c) => img(p.slug, heroKey(p, c.id)));
  const alt = cws[1];
  return html`<article class="card" style="--bg: ${bg(p)}" data-card="${p.slug}">
  <a class="card-link" href="/${p.slug}">
    <div class="card-media" style="view-transition-name: p-${p.slug}">
      ${pic(p.slug, heroKey(p), { alt: `${p.name} in ${p.colorways[0].name}`, eager, sizes, cls: 'card-img is-on', attrs: `data-cw="${p.colorways[0].id}"` })}
      ${alt ? pic(p.slug, heroKey(p, alt.id), { alt: '', sizes, cls: 'card-img', attrs: `data-cw="${alt.id}" aria-hidden="true"` }) : ''}
      ${p.limited ? html`<span class="tag tag-limited">${p.limited}</span>` : ''}
      ${p.was ? html`<span class="tag">Save ${money(p.was - p.price)}</span>` : p.isNew && !p.limited ? html`<span class="tag tag-new">New</span>` : ''}
    </div>
    <div class="card-info">
      <p class="card-no">No. ${p.no}</p>
      <h3 class="card-name">${p.name}</h3>
      <p class="card-price">${money(p.price)}</p>
      <p class="card-line">${p.line}</p>
    </div>
  </a>
  ${cws.length > 1 ? html`<ul class="card-swatches" aria-label="${cws.length} colours">${cws.map((c) => html`<li><span class="sw" style="${swatch(c)}" title="${c.name}"></span></li>`)}</ul>` : ''}
  <div class="card-quick js-only">${p.buy
    ? html`<a class="quick-buy" href="${p.buy}" rel="noopener" aria-label="Buy ${p.name}">Buy</a>`
    : html`<button type="button" data-quick-add="${p.slug}" aria-label="Add ${p.name} to your bag">Add</button>`}</div>
</article>`;
}

// Editorial tiles that sit between products on the home page, keyed by the position they follow.
const INTERLUDES = {
  5: html`<aside class="interlude"><p>Nothing here gets made until someone wants it.</p><small>Reserve what you like. The most wanted gets printed first.</small></aside>`,
  13: html`<a class="interlude sun" href="/shop/thumb"><p>Your thumb deserves a hobby.</p><small>See: thumb rehab</small></a>`,
  19: html`<a class="interlude leaf" href="/shop/outside"><p>The best followers have feathers.</p><small>See: fire escape</small></a>`,
  27: html`<aside class="interlude"><p>Each one takes a job off your phone.</p><small>Then it leaves you alone. That’s the whole idea.</small></aside>`,
  37: html`<a class="interlude sun" href="/shop/bedtime"><p>Your phone needs a bedtime too.</p><small>See: bedtime for phones</small></a>`,
};

export const grid = (products, opts = {}) =>
  html`<div class="grid ${opts.cls || ''}">${products.map((p, i) => [card(p, { eager: opts.eager && i < 4, sizes: opts.sizes }), opts.interludes ? INTERLUDES[i + 1] : ''])}</div>`;

// ------------------------------------------------------------------ shell

const NAV = [
  ['/shop', 'Shop all'],
  ['/shop/bedtime', 'Bedtime'],
  ['/shop/thumb', 'Thumb rehab'],
  ['/shop/analog', 'Analog'],
  ['/merch', 'Merch'],
  ['/about', 'Why'],
];

export const emblem = (size = 40) => html`<img class="emblem" src="/img/emblem.svg" alt="" width="${size}" height="${size}">`;

function header(path) {
  return html`<header class="head" data-head>
  <a class="brand" href="/" aria-label="Try Solarpunk, home">${emblem(38)}<span class="brand-word">Try Solarpunk</span></a>
  <nav class="nav" aria-label="Main">${NAV.map(([href, label]) => html`<a href="${href}" ${path === href ? raw('aria-current="page"') : ''}>${label}</a>`)}</nav>
  <div class="head-actions">
    <button class="bag-btn" type="button" data-bag-open aria-controls="bag">Bag <span class="bag-count" data-bag-count>0</span></button>
    <button class="menu-btn" type="button" data-menu aria-expanded="false" aria-controls="menu"><span class="vh">Menu</span><i aria-hidden="true"></i></button>
  </div>
</header>
<div class="menu" id="menu" data-menu-panel hidden>
  <nav aria-label="Menu">
    <a class="menu-big" href="/shop">The whole catalog</a>
    ${CATEGORIES.map((c) => html`<a href="${c.id === 'merch' ? '/merch' : `/shop/${c.id}`}">${c.name}</a>`)}
    <a href="/about">Why we make this</a>
    <a href="${TIKTOK}" rel="noopener">Moss on TikTok</a>
  </nav>
</div>`;
}

export function joinForm(product, { label = 'Get one email when it’s ready', button = 'Reserve', id = '' } = {}) {
  return html`<form class="join" action="/api/join" method="post" ${id ? raw(`id="${id}"`) : ''}>
  <div class="join-fields">
    <p class="join-error" id="join-error">That didn’t work. Check the email and try again.</p>
    <label for="email-${product}">${label}</label>
    <div class="join-row">
      <input id="email-${product}" name="email" type="email" autocomplete="email" inputmode="email" placeholder="you@example.com" required>
      <button type="submit" class="btn btn-ink">${button}</button>
    </div>
    <input type="hidden" name="product" value="${product}">
    <input type="hidden" name="source" value="">
    <div class="hp" aria-hidden="true"><label>Website <input name="website" tabindex="-1" autocomplete="off"></label></div>
    <p class="join-msg" role="status"></p>
  </div>
  <div class="join-thanks" id="joined"><p class="join-thanks-big">You’re on the list.</p><p>One email when it’s ready. That’s the whole relationship.</p></div>
</form>`;
}

function footer() {
  return html`<footer class="end" data-end>
  <div class="end-sky" aria-hidden="true"><div class="end-sun"></div><div class="end-hill"></div></div>
  <div class="end-inner">
    <p class="end-kicker">You reached the bottom of the page.</p>
    <h2 class="end-title">The end.</h2>
    <p class="end-sub">As far as we know, this is the only feed that finishes. Go do something nice. We’ll be here.</p>
    <div class="end-cols">
      <div class="end-col">
        <h3>Shop</h3>
        <a href="/shop">The whole catalog</a>
        ${CATEGORIES.map((c) => html`<a href="${c.id === 'merch' ? '/merch' : `/shop/${c.id}`}">${c.name}</a>`)}
      </div>
      <div class="end-col">
        <h3>Try Solarpunk</h3>
        <a href="/about">Why we make this</a>
        <a href="/about#how-reserving-works">How reserving works</a>
        <a href="/about#questions">Questions</a>
        <a href="${TIKTOK}" rel="noopener">Moss on TikTok</a>
      </div>
      <div class="end-col end-news">
        <h3>Hear about every drop</h3>
        ${joinForm('everything', { label: 'Your email', button: 'Sign me up' })}
      </div>
    </div>
    <p class="end-fine">Gear for recovering scrollers. Printed in New York. Made by humans and AI, openly: the videos are AI, the objects are real plastic. Product images are renders of the final designs.</p>
  </div>
</footer>`;
}

function bag() {
  return html`<div class="bag" id="bag" data-bag hidden>
  <div class="bag-scrim" data-bag-close></div>
  <section class="bag-panel" role="dialog" aria-modal="true" aria-labelledby="bag-title">
    <header class="bag-head">
      <h2 id="bag-title">Your bag</h2>
      <button class="bag-x" type="button" data-bag-close>Close</button>
    </header>
    <div class="bag-items" data-bag-items></div>
    <div class="bag-foot" data-bag-foot>
      <p class="bag-total"><span>Total at launch</span><strong data-bag-total>$0</strong></p>
      <p class="bag-note">Nothing to pay today. Reserving holds your spot in the first print run, and we email you once, when your things are ready.</p>
      <form class="bag-form" data-bag-form novalidate>
        <label for="bag-email">Your email</label>
        <input id="bag-email" name="email" type="email" autocomplete="email" inputmode="email" placeholder="you@example.com" required>
        <div class="hp" aria-hidden="true"><label>Website <input name="website" tabindex="-1" autocomplete="off"></label></div>
        <button class="btn btn-sun btn-wide" type="submit">Reserve my bag</button>
        <p class="bag-msg" role="status" data-bag-msg></p>
      </form>
    </div>
    <div class="bag-done" data-bag-done hidden>
      <div class="bag-done-sun" aria-hidden="true"></div>
      <p class="bag-done-big">Reserved.</p>
      <p>You’re on the list for <span data-bag-done-list></span>. We’ll send one email when it’s printed, with a link to buy. Your phone has been notified. It’s nervous.</p>
      <button class="btn btn-ink" type="button" data-bag-close>Back to the catalog</button>
    </div>
  </section>
</div>`;
}

// What the bag needs to know about each product, embedded once per page.
export function catalogJson() {
  const data = live().map((p) => ({
    s: p.slug,
    n: p.name,
    no: p.no,
    $: p.price,
    c: p.colorways.filter((c) => img(p.slug, heroKey(p, c.id))).map((c) => ({ id: c.id, n: c.name, i: imageUrl(p.slug, heroKey(p, c.id), 400) })),
    z: p.sizes || null,
  }));
  return raw(`<script type="application/json" id="catalog-data">${JSON.stringify(data).replace(/</g, '\\u003c')}</script>`);
}

export function page({ path, title, desc, body, image, cls = '', assets, head = '' }) {
  const full = title ? `${title} | Try Solarpunk` : 'Try Solarpunk: gear for recovering scrollers';
  const ogImage = image || '/img/og.jpg';
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<script>document.documentElement.classList.add('js')</script>
${html`<title>${full}</title>
<meta name="description" content="${desc}">
<link rel="canonical" href="${SITE}${path === '/' ? '/' : path}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Try Solarpunk">
<meta property="og:title" content="${title || 'Try Solarpunk'}">
<meta property="og:description" content="${desc}">
<meta property="og:image" content="${SITE}${ogImage}">
<meta property="og:url" content="${SITE}${path}">
<meta name="twitter:card" content="summary_large_image">`}
<meta name="theme-color" content="#F6F1E4">
<link rel="icon" href="/img/emblem.svg" type="image/svg+xml">
<link rel="apple-touch-icon" href="/img/apple-touch-icon.png">
<link rel="preload" href="/fonts/fraunces.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/fonts/dmsans.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="${assets.css}">
<script type="module" src="${assets.js}"></script>
${head}
</head>
<body class="${cls}">
<a class="skip" href="#main">Skip to content</a>
<p class="announce"><span>Drop 01 is open for reservations.</span> <span>Pay nothing until it ships.</span></p>
${header(path)}
<main id="main">
${body}
</main>
${footer()}
${bag()}
${catalogJson()}
</body>
</html>
`;
}
