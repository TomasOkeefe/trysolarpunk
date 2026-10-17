// Moss videos: load and play only while on screen.
export function initReel() {
  const videos = document.querySelectorAll('[data-reel] video');
  if (!videos.length) return;
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const io = new IntersectionObserver(
    (entries) => {
      for (const { target: v, isIntersecting } of entries) {
        if (isIntersecting) {
          if (!v.src && v.dataset.src) v.src = v.dataset.src;
          if (!reduce) v.play().catch(() => {});
        } else v.pause();
      }
    },
    { rootMargin: '200px 0px' },
  );
  videos.forEach((v) => io.observe(v));
}
