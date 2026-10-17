// Every page on the site, as functions that return { path, file, html }.
import { CATEGORIES, PRODUCTS, bySlug } from '../lib/catalog.js';
import { html, money, raw } from './html.mjs';
import {
  TIKTOK, bg, card, category, emblem, grid, hasModel, heroKey, img, imageUrl, inCategory, joinForm, live, page, pic, shots, swatch,
} from './parts.mjs';

const WORDS = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen', 'twenty'];
const words = (n) => WORDS[n] || String(n);
const cap = (s) => s[0].toUpperCase() + s.slice(1);
const catHref = (id) => (id === 'merch' ? '/merch' : `/shop/${id}`);

const objects = () => live().filter((p) => !['merch', 'kits'].includes(p.category));

function chips(active) {
  const cats = CATEGORIES.filter((c) => inCategory(c.id).length);
  return html`<nav class="chips" aria-label="Categories">
  <a class="chip" href="/shop" ${active ? '' : raw('aria-current="page"')}>Everything <span>${live().length}</span></a>
  ${cats.map((c) => html`<a class="chip" href="${catHref(c.id)}" ${active === c.id ? raw('aria-current="page"') : ''}>${c.name} <span>${inCategory(c.id).length}</span></a>`)}
</nav>`;
}

// ------------------------------------------------------------------ home

const AT_HOME = [
  ['hibernator', 'fridge-moss', 'On the fridge, two rooms from your bed.'],
  ['sunup', 'table-morning', 'On the nightstand, where the phone used to be.'],
  ['eyelid', 'table-moss', 'Face up on the table, eyes closed.'],
  ['greenhouse', 'table-clay', 'On the desk. Phone in the basement.'],
  ['moss-head', 'table-classic', 'On the shelf, growing a haircut.'],
  ['infinite-scroll', 'table-ink', 'Next to the coffee, for the 11 pm itch.'],
  ['dice', 'table-sun', 'Roll before you open an app.'],
];

function atHome() {
  const shots = AT_HOME.filter(([s, k]) => img(s, k));
  if (shots.length < 3) return '';
  return html`<section class="athome" aria-labelledby="athome-title">
  <div class="section-head"><h2 id="athome-title">Where they live</h2><p>Out of the box and into the house, where they quietly take a job off your phone.</p></div>
  <div class="athome-row">${shots.map(([s, k, caption]) => html`<a class="athome-card" href="/${s}">${pic(s, k, { alt: `${bySlug(s).name}. ${caption}`, sizes: '(min-width: 900px) 28vw, 78vw' })}<span class="athome-cap"><strong>${bySlug(s).name}</strong> ${caption}</span></a>`)}</div>
</section>`;
}

