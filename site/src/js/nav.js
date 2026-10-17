// Header: border once you scroll, tucks away while you scroll down, back when you scroll up.
// Menu: full-screen on small screens.
export function initNav() {
  const head = document.querySelector('[data-head]');
  const btn = document.querySelector('[data-menu]');
  const panel = document.querySelector('[data-menu-panel]');
  let last = scrollY;
  let ticking = false;

  addEventListener(
    'scroll',
    () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(() => {
        const y = scrollY;
        head.classList.toggle('is-scrolled', y > 8);
        const menuOpen = btn?.getAttribute('aria-expanded') === 'true';
        head.classList.toggle('is-hidden', !menuOpen && y > 240 && y > last + 4);
        if (y < last - 4) head.classList.remove('is-hidden');
        last = y;
        ticking = false;
      });
    },
    { passive: true },
  );

  if (!btn || !panel) return;
  const set = (open) => {
    btn.setAttribute('aria-expanded', String(open));
    btn.querySelector('.vh').textContent = open ? 'Close menu' : 'Menu';
    document.documentElement.classList.toggle('menu-open', open);
    if (open) {
      panel.hidden = false;
      requestAnimationFrame(() => panel.classList.add('is-open'));
    } else {
      panel.classList.remove('is-open');
      setTimeout(() => {
        if (btn.getAttribute('aria-expanded') === 'false') panel.hidden = true;
      }, 650);
    }
  };
  btn.addEventListener('click', () => set(btn.getAttribute('aria-expanded') !== 'true'));
  panel.addEventListener('click', (e) => {
    if (e.target.closest('a')) set(false);
  });
  addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && btn.getAttribute('aria-expanded') === 'true') {
      set(false);
      btn.focus();
    }
  });
}
