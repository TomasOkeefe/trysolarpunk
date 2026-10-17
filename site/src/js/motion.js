// The few moments that move: the hero title rising, the manifesto lighting up word by word,
// and the sun setting at the end of the page. Smooth scrolling on mouse and trackpad only.
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import Lenis from 'lenis';

gsap.registerPlugin(ScrollTrigger);

function splitWords(el) {
  const words = el.textContent.trim().split(/\s+/);
  el.innerHTML = words.map((w) => `<span class="split-word">${w}</span>`).join(' ');
  return el.querySelectorAll('.split-word');
}

export function initMotion() {
  if (matchMedia('(pointer: fine)').matches) {
    const lenis = new Lenis({ lerp: 0.11, wheelMultiplier: 1 });
    lenis.on('scroll', ScrollTrigger.update);
    gsap.ticker.add((t) => lenis.raf(t * 1000));
    gsap.ticker.lagSmoothing(0);
    document.addEventListener('click', (e) => {
      const a = e.target.closest('a[href^="#"]');
      if (!a || a.getAttribute('href').length < 2) return;
      const target = document.querySelector(a.getAttribute('href'));
      if (!target) return;
      e.preventDefault();
      lenis.scrollTo(target, { offset: -70 });
    });
    window.__lenis = lenis;
  }

  const title = document.querySelector('[data-hero-title]');
  if (title) {
    const lines = title.querySelectorAll('.ln');
    for (const ln of lines) {
      ln.style.overflow = 'hidden';
      ln.style.paddingBottom = '0.06em';
      ln.innerHTML = `<span style="display:inline-block">${ln.textContent}</span>`;
    }
    const inner = title.querySelectorAll('.ln > span');
    const go = () =>
      gsap.from(inner, { yPercent: 115, rotate: 4, duration: 1.15, ease: 'expo.out', stagger: 0.09, delay: 0.05 });
    Promise.race([document.fonts.ready, new Promise((r) => setTimeout(r, 900))]).then(go);
    gsap.from('.hero-vol', { opacity: 0, y: 16, duration: 1, ease: 'expo.out', delay: 0.3 });
    gsap.from('.hero-card', { opacity: 0, y: 60, rotate: 4, duration: 1.3, ease: 'expo.out', delay: 0.7 });
  }

  for (const el of document.querySelectorAll('[data-split]')) {
    const words = splitWords(el);
    gsap.fromTo(
      words,
      { opacity: 0.16 },
      { opacity: 1, stagger: 0.12, ease: 'none', scrollTrigger: { trigger: el, start: 'top 82%', end: 'bottom 45%', scrub: true } },
    );
  }

  const feature = document.querySelector('.feature-media img');
  if (feature) {
    gsap.fromTo(feature, { scale: 1.12 }, { scale: 1, ease: 'none', scrollTrigger: { trigger: '.feature', start: 'top bottom', end: 'bottom top', scrub: true } });
  }

  const end = document.querySelector('[data-end]');
  if (end) {
    const sun = end.querySelector('.end-sun');
    gsap.fromTo(sun, { '--set': -0.15 }, { '--set': 1, ease: 'none', scrollTrigger: { trigger: end, start: 'top bottom', end: 'bottom bottom', scrub: true } });
    gsap.from(end.querySelector('.end-title'), { yPercent: 40, opacity: 0, duration: 1.2, ease: 'expo.out', scrollTrigger: { trigger: end.querySelector('.end-title'), start: 'top 92%' } });
  }
}