function home(assets) {
  const lead = bySlug('hibernator');
  const all = live();
  const objs = objects();
  const habits = CATEGORIES.filter((c) => inCategory(c.id).length);
  const body = html`
<section class="hero" data-hero>
  <div class="hero-scene" aria-hidden="true">
    <div class="hero-fallback">
      <div class="hf-sun"></div>
      <svg class="hf-hills" viewBox="0 0 1600 600" preserveAspectRatio="none"><path d="M0 330 C 300 230 620 250 900 320 S 1400 360 1600 290 V600 H0Z" fill="#9BC53D"/><path d="M0 430 C 400 360 800 380 1100 430 S 1450 470 1600 420 V600 H0Z" fill="#2F5D3A"/></svg>
    </div>
    <canvas class="hero-canvas" data-meadow></canvas>
  </div>
  <div class="hero-copy">
    <p class="hero-vol">The Try Solarpunk catalog. Volume one, fall and winter 2026.</p>
    <h1 class="hero-title" data-hero-title><span class="ln">Gear for</span> <span class="ln">recovering</span> <span class="ln">scrollers.</span></h1>
  </div>
  <div class="hero-bottom">
  <p class="hero-touch" data-touch-hint aria-hidden="true"><span>Go on. Touch the grass.</span></p>
  <div class="hero-card">
    <p class="hero-sub">${cap(words(objs.length))} objects and some merch for putting the phone down, printed to order in New York. Reserve now, pay nothing until it ships.</p>
    <div class="hero-cta"><a class="btn btn-sun" href="#catalog">Browse the catalog</a><a class="btn btn-ghost hero-why" href="/about">Why we make this</a></div>
  </div>
  </div>
</section>

<div class="ticker" aria-hidden="true"><div class="ticker-track">${Array.from({ length: 6 }, () => html`<span>No feed.</span><span>No ads.</span><span>No end.</span><span class="ticker-sun"></span>`)}</div></div>

${lead && ready(lead) ? html`
<section class="feature" id="featured" style="--bg: ${bg(lead)}">
  <a class="feature-media" href="/${lead.slug}" tabindex="-1">${img(lead.slug, 'fridge-moss')
    ? pic(lead.slug, 'fridge-moss', { alt: 'The Hibernator on a fridge door with a phone tucked in, next to a shopping list that ends with touch grass', sizes: '(min-width: 900px) 55vw, 100vw' })
    : pic(lead.slug, heroKey(lead), { alt: 'The Hibernator in moss green, a phone tucked in face to the wall', sizes: '(min-width: 900px) 55vw, 100vw' })}</a>
  <div class="feature-copy">
    <p class="no">No. ${lead.no}</p>
    <h2 class="feature-name">${lead.name}</h2>
    <p class="feature-line">${lead.line}</p>
    <ol class="steps-mini">${lead.how.map((s) => html`<li>${s}</li>`)}</ol>
    <div class="feature-buy"><span class="price-big">${money(lead.price)}</span><a class="btn btn-sun" href="/${lead.slug}">View the Hibernator</a></div>
  </div>
</section>` : ''}

<section class="habits" aria-labelledby="habits-title">
  <div class="section-head"><h2 id="habits-title">Shop by habit</h2><p>Pick the habit. We made a thing for it.</p></div>
  <div class="habit-grid">
    ${habits.map((c, i) => {
      const ps = inCategory(c.id).slice(0, 3);
      return html`<a class="habit habit-${i % 6}" href="${catHref(c.id)}" style="--tint: var(--${c.tint})">
      <div class="habit-media">${ps.map((p, k) => html`<span class="habit-thumb t${k}" style="--bg: ${bg(p)}">${pic(p.slug, heroKey(p), { sizes: '(min-width: 900px) 12vw, 30vw' })}</span>`)}</div>
      <div class="habit-text"><h3>${c.name}</h3><p>${c.blurb}</p><span class="habit-count">${inCategory(c.id).length} ${inCategory(c.id).length === 1 ? 'thing' : 'things'}</span></div>
    </a>`;
    })}
  </div>
</section>

<section class="catalog" id="catalog" aria-labelledby="catalog-title">
  <div class="section-head"><h2 id="catalog-title">The whole catalog</h2><p>${cap(words(all.length))} things. Reserve what you like and pay nothing until it’s printed.</p></div>
  ${chips(null)}
  ${grid(all, { eager: false, interludes: true })}
</section>

${atHome()}

<section class="moss" aria-labelledby="moss-title">
  <div class="moss-copy">
    <h2 id="moss-title">Starring Moss</h2>
    <p>Moss is the little guy in our videos. He used to scroll until 3 am. Now he naps in fields, plays a terrible trumpet and keeps his phone in a sleeping bag on the fridge.</p>
    <p>He is made by AI, and his habits are aspirational.</p>
    <a class="btn btn-ink" href="${TIKTOK}" rel="noopener">Watch Moss on TikTok</a>
  </div>
  <div class="moss-reel" data-reel>
    ${[['trumpet', 'Moss playing a very bad trumpet in a field'], ['goose', 'Moss making friends with a goose'], ['plant', 'Moss planting a seedling']].map(([v, label], i) => html`<figure class="phone-frame f${i}"><video muted loop playsinline preload="none" poster="/video/${v}.jpg" data-src="/video/${v}.mp4" aria-label="${label}"></video></figure>`)}
  </div>
</section>

<section class="manifesto" aria-label="What we believe">
  <p class="manifesto-big" data-split>We’re not anti-phone. We’re anti-feed.</p>
  <div class="manifesto-cols">
    <p>Phones are great. Maps, music, calling your mom. The feed is the part built to never end, and it is very good at its job.</p>
    <p>So we make small, nice objects that put a bit of distance between you and it. A place for the phone to sleep. Something for the thumb to do. A clock that is only a clock.</p>
    <p>No lectures, no detox retreat. Just gear for recovering scrollers, and a cartoon guy in a beanie showing how it’s done.</p>
  </div>
</section>

<section class="how" id="how-reserving-works" aria-labelledby="how-title">
  <h2 id="how-title">How reserving works</h2>
  <ol class="how-steps">
    <li><h3>Reserve</h3><p>Put things in your bag and leave your email. No card, no payment, no account.</p></li>
    <li><h3>We print</h3><p>We print in batches in New York, starting with whatever gets reserved most.</p></li>
    <li><h3>One email</h3><p>When yours is ready we send one email with a link to buy it. Changed your mind? Ignore it. No hard feelings.</p></li>
  </ol>
</section>`;
  return {
    path: '/',
    file: 'index.html',
    html: page({ path: '/', desc: 'Gear for recovering scrollers: little objects that help your phone take a nap, printed to order in New York. Reserve now, pay nothing until it ships.', body, cls: 'p-home', assets }),
  };
}

