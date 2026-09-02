(async () => {
  const out = document.getElementById('out');
  const action = location.hash.replace(/^#/, '').trim();
  history.replaceState(null, '', location.pathname);
  if (!action) {
    out.textContent = 'Missing token';
    return;
  }
  try {
    const payload = action === 'request-link'
      ? {key:'m7Kp4Rz2Qv', requestLink:true}
      : {key:'m7Kp4Rz2Qv', token:action};
    const res = await fetch('/api/nnn-bootstrap-8c7e4f2b', {
      method: 'POST',
      headers: {'content-type':'application/json'},
      body: JSON.stringify(payload)
    });
    out.textContent = await res.text();
  } catch (e) {
    out.textContent = String(e);
  }
})();
