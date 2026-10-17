// Which video or site sent this visitor: ?v= from the bio link, else the referring site's host.
// It rides along on internal links and is sent with every reservation.
const KEY = 'tsp-source';

function fromVisit() {
  const v = new URLSearchParams(location.search).get('v');
  if (v) return v;
  try {
    const host = new URL(document.referrer).host;
    return host && host !== location.host ? host.replace(/^www\./, '') : '';
  } catch {
    return '';
  }
}

function remember(value) {
  try {
    if (value) sessionStorage.setItem(KEY, value);
    return value || sessionStorage.getItem(KEY) || '';
  } catch {
    return value;
  }
}

export const source = remember(fromVisit());

export function carrySource(root = document) {
  if (!source) return;
  for (const a of root.querySelectorAll('a[href^="/"]')) {
    const url = new URL(a.href, location.origin);
    if (url.pathname.startsWith('/api/')) continue;
    url.searchParams.set('v', source);
    a.href = url.pathname + url.search + url.hash;
  }
  for (const input of root.querySelectorAll('input[name="source"]')) input.value = source;
}