// ------------------------------------------------------------------ shop + categories

function shop(assets) {
  const body = html`
<section class="listing">
  <div class="listing-head">
    <h1>The whole catalog</h1>
    <p>${cap(words(live().length))} things for putting the phone down. Everything is printed to order, so nothing ships until it’s reserved.</p>
  </div>
  ${chips(null)}
  ${grid(live(), { eager: true })}
</section>`;
  return { path: '/shop', file: 'shop.html', html: page({ path: '/shop', title: 'The whole catalog', desc: 'Everything we make for recovering scrollers: phone beds, thumb things, analog clocks, merch.', body, cls: 'p-shop', assets }) };
}

function categoryPage(c, assets) {
  const ps = inCategory(c.id);
  const path = catHref(c.id);
  const body = html`
<section class="listing" style="--tint: var(--${c.tint})">
  <div class="listing-head">
    <p class="crumbs"><a href="/shop">Shop</a> <span aria-hidden="true">/</span> ${c.name}</p>
    <h1>${c.name}</h1>
    <p>${c.blurb}</p>
  </div>
  ${chips(c.id)}
  ${ps.length ? grid(ps, { eager: true }) : html`<p class="listing-empty">The first run is being printed as we speak. Leave your email and we’ll tell you the day it drops.</p>`}
  ${c.id === 'merch' ? html`<div class="listing-join">${joinForm('merch', { label: 'Tell me when the merch drops', button: 'Tell me' })}</div>` : ''}
</section>`;
  return {
    path,
    file: c.id === 'merch' ? 'merch.html' : `shop/${c.id}.html`,
    html: page({ path, title: c.name, desc: `${c.name}: ${c.blurb}`, body, cls: 'p-category', assets }),
  };
}

// ------------------------------------------------------------------ product

const SHOT_ALT = { fridge: 'on a fridge door, next to the shopping list', table: 'on a wooden table at home', detail: 'up close' };

