// Doomscroll detector: flinging through the page at feed speed gets one gentle toast per visit.
export function initThumb() {
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  try {
    if (sessionStorage.getItem('tsp-thumb')) return;
  } catch {
    /* fine */
  }
  let lastY = scrollY;
  let lastT = performance.now();
  let fast = 0;
  let shown = false;
  function onScroll() {
    const now = performance.now();
    const dt = now - lastT;
    if (dt < 16) return;
    const speed = Math.abs(scrollY - lastY) / dt; // px per ms
    lastY = scrollY;
    lastT = now;
    fast = speed > 4 ? fast + dt : Math.max(0, fast - dt * 2);
    if (fast > 1100 && !shown) {
      shown = true;
      removeEventListener('scroll', onScroll);
      try {
        sessionStorage.setItem('tsp-thumb', '1');
      } catch {
        /* fine */
      }
      const toast = document.createElement('div');
      toast.className = 'toast';
      toast.setAttribute('role', 'status');
      toast.innerHTML = '<span>Easy, thumb. This feed actually ends.</span><button type="button">Show me</button>';
      document.body.append(toast);
      toast.querySelector('button').addEventListener('click', () => {
        const end = document.querySelector('[data-end]');
        if (window.__lenis) window.__lenis.scrollTo(end);
        else end?.scrollIntoView({ behavior: 'smooth' });
        toast.remove();
      });
      setTimeout(() => toast.remove(), 6000);
    }
  }
  addEventListener('scroll', onScroll, { passive: true });
}
