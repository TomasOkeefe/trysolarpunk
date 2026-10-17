// Tiny HTML templating: html`...` escapes interpolated values unless they came from html`` or raw().
const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };

class Raw {
  constructor(s) {
    this.s = s;
  }
  toString() {
    return this.s;
  }
}

export const raw = (s) => new Raw(String(s));

function render(v) {
  if (v == null || v === false || v === true) return '';
  if (Array.isArray(v)) return v.map(render).join('');
  if (v instanceof Raw) return v.s;
  return String(v).replace(/[&<>"']/g, (c) => ESC[c]);
}

export function html(strings, ...values) {
  let out = strings[0];
  for (let i = 0; i < values.length; i++) out += render(values[i]) + strings[i + 1];
  return new Raw(out);
}

export const money = (n) => `$${Number.isInteger(n) ? n : n.toFixed(2)}`;
