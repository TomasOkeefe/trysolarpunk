// POST /api/join, the waitlist endpoint the site has always used. One row per email and product.
import { source } from './source.js';

export async function join({ email, product, website = '' }) {
  try {
    const res = await fetch('/api/join', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ email, product, source, website }),
    });
    const data = await res.json().catch(() => ({}));
    if (res.ok && data.ok) return { ok: true };
    return { ok: false, error: data.error || 'Something broke on our end. Try again in a minute.' };
  } catch {
    return { ok: false, error: 'No connection. Try again?' };
  }
}

// The plain waitlist forms (product pages without JS, the footer, merch): submit in place.
export function wireJoinForms(root = document) {
  for (const form of root.querySelectorAll('form.join')) {
    const msg = form.querySelector('.join-msg');
    const button = form.querySelector('button');
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      button.disabled = true;
      msg.textContent = '';
      const f = new FormData(form);
      const r = await join({ email: f.get('email'), product: f.get('product'), website: f.get('website') || '' });
      if (r.ok) {
        form.classList.add('done');
        try {
          const done = JSON.parse(localStorage.getItem('tsp-reserved') || '[]');
          localStorage.setItem('tsp-reserved', JSON.stringify([...new Set([...done, f.get('product')])]));
        } catch {
          /* fine */
        }
      } else msg.textContent = r.error;
      button.disabled = false;
    });
  }
}
