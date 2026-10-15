// Validation for POST /api/join, kept free of Cloudflare APIs so node --test can run it.
export const PRODUCTS = ['hibernator', 'eyelid', 'merch'];

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Which video (or site) a signup came from: lowercase letters, digits and dashes, max 64.
export function cleanSource(raw) {
  return String(raw ?? '')
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 64)
    .replace(/-+$/, '');
}

// Explicit source, else ?v= from our own page, else the referring site's host.
export function pickSource(raw, referer, ownHost) {
  const direct = cleanSource(raw);
  if (direct) return direct;
  let ref;
  try {
    ref = new URL(referer);
  } catch {
    return '';
  }
  if (ref.host === ownHost) return cleanSource(ref.searchParams.get('v'));
  return cleanSource(ref.host.replace(/^www\./, ''));
}

export function parseSignup(fields, referer, ownHost) {
  const product = PRODUCTS.includes(fields?.product) ? fields.product : null;
  if (fields?.website) return { ok: true, bot: true, product };
  if (!product) return { ok: false, status: 400, error: 'Unknown product.', product };
  const email = String(fields.email ?? '').trim().toLowerCase();
  if (email.length > 254 || !EMAIL.test(email)) {
    return { ok: false, status: 400, error: "That email doesn't look right.", product };
  }
  return { ok: true, email, product, source: pickSource(fields.source, referer, ownHost) };
}
