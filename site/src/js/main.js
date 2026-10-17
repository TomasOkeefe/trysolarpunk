import { wireJoinForms } from './api.js';
import { initBag } from './bag.js';
import { initMotion } from './motion.js';
import { initNav } from './nav.js';
import { initProduct, initQuickAdd } from './product.js';
import { initReel } from './reel.js';
import { carrySource } from './source.js';

carrySource();
initNav();
initBag();
initProduct();
initQuickAdd();
wireJoinForms();
initReel();
initMotion();

const hero = document.querySelector('[data-hero]');
const canvas = hero?.querySelector('[data-meadow]');
const saveData = navigator.connection?.saveData;
if (canvas && !saveData) {
  const gl = document.createElement('canvas').getContext('webgl2');
  if (gl) {
    import('./meadow.js')
      .then((m) => m.startMeadow(canvas, hero))
      .catch((err) => console.warn('meadow off:', err));
  }
}
