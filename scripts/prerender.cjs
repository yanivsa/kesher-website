const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { chromium } = require('playwright');
const { ROOT, STATIC_ROUTES, isPublishable, blogRoute } = require('./content-policy.cjs');

const dist = path.join(ROOT, 'dist');
const posts = JSON.parse(fs.readFileSync(path.join(ROOT, 'src/data/posts.json'), 'utf8'));
const routes = [
  ...STATIC_ROUTES.filter(r => r !== '/'),
  ...posts.filter(isPublishable).map(blogRoute),
  '/'
];
const port = 4179;
let viteExitCode = null;
const vite = spawn(process.execPath, [
  path.join(ROOT, 'node_modules/vite/bin/vite.js'),
  'preview',
  '--host',
  '127.0.0.1',
  '--port',
  String(port),
  '--strictPort',
], { cwd: ROOT, stdio: 'inherit' });
vite.on('exit', (code) => {
  viteExitCode = code;
});

const waitForServer = async () => {
  for (let attempt = 0; attempt < 50; attempt += 1) {
    if (viteExitCode !== null) throw new Error(`Vite preview exited with code ${viteExitCode}`);
    try {
      const response = await fetch(`http://127.0.0.1:${port}/`);
      if (response.ok) return;
    } catch {
      // The preview server may still be starting; retry within the bounded loop.
    }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error('Vite preview did not start');
};

const stopVite = () => {
  if (!vite.killed && viteExitCode === null) vite.kill();
};

const writeRoute = (route, html) => {
  if (route === '/') {
    fs.writeFileSync(path.join(dist, 'index.html'), html);
    return;
  }
  const file = path.join(dist, `${route.replace(/^\//, '')}.html`);
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, html);
};

(async () => {
  let browser;
  try {
    await waitForServer();
    browser = await chromium.launch();
    const page = await browser.newPage();
    await page.route(/\.(png|jpg|jpeg|webp|svg|gif|mp4|webm|woff2?)$/i, (route) => route.abort());
    await page.route(/(googletagmanager|google-analytics|calendly)\.com/, (route) => route.abort());

    for (const route of routes) {
      await page.goto(`http://127.0.0.1:${port}${route}`, { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('#main-content h1');
      await page.waitForSelector('link[rel="canonical"]', { state: 'attached' });
      writeRoute(route, await page.content());
    }

    await page.goto(`http://127.0.0.1:${port}/__not-found__`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#main-content h1');
    await page.waitForSelector('meta[name="robots"][content*="noindex"]', { state: 'attached' });
    fs.writeFileSync(path.join(dist, '404.html'), await page.content());
  } finally {
    if (browser) await browser.close();
    stopVite();
  }
})().catch((error) => {
  console.error(error);
  stopVite();
  process.exit(1);
});