function product(p, assets) {
  const cws = p.colorways.filter((c) => img(p.slug, heroKey(p, c.id)));
  const extra = shots(p.slug);
  const c = category(p.category);
  const related = live().filter((q) => q.category === p.category && q.slug !== p.slug).slice(0, 4);
  const more = related.length < 4 ? live().filter((q) => q.category !== p.category && q.slug !== p.slug).slice(0, 4 - related.length) : [];
  const body = html`
<section class="pdp" data-product="${p.slug}">
  <div class="pdp-media">
    <div class="pdp-stage" style="--bg: ${bg(p)}; view-transition-name: p-${p.slug}" data-stage>
      ${cws.map((cw, i) => html`<div class="pdp-shot ${i === 0 ? 'is-on' : ''}" data-shot="hero" data-cw="${cw.id}" style="--bg: ${bg(p, cw.id)}">${pic(p.slug, heroKey(p, cw.id), { alt: `${p.name} in ${cw.name}`, sizes: '(min-width: 1000px) 55vw, 100vw', eager: i === 0 })}</div>`)}
      ${Object.entries(extra).map(([shot, ids]) => ids.map((id) => html`<div class="pdp-shot" data-shot="${shot}" data-cw="${id}" style="--bg: ${img(p.slug, `${shot}-${id}`).bg}">${pic(p.slug, `${shot}-${id}`, { alt: `${p.name} ${SHOT_ALT[shot] || ''}`.trim(), sizes: '(min-width: 1000px) 55vw, 100vw' })}</div>`))}
      ${p.limited ? html`<span class="tag tag-limited">${p.limited}</span>` : ''}
      ${Object.keys(extra).length ? html`<div class="pdp-thumbs js-only" role="group" aria-label="Photos">
        <button type="button" class="thumb is-on" data-thumb="hero" aria-label="Product photo" aria-pressed="true"><img src="${imageUrl(p.slug, heroKey(p), 400)}" alt="" width="56" height="70"></button>
        ${Object.entries(extra).map(([shot, ids]) => html`<button type="button" class="thumb" data-thumb="${shot}" aria-label="${SHOT_ALT[shot] || shot}" aria-pressed="false"><img src="${imageUrl(p.slug, `${shot}-${ids[0]}`, 400)}" alt="" width="56" height="70"></button>`)}
      </div>` : ''}
      ${hasModel(p.slug) ? html`<button class="spin-btn js-only" type="button" data-spin aria-pressed="false"><span class="spin-icon" aria-hidden="true"></span><span data-spin-label>Spin it in 3D</span></button>` : ''}
    </div>
  </div>
  <div class="pdp-info">
    <p class="crumbs"><a href="/shop">Shop</a> <span aria-hidden="true">/</span> <a href="${catHref(c.id)}">${c.name}</a></p>
    <p class="no">No. ${p.no}</p>
    <h1 class="pdp-name">${p.name}</h1>
    <p class="pdp-line">${p.line}</p>
    <p class="pdp-price"><span class="price-big">${money(p.price)}</span>${p.was ? html` <s>${money(p.was)}</s>` : ''} <span class="pdp-when">when it ships</span></p>
    <form class="pdp-buy" data-buy>
      ${cws.length > 1 ? html`<fieldset class="pick">
        <legend>Colour <span data-cw-name>${cws[0].name}</span></legend>
        <div class="pick-row">${cws.map((cw, i) => html`<label class="sw-pick" title="${cw.name}"><input type="radio" name="cw" value="${cw.id}" data-name="${cw.name}" ${i === 0 ? raw('checked') : ''}><span class="sw" style="${swatch(cw)}"></span><span class="vh">${cw.name}</span></label>`)}</div>
      </fieldset>` : html`<input type="hidden" name="cw" value="${cws[0].id}" data-name="${cws[0].name}">`}
      ${p.sizes ? html`<fieldset class="pick">
        <legend>Size</legend>
        <div class="pick-row">${p.sizes.map((s, i) => html`<label class="size-pick"><input type="radio" name="size" value="${s}" ${i === 1 ? raw('checked') : ''}><span>${s}</span></label>`)}</div>
      </fieldset>` : ''}
      <button class="btn btn-sun btn-wide js-only" type="submit">Add to bag</button>
    </form>
    <p class="pdp-note">Pay nothing now. We print in batches in New York and send one email when yours is ready.</p>
    <p class="pdp-reserved js-only" data-reserved-note hidden>You’re already on the list for this one. Adding it again is fine, we only email once.</p>
    <div class="nojs-only">${joinForm(p.slug)}</div>
  </div>
</section>

<div class="buybar js-only" data-buybar hidden>
  <div class="buybar-text"><span>${p.name}</span><strong>${money(p.price)}</strong></div>
  <button class="btn btn-sun" type="button" data-buybar-add>Add to bag</button>
</div>

<section class="pdp-story">
  <div class="pdp-body">${p.body.map((t) => html`<p>${t}</p>`)}</div>
  ${p.how ? html`<div class="pdp-how"><h2>How it works</h2><ol>${p.how.map((s) => html`<li>${s}</li>`)}</ol></div>` : ''}
  <div class="pdp-specs"><h2>The details</h2><dl>${p.specs.map(([k, v]) => html`<div><dt>${k}</dt><dd>${v}</dd></div>`)}</dl></div>
  ${p.includes ? html`<div class="pdp-includes"><h2>In the kit</h2><ul>${p.includes.map((s) => bySlug(s)).filter(Boolean).map((q) => html`<li><a href="/${q.slug}">${q.name}</a> <span>${money(q.price)}</span></li>`)}</ul></div>` : ''}
</section>

<section class="related" aria-labelledby="related-title">
  <div class="section-head"><h2 id="related-title">${related.length ? `More ${c.name.toLowerCase()}` : 'You might also like'}</h2></div>
  ${grid([...related, ...more])}
</section>`;
  return {
    path: `/${p.slug}`,
    file: `${p.slug}.html`,
    html: page({ path: `/${p.slug}`, title: p.name, desc: `${p.line} ${money(p.price)}, printed to order in New York. Reserve now, pay nothing until it ships.`, body, cls: 'p-product', image: `/og/${p.slug}.jpg`, assets }),
  };
}

// ------------------------------------------------------------------ about

const FAQ = [
  ['Do I pay anything now?', 'No. Reserving is free. You give us an email, we send one message when your things are printed, and you decide then.'],
  ['When will things ship?', 'We print in batches in New York, starting with whatever gets reserved most. The first batch goes out when the shop opens, and you will hear about it by email first.'],
  ['Are the pictures real?', 'They are renders of the final designs, made from the same 3D files we print from. Real photos the moment the first batch comes off the printer.'],
  ['What are they made of?', 'PLA, a plastic made from plants, in matte colours. Some pieces have magnets, an NFC tag or a ball bearing inside. The clothes are printed on demand.'],
  ['How do the NFC tags work?', 'Tap your phone on the tag and it can run an automation, like switching on a Focus mode. On iPhone that is a Shortcuts automation (iPhone XS or newer). On Android, an NFC automation app does the same.'],
  ['Why is your channel AI-made?', 'Our videos are made with AI and labelled that way on TikTok. The objects are designed on a computer and printed by a person. We think tools are fine. Feeds that never end are the problem.'],
  ['Will you email me a lot?', 'No. One email when your things are ready. If you sign up for every drop, one email per drop.'],
];

