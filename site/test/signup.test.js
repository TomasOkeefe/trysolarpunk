import { test } from 'node:test';
import assert from 'node:assert/strict';
import { PRODUCTS, cleanSource, pickSource, parseSignup } from '../lib/signup.js';

const HOST = 'trysolarpunk.pages.dev';

test('products are fixed', () => {
  assert.deepEqual(PRODUCTS, ['hibernator', 'eyelid', 'merch']);
});

test('good signup is normalized', () => {
  assert.deepEqual(
    parseSignup({ email: '  Me@Example.COM ', product: 'eyelid', source: 'phone-nap' }, null, HOST),
    { ok: true, email: 'me@example.com', product: 'eyelid', source: 'phone-nap' },
  );
});

test('honeypot is a silent success', () => {
  assert.deepEqual(
    parseSignup({ email: 'bot@x.com', product: 'merch', website: 'spam.biz' }, null, HOST),
    { ok: true, bot: true, product: 'merch' },
  );
  assert.deepEqual(
    parseSignup({ product: 'toaster', website: 'x' }, null, HOST),
    { ok: true, bot: true, product: null },
  );
});

test('unknown or missing product is a 400', () => {
  for (const product of ['toaster', '', undefined, 'Hibernator']) {
    const r = parseSignup({ email: 'a@b.co', product }, null, HOST);
    assert.equal(r.ok, false);
    assert.equal(r.status, 400);
    assert.equal(r.product, null);
  }
});

test('bad emails are a 400 that remembers the product', () => {
  const long = 'a'.repeat(250) + '@b.co';
  for (const email of ['', 'nope', 'a@b', '@b.co', 'a b@c.co', long, undefined]) {
    const r = parseSignup({ email, product: 'hibernator' }, null, HOST);
    assert.equal(r.ok, false, `accepted ${email}`);
    assert.equal(r.status, 400);
    assert.equal(r.product, 'hibernator');
  }
});

test('array or empty fields are a 400', () => {
  assert.equal(parseSignup([], null, HOST).status, 400);
  assert.equal(parseSignup({}, null, HOST).status, 400);
});

test('cleanSource cleans instead of rejecting', () => {
  assert.equal(cleanSource('Phone Nap!!'), 'phone-nap');
  assert.equal(cleanSource('  --x--  '), 'x');
  assert.equal(cleanSource('🐻 bear'), 'bear');
  assert.equal(cleanSource(null), '');
  assert.equal(cleanSource(undefined), '');
  const long = cleanSource('ab-'.repeat(200));
  assert.ok(long.length <= 64);
  assert.match(long, /^[a-z0-9][a-z0-9-]*[a-z0-9]$/);
});

test('pickSource prefers the explicit value', () => {
  assert.equal(pickSource('Video-1', `https://${HOST}/eyelid?v=other`, HOST), 'video-1');
});

test('pickSource falls back to ?v= on our own referer', () => {
  assert.equal(pickSource('', `https://${HOST}/eyelid?v=Phone-Nap`, HOST), 'phone-nap');
  assert.equal(pickSource('', `https://${HOST}/eyelid`, HOST), '');
});

test('pickSource uses a foreign referer host', () => {
  assert.equal(pickSource('', 'https://www.tiktok.com/@trysolarpunk', HOST), 'tiktok-com');
});

test('pickSource survives junk referers', () => {
  assert.equal(pickSource('', 'not a url', HOST), '');
  assert.equal(pickSource('', null, HOST), '');
});
