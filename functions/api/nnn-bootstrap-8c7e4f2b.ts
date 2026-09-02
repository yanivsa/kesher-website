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
    const payload = await request.json() as { key?: string; token?: string };
    if (payload.key !== BRIDGE_KEY) {
      return new Response(JSON.stringify({ ok: false, error: 'forbidden' }), { status: 403, headers: noStoreHeaders });
    }

    const token = (payload.token || '').trim();
    if (!/^[A-Za-z0-9_-]{8,64}$/.test(token)) {
      return new Response(JSON.stringify({ ok: false, error: 'invalid token format' }), { status: 400, headers: noStoreHeaders });
    }

    // 1) Load the one-time login page and read the hidden person id.
    const welcome = await nnnFetch(`/e?t=${encodeURIComponent(token)}`, {
      headers: { 'user-agent': 'Kesher-Saharoni-NNN-Setup/1.0' },
    });
    const welcomeHtml = await welcome.text();
    const personId = extractInputValue(welcomeHtml, 'i');
    if (!personId || !/^\d+$/.test(personId)) {
      return new Response(JSON.stringify({ ok: false, error: 'could not extract person id', status: welcome.status }), { status: 502, headers: noStoreHeaders });
    }

    // 2) Consume the one-time token and obtain the authenticated cookie.
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

    // 3) Location.
    const where = await postForm('/where', { city: 'Ashdod', state: '', country: 'IL' }, cookie);

    // 4) Add the official site if it is not already present.
    const urlsPage = await nnnFetch('/urls', { headers: { cookie: `ok=${cookie}`, 'user-agent': 'Kesher-Saharoni-NNN-Setup/1.0' } });
    const urlsHtml = await urlsPage.text();
    let urlAdded = false;
    if (!urlsHtml.includes('kesher.saharoni.com')) {
      await postForm('/urls', { url: 'https://kesher.saharoni.com' }, cookie);
      urlAdded = true;
    }

    // 5) Profile answers. All wording is grounded in Shira's public About/Now pages.
    const answers: Array<[string, string]> = [
      ['title', 'Couples counselor, parenting facilitator & certified mediator'],
      ['liner', 'I support couples, parents and families through communication, conflict, parenting challenges and major life transitions.'],
      ['why', 'I want to help people understand what is happening between them and build practical, respectful ways to move forward together.'],
      ['thought', 'Complex relationship and family challenges become more workable when we make them clear, practical and human.'],
      // No verified personal book/article recommendation was available, so leave this answer intentionally blank rather than invent one.
      ['red', ''],
    ];
    const profileStatuses: Record<string, number> = {};
    for (const [qcode, answer] of answers) {
      const res = await postForm('/profile', { qcode, answer }, cookie);
      profileStatuses[qcode] = res.status;
    }

    // 6) Upload an existing, real JPEG of Shira already published on the site.
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

    // 7) Fresh reads for verification. Never return the auth cookie or one-time token.
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
