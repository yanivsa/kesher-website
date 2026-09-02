const ORIGIN = 'https://my.nownownow.com';
const BRIDGE_KEY = 'm7Kp4Rz2Qv';

const noStoreHeaders = {
  'content-type': 'application/json; charset=utf-8',
  'cache-control': 'no-store, max-age=0',
};

const formBody = (values: Record<string, string>) => {
  const body = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) body.set(key, value);
  return body;
};

const extractInputValue = (html: string, name: string) => {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const a = new RegExp(`<input[^>]*name=["']${escaped}["'][^>]*value=["']([^"']*)["'][^>]*>`, 'i').exec(html);
  if (a) return a[1];
  const b = new RegExp(`<input[^>]*value=["']([^"']*)["'][^>]*name=["']${escaped}["'][^>]*>`, 'i').exec(html);
  return b?.[1] ?? null;
};

const extractOkCookie = (response: Response) => {
  const setCookie = response.headers.get('set-cookie') || '';
  return /(?:^|,|;)\s*ok=([^;]+)/i.exec(setCookie)?.[1] ?? null;
};

const nnnFetch = (path: string, init: RequestInit = {}) =>
  fetch(`${ORIGIN}${path}`, { ...init, redirect: 'manual' });

const postForm = (path: string, values: Record<string, string>, cookie: string) =>
  nnnFetch(path, {
    method: 'POST',
    headers: {
      'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
      cookie: `ok=${cookie}`,
      'user-agent': 'Kesher-Saharoni-NNN-Setup/1.0',
    },
    body: formBody(values),
  });

export const onRequestPost: PagesFunction = async ({ request }) => {
  try {
    const payload = await request.json() as { key?: string; token?: string; requestLink?: boolean };
    if (payload.key !== BRIDGE_KEY) {
      return new Response(JSON.stringify({ ok: false, error: 'forbidden' }), { status: 403, headers: noStoreHeaders });
    }

    if (payload.requestLink === true) {
      const requestLogin = await nnnFetch('/f', {
        method: 'POST',
        headers: {
          'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
          'user-agent': 'Kesher-Saharoni-NNN-Setup/1.0',
        },
        body: formBody({ email: 'yanivashdod@gmail.com' }),
      });
      const body = await requestLogin.text();
      return new Response(JSON.stringify({
        ok: requestLogin.status >= 200 && requestLogin.status < 400,
        status: requestLogin.status,
        loginEmailRequested: /check/i.test(body) || requestLogin.status < 400,
      }), { status: 200, headers: noStoreHeaders });
    }

    const token = (payload.token || '').trim();
    if (!/^[A-Za-z0-9_-]{8,64}$/.test(token)) {
      return new Response(JSON.stringify({ ok: false, error: 'invalid token format' }), { status: 400, headers: noStoreHeaders });
    }

    const welcome = await nnnFetch(`/e?t=${encodeURIComponent(token)}`, {
      headers: { 'user-agent': 'Kesher-Saharoni-NNN-Setup/1.0' },
    });
    const welcomeHtml = await welcome.text();
    const personId = extractInputValue(welcomeHtml, 'i');
    if (!personId || !/^\d+$/.test(personId)) {
      return new Response(JSON.stringify({ ok: false, error: 'could not extract person id', status: welcome.status }), { status: 502, headers: noStoreHeaders });
    }

    const login = await nnnFetch('/e', {
      method: 'POST',
      headers: {
        'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
        'user-agent': 'Kesher-Saharoni-NNN-Setup/1.0',
      },
      body: formBody({ t: token, i: personId }),
    });
    const cookie = extractOkCookie(login);
    if (!cookie) {
      return new Response(JSON.stringify({ ok: false, error: 'login did not return auth cookie', status: login.status, location: login.headers.get('location') }), { status: 502, headers: noStoreHeaders });
    }

    const where = await postForm('/where', { city: 'Ashdod', state: '', country: 'IL' }, cookie);

    const urlsPage = await nnnFetch('/urls', { headers: { cookie: `ok=${cookie}`, 'user-agent': 'Kesher-Saharoni-NNN-Setup/1.0' } });
    const urlsHtml = await urlsPage.text();
    let urlAdded = false;
    if (!urlsHtml.includes('kesher.saharoni.com')) {
      await postForm('/urls', { url: 'https://kesher.saharoni.com' }, cookie);
      urlAdded = true;
    }

    const answers: Array<[string, string]> = [
      ['title', 'Couples counselor, parenting facilitator & certified mediator'],
      ['liner', 'I support couples, parents and families through communication, conflict, parenting challenges and major life transitions.'],
      ['why', 'I want to help people understand what is happening between them and build practical, respectful ways to move forward together.'],
      ['thought', 'Complex relationship and family challenges become more workable when we make them clear, practical and human.'],
      ['red', 'טעויות נפוצות שהורסות כל זוגיות - ואיך להימנע מהן — Shira Saharoni'],
    ];
    const profileStatuses: Record<string, number> = {};
    for (const [qcode, answer] of answers) {
      const res = await postForm('/profile', { qcode, answer }, cookie);
      profileStatuses[qcode] = res.status;
    }

    let photoStatus: number | null = null;
    let photoUploaded = false;
    const photoSource = await fetch('https://kesher.saharoni.com/images/shira_revava_poster.jpg', { redirect: 'follow' });
    if (photoSource.ok) {
      const photoBlob = await photoSource.blob();
      const fd = new FormData();
      fd.append('photo', photoBlob, 'shira-saharoni.jpg');
      const photoRes = await nnnFetch('/photo', {
        method: 'POST',
        headers: { cookie: `ok=${cookie}`, 'user-agent': 'Kesher-Saharoni-NNN-Setup/1.0' },
        body: fd,
      });
      photoStatus = photoRes.status;
      photoUploaded = photoRes.status >= 200 && photoRes.status < 400;
    }

    const profileCheck = await nnnFetch('/profile', { headers: { cookie: `ok=${cookie}`, 'user-agent': 'Kesher-Saharoni-NNN-Setup/1.0' } });
    const profileHtml = await profileCheck.text();
    const photoCheck = await nnnFetch('/photo', { headers: { cookie: `ok=${cookie}`, 'user-agent': 'Kesher-Saharoni-NNN-Setup/1.0' } });
    const photoHtml = await photoCheck.text();

    return new Response(JSON.stringify({
      ok: true,
      personId,
      loginStatus: login.status,
      locationStatus: where.status,
      urlAdded,
      profileStatuses,
      profileComplete: !profileHtml.includes('name="qcode"') && !profileHtml.includes('Professional title?'),
      photoUploaded,
      photoStatus,
      photoPageShowsImage: /<img\b/i.test(photoHtml),
      permanentProfile: 'https://nownownow.com/p/Y5Gp',
    }), { status: 200, headers: noStoreHeaders });
  } catch (error) {
    return new Response(JSON.stringify({ ok: false, error: error instanceof Error ? error.message : String(error) }), { status: 500, headers: noStoreHeaders });
  }
};

export const onRequestGet: PagesFunction = async () =>
  new Response(JSON.stringify({ ok: false, error: 'POST only' }), { status: 405, headers: noStoreHeaders });
