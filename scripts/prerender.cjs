const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { chromium } = require('playwright');
const { ROOT, STATIC_ROUTES, isPublishable, blogRoute } = require('./content-policy.cjs');

const dist = path.join(ROOT, 'dist');
const posts = JSON.parse(fs.readFileSync(path.join(ROOT, 'src/data/posts.json'), 'utf8'));
const routes = [...STATIC_ROUTES, ...posts.filter(isPublishable).map(blogRoute)];
const port = 4179;
let viteExitCode = null;
const vite = spawn(process.execPath, [
  path.join(ROOT, 'node_modules/vite/bin/vite.js'),
  'preview',
  '--host',
  '127.0.0.1',
  '--port',
  String(port),
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
    } catch {}
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
  const directory = path.join(dist, route.replace(/^\//, ''));
  fs.mkdirSync(directory, { recursive: true });
  fs.writeFileSync(path.join(directory, 'index.html'), html);
};

(async () => {
  let browser;
  try {
    await waitForServer();
    browser = await chromium.launch();
    const page = await browser.newPage();

    for (const route of routes) {
      await page.goto(`http://127.0.0.1:${port}${route}`, { waitUntil: 'networkidle' });
      await page.waitForSelector('#main-content h1');
      writeRoute(route, await page.content());
    }

    await page.goto(`http://127.0.0.1:${port}/__not-found__`, { waitUntil: 'networkidle' });
    await page.waitForSelector('#main-content h1');
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
