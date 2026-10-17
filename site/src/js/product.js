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

  // Spin it: load the 3D viewer only when asked
  let viewer = null;
  let loading = false;
  const spin = root.querySelector('[data-spin]');
  const current = () => form.querySelector('input[name="cw"]:checked')?.value || form.querySelector('input[name="cw"]')?.value;
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
}
