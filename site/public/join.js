// Submits waitlist forms in place. Without JS the form posts normally and the server redirects.

// Which video or site sent this visitor: ?v= from the link, else the referring site's host.
function visitSource() {
  const v = new URLSearchParams(location.search).get('v');
  if (v) return v;
  try {
    const host = new URL(document.referrer).host;
    return host !== location.host ? host.replace(/^www\./, '') : '';
  } catch {
    return '';
  }
}

const source = visitSource();

// Keep the source when someone taps from the home page through to a product.
if (source) {
  for (const a of document.querySelectorAll('a[href^="/"]')) {
    const url = new URL(a.href);
    url.searchParams.set('v', source);
    a.href = url.pathname + url.search;
  }
}

for (const form of document.querySelectorAll('form.join')) {
  const msg = form.querySelector('.join-msg');
  const button = form.querySelector('button');
  form.elements.source.value = source;

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    button.disabled = true;
    msg.textContent = '';
    try {
      const res = await fetch(form.action, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(Object.fromEntries(new FormData(form))),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.ok) {
        form.classList.add('done');
        return;
      }
      msg.textContent = data.error || 'Something broke on our end. Try again in a minute.';
    } catch {
      msg.textContent = 'No connection. Try again?';
    }
    button.disabled = false;
  });
}