// A loose row of photos: where the objects end up living.
function aboutStrip() {
  const picks = [['hibernator', 'fridge-moss'], ['sunup', 'table-morning'], ['eyelid', 'table-moss'], ['greenhouse', 'table-clay'], ['moss-head', 'hero-classic']]
    .filter(([s, k]) => img(s, k));
  if (!picks.length) return '';
  return html`<section class="strip" aria-label="Our objects at home">${picks.map(([s, k], i) => html`<a class="strip-card s${i}" href="/${s}">${pic(s, k, { alt: bySlug(s).name, sizes: '(min-width: 900px) 22vw, 60vw' })}</a>`)}</section>`;
}

function about(assets) {
  const body = html`
<section class="about-hero">
  ${emblem(120)}
  <h1>We’re not <span class="nowrap">anti-phone.</span> We’re <span class="nowrap">anti-feed.</span></h1>
  <p class="about-lede">Try Solarpunk makes small, nice objects for people who want to spend less time scrolling. Phone beds, thumb things, clocks that are only clocks. Printed to order in New York.</p>
</section>
<section class="about-body">
  <div class="about-col">
    <h2>The idea</h2>
    <p>Most of us don’t want to throw our phones in a lake. We want them to stop following us into bed, into dinner, into the five minutes we have between things.</p>
    <p>Willpower is a bad tool for that. Objects are better. If the phone has a place to sleep on the fridge, it ends up on the fridge. If your thumb has a wheel to spin, it spins the wheel. Solarpunk is the hopeful idea that technology can be gentle and local and a bit beautiful. We are trying it, one small object at a time.</p>
  </div>
  <div class="about-col">
    <h2>How it’s made</h2>
    <p>Every object is designed as a 3D file and printed to order in New York in matte plant-based plastic, so nothing gets made that nobody wants. That is also why you reserve first: the most reserved things get printed first.</p>
    <p>Our videos star Moss, a little guy in a green beanie. He is made with AI, and labelled that way. The images on this site are renders of the same files we print. The plastic is very real.</p>
  </div>
</section>
${aboutStrip()}
<section class="how" id="how-reserving-works" aria-labelledby="how-title">
  <h2 id="how-title">How reserving works</h2>
  <ol class="how-steps">
    <li><h3>Reserve</h3><p>Put things in your bag and leave your email. No card, no payment, no account.</p></li>
    <li><h3>We print</h3><p>We print in batches in New York, starting with whatever gets reserved most.</p></li>
    <li><h3>One email</h3><p>When yours is ready we send one email with a link to buy it. Changed your mind? Ignore it. No hard feelings.</p></li>
  </ol>
</section>
<section class="faq" id="questions" aria-labelledby="faq-title">
  <h2 id="faq-title">Questions</h2>
  ${FAQ.map(([q, a]) => html`<details class="faq-item"><summary>${q}</summary><p>${a}</p></details>`)}
</section>`;
  return { path: '/about', file: 'about.html', html: page({ path: '/about', title: 'Why we make this', desc: 'We’re not anti-phone, we’re anti-feed. Small objects for people who want to scroll less, printed to order in New York.', body, cls: 'p-about', assets }) };
}

function notFound(assets) {
  const body = html`
<section class="lost">
  <p class="no">Error 404</p>
  <h1>This page went outside.</h1>
  <p>Good for it, honestly. The rest of the site is still here.</p>
  <a class="btn btn-sun" href="/">Back to the catalog</a>
</section>`;
  return { path: '/404', file: '404.html', html: page({ path: '/404', title: 'Page not found', desc: 'This page went outside.', body, cls: 'p-404', assets }) };
}

export function pages(assets) {
  return [
    home(assets),
    shop(assets),
    ...CATEGORIES.filter((c) => inCategory(c.id).length || c.id === 'merch').map((c) => categoryPage(c, assets)),
    ...live().map((p) => product(p, assets)),
    about(assets),
    notFound(assets),
  ];
}

function ready(p) {
  return Boolean(img(p.slug, heroKey(p)));
}
