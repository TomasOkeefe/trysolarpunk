// Product page: the colour picker swaps the photo, Add to bag puts the pick in the bag.
import { add } from './bag.js';

export function initProduct() {
  const root = document.querySelector('[data-product]');
  if (!root) return;
  const slug = root.dataset.product;
  const form = root.querySelector('[data-buy]');
  const stage = root.querySelector('[data-stage]');
  const name = root.querySelector('[data-cw-name]');
  const current = () => form.querySelector('input[name="cw"]:checked')?.value || form.querySelector('input[name="cw"]')?.value;

  let view = 'hero';
  const thumbs = root.querySelectorAll('[data-thumb]');

  // Show colourway `id` in the current view (the product photo, or an extra shot like the fridge).
  function show(id, push) {
    const pick = (shot) => stage.querySelector(`.pdp-shot[data-shot="${shot}"][data-cw="${CSS.escape(id)}"]`) || stage.querySelector(`.pdp-shot[data-shot="${shot}"]`);
    const shot = pick(view) || pick('hero');
    if (!shot) return;
    for (const s of stage.querySelectorAll('.pdp-shot')) s.classList.toggle('is-on', s === shot);
    stage.style.setProperty('--bg', getComputedStyle(shot).getPropertyValue('--bg'));
    for (const t of thumbs) {
      const own = stage.querySelector(`.pdp-shot[data-shot="${t.dataset.thumb}"][data-cw="${CSS.escape(id)}"] img`);
      if (own) t.querySelector('img').src = own.currentSrc || own.src;
    }
    const input = form.querySelector(`input[name="cw"][value="${CSS.escape(id)}"]`);
    if (input) {
      input.checked = true;
      if (name) name.textContent = input.dataset.name;
    }
    if (push) {
      const url = new URL(location.href);
      url.searchParams.set('c', id);
      history.replaceState(null, '', url);
    }
  }

  const wanted = new URLSearchParams(location.search).get('c');
  if (wanted) show(wanted, false);

  for (const t of thumbs) {
    t.addEventListener('click', () => {
      view = t.dataset.thumb;
      for (const o of thumbs) {
        o.classList.toggle('is-on', o === t);
        o.setAttribute('aria-pressed', String(o === t));
      }
      show(current(), false);
    });
  }

  // Spin it: load the 3D viewer only when asked
  let viewer = null;
  let loading = false;
  const spin = root.querySelector('[data-spin]');
  spin?.addEventListener('click', async () => {
    if (loading) return;
    if (viewer) {
      viewer.stop();
      viewer = null;
      stage.classList.remove('is-3d');
      spin.setAttribute('aria-pressed', 'false');
      spin.querySelector('[data-spin-label]').textContent = 'Spin it in 3D';
      return;
    }
    loading = true;
    spin.querySelector('[data-spin-label]').textContent = 'Loading…';
    try {
      const { startViewer } = await import('./viewer.js');
      viewer = await startViewer(stage, slug, current());
      stage.classList.add('is-3d');
      spin.setAttribute('aria-pressed', 'true');
      spin.querySelector('[data-spin-label]').textContent = 'Back to the photo';
    } catch (err) {
      console.warn('viewer:', err);
      spin.querySelector('[data-spin-label]').textContent = 'Spin it in 3D';
    }
    loading = false;
  });

  form.addEventListener('change', (event) => {
    if (event.target.name === 'cw') {
      show(event.target.value, true);
      viewer?.recolor(event.target.value);
    }
  });
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const f = new FormData(form);
    add(slug, f.get('cw'), f.get('size'));
  });

  // on phones, a bar with the price and the button follows once the real button scrolls away
  const bar = document.querySelector('[data-buybar]');
  const main = form.querySelector('button[type=submit]');
  if (bar && main && 'IntersectionObserver' in window) {
    new IntersectionObserver(([e]) => {
      const past = !e.isIntersecting && e.boundingClientRect.top < 0;
      bar.hidden = !past;
    }).observe(main);
    bar.querySelector('[data-buybar-add]').addEventListener('click', () => form.requestSubmit());
  }
}

// Quick add from a catalog card: the first colour, a medium if it comes in sizes.
export function initQuickAdd() {
  document.addEventListener('click', (e) => {
    const b = e.target.closest('[data-quick-add]');
    if (!b) return;
    const data = JSON.parse(document.getElementById('catalog-data').textContent);
    const p = data.find((x) => x.s === b.dataset.quickAdd);
    if (p) add(p.s, p.c[0]?.id, p.z ? p.z[Math.min(1, p.z.length - 1)] : null);
  });
}
