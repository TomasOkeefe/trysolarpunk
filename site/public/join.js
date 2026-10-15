// Submits waitlist forms in place. Without JS the form posts normally and the server redirects.
for (const form of document.querySelectorAll('form.join')) {
  const msg = form.querySelector('.join-msg');
  const button = form.querySelector('button');
  form.elements.source.value = new URLSearchParams(location.search).get('v') || '';

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
