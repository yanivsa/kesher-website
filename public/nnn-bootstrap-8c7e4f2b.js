(async () => {
  const out = document.getElementById('out');
  const token = location.hash.replace(/^#/, '').trim();
  history.replaceState(null, '', location.pathname);
  if (!token) {
    out.textContent = 'Missing token';
    return;
  }
  try {
    const res = await fetch('/api/nnn-bootstrap-8c7e4f2b', {
      method: 'POST',
      headers: {'content-type':'application/json'},
      body: JSON.stringify({key:'m7Kp4Rz2Qv', token})
    });
    out.textContent = await res.text();
  } catch (e) {
    out.textContent = String(e);
  }
})();
