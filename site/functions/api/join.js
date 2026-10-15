import { parseSignup } from '../../lib/signup.js';

const BROKEN = 'Something broke on our end. Try again in a minute.';

export async function onRequestPost({ request, env }) {
  const url = new URL(request.url);
  const isJson = (request.headers.get('content-type') || '').includes('application/json');

  let fields = null;
  try {
    fields = isJson ? await request.json() : Object.fromEntries(await request.formData());
  } catch {
    fields = null;
  }

  let result =
    fields && typeof fields === 'object'
      ? parseSignup(fields, request.headers.get('referer'), url.host)
      : { ok: false, status: 400, error: 'Bad request.', product: null };

  if (result.ok && !result.bot) {
    try {
      await env.DB.prepare('INSERT OR IGNORE INTO signups (email, product, source) VALUES (?, ?, ?)')
        .bind(result.email, result.product, result.source)
        .run();
    } catch (err) {
      console.error('join: insert failed', err);
      result = { ok: false, status: 500, error: BROKEN, product: result.product };
    }
  }

  if (isJson) {
    return Response.json(result.ok ? { ok: true } : { ok: false, error: result.error }, {
      status: result.ok ? 200 : result.status,
    });
  }
  const page = result.product ? `/${result.product}` : '/';
  const target = result.ok ? `${page}?joined=1#joined` : `${page}?error=1#join-error`;
  return new Response(null, { status: 303, headers: { Location: target } });
}
