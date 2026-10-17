// Product page: the colour picker swaps the photo, Add to bag puts the pick in the bag.
import { add } from './bag.js';

export function initProduct() {
  const root = document.querySelector('[data-product]');
  if (!root) return;
  const slug = root.dataset.product;
  const form = root.querySelector('[data-buy]');
  const stage = root.querySelector('[data-stage]');
  const name = root.querySelector('[data-cw-name]');

  function show(id, push) {
    const shot = stage.querySelector(`.pdp-shot[data-cw="${CSS.escape(id)}"]`);
    if (!shot) return;
    for (const s of stage.querySelectorAll('.pdp-shot')) s.classList.toggle('is-on', s === shot);
    stage.style.setProperty('--bg', getComputedStyle(shot).getPropertyValue('--bg'));
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

  form.addEventListener('change', (event) => {
    if (event.target.name === 'cw') show(event.target.value, true);
  });
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const f = new FormData(form);
    add(slug, f.get('cw'), f.get('size'));
  });
}
