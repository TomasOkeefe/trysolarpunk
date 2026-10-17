// The bag: what you plan to buy at launch, kept in this browser. Reserving it sends one
// waitlist signup per product, so the owner sees demand per product.
import { join } from './api.js';

const KEY = 'tsp-bag-v1';
const catalog = JSON.parse(document.getElementById('catalog-data')?.textContent || '[]');
const bySlug = Object.fromEntries(catalog.map((p) => [p.s, p]));
const $ = (sel, root = document) => root.querySelector(sel);
const money = (n) => `$${n}`;

let items = load();
let lastFocus = null;

function load() {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) || '[]');
    return Array.isArray(raw) ? raw.filter((i) => bySlug[i.s]) : [];
  } catch {
    return [];
  }
}

function save() {
  try {
    localStorage.setItem(KEY, JSON.stringify(items));
  } catch {
    /* private mode: the bag lives for this page only */
  }
}

const el = {
  root: $('[data-bag]'),
  items: $('[data-bag-items]'),
  total: $('[data-bag-total]'),
  foot: $('[data-bag-foot]'),
  form: $('[data-bag-form]'),
  msg: $('[data-bag-msg]'),
  done: $('[data-bag-done]'),
  doneList: $('[data-bag-done-list]'),
};

function counts() {
  const n = items.reduce((a, i) => a + i.q, 0);
  for (const c of document.querySelectorAll('[data-bag-count]')) {
    if (c.textContent !== String(n)) {
      c.textContent = n;
      c.classList.remove('bump');
      void c.offsetWidth;
      c.classList.add('bump');
    }
  }
}

function describe(i) {
  const p = bySlug[i.s];
  const cw = p.c.find((c) => c.id === i.c) || p.c[0];
  return { p, cw, label: [p.c.length > 1 ? cw.n : '', i.z ? `Size ${i.z}` : '', i.q > 1 ? `x ${i.q}` : ''].filter(Boolean).join(', ') };
}

function render() {
  counts();
  if (!el.root) return;
  el.done.hidden = true;
  el.foot.hidden = items.length === 0;
  el.items.hidden = false;
  if (!items.length) {
    el.items.innerHTML = `<div class="bag-empty"><p>Your bag is empty, like a phone-free evening.</p><a class="btn btn-sun" href="/shop" data-bag-close>Browse the catalog</a></div>`;
    return;
  }
  el.items.innerHTML = items
    .map((i, k) => {
      const { p, cw, label } = describe(i);
      return `<div class="bag-item">
        <img src="${cw.i}" alt="" width="72" height="90" loading="lazy">
        <div><h3>${p.n}</h3><p>${label || `No. ${p.no}`}</p><button class="bag-rm" type="button" data-rm="${k}">Remove</button></div>
        <span class="price">${money(p.$ * i.q)}</span>
      </div>`;
    })
    .join('');
  el.total.textContent = money(items.reduce((a, i) => a + bySlug[i.s].$ * i.q, 0));
}

export function add(slug, colorway, size) {
  const p = bySlug[slug];
  if (!p) return;
  const c = colorway || p.c[0]?.id;
  const same = items.find((i) => i.s === slug && i.c === c && (i.z || null) === (size || null));
  if (same) same.q += 1;
  else items.push({ s: slug, c, z: size || null, q: 1 });
  save();
  render();
  open();
}

function trap(event) {
  if (event.key === 'Escape') return close();
  if (event.key !== 'Tab') return;
  const f = [...el.root.querySelectorAll('a[href], button:not([disabled]), input:not([type=hidden]):not([tabindex="-1"])')].filter((n) => n.offsetParent);
  if (!f.length) return;
  const first = f[0];
  const last = f[f.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    last.focus();
    event.preventDefault();
  } else if (!event.shiftKey && document.activeElement === last) {
    first.focus();
    event.preventDefault();
  }
}

export function open() {
  if (!el.root || !el.root.hidden) return;
  lastFocus = document.activeElement;
  el.root.hidden = false;
  document.documentElement.classList.add('bag-open');
  requestAnimationFrame(() => {
    el.root.classList.add('is-open');
    $('.bag-x', el.root).focus({ preventScroll: true });
  });
  document.addEventListener('keydown', trap);
}

export function close() {
  if (!el.root || el.root.hidden) return;
  el.root.classList.remove('is-open');
  document.removeEventListener('keydown', trap);
  document.documentElement.classList.remove('bag-open');
  setTimeout(() => {
    el.root.hidden = true;
    if (!items.length) render();
  }, 450);
  lastFocus?.focus?.({ preventScroll: true });
}

async function reserve(event) {
  event.preventDefault();
  const email = el.form.email.value.trim();
  const website = el.form.website.value;
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    el.msg.textContent = 'That email doesn’t look right.';
    el.form.email.focus();
    return;
  }
  const button = $('button[type=submit]', el.form);
  button.disabled = true;
  button.textContent = 'Reserving…';
  el.msg.textContent = '';
  const slugs = [...new Set(items.map((i) => i.s))];
  const results = await Promise.all(slugs.map((product) => join({ email, product, website })));
  const failed = results.find((r) => !r.ok);
  button.disabled = false;
  button.textContent = 'Reserve my bag';
  if (failed) {
    el.msg.textContent = failed.error;
    return;
  }
  const names = slugs.map((s) => bySlug[s].n);
  el.doneList.textContent = names.length > 1 ? `${names.slice(0, -1).join(', ')} and ${names.at(-1)}` : names[0];
  items = [];
  save();
  counts();
  el.items.hidden = true;
  el.foot.hidden = true;
  el.done.hidden = false;
  el.form.reset();
  try {
    localStorage.setItem('tsp-reserved', JSON.stringify([...new Set([...(JSON.parse(localStorage.getItem('tsp-reserved') || '[]')), ...slugs])]));
  } catch {
    /* fine */
  }
}

export function initBag() {
  render();
  document.addEventListener('click', (event) => {
    const t = event.target.closest('[data-bag-open], [data-bag-close], [data-rm]');
    if (!t) return;
    if (t.matches('[data-bag-open]')) open();
    else if (t.matches('[data-rm]')) {
      items.splice(Number(t.dataset.rm), 1);
      save();
      render();
    } else {
      if (t.tagName === 'A') return close();
      event.preventDefault();
      close();
    }
  });
  el.form?.addEventListener('submit', reserve);
  window.addEventListener('storage', (e) => {
    if (e.key === KEY) {
      items = load();
      render();
    }
  });
}
