const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');
const { spawn } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const port = 4173;

(async () => {
  const vite = spawn(process.execPath, [
    path.join(ROOT, 'node_modules/vite/bin/vite.js'),
    'preview',
    '--host',
    '127.0.0.1',
    '--port',
    String(port),
  ], { cwd: ROOT, stdio: 'ignore' });

  // wait for preview server
  for (let i = 0; i < 30; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/`);
      if (res.ok) break;
    } catch {
      await new Promise((r) => setTimeout(r, 200));
    }
  }

  const screenshotDir = path.join(ROOT, 'public/images/landing-previews');
  fs.mkdirSync(screenshotDir, { recursive: true });

  const browser = await chromium.launch();

  // Desktop Screenshot (1440x900)
  const pageDesktop = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await pageDesktop.goto(`http://127.0.0.1:${port}/couples-counseling-ashdod`, { waitUntil: 'domcontentloaded' });
  await pageDesktop.waitForSelector('#main-content h1');
  await pageDesktop.screenshot({ path: path.join(screenshotDir, 'desktop_preview.png'), fullPage: true });

  // Mobile Screenshot (390x844)
  const pageMobile = await browser.newPage({ viewport: { width: 390, height: 844 } });
  await pageMobile.goto(`http://127.0.0.1:${port}/couples-counseling-ashdod`, { waitUntil: 'domcontentloaded' });
  await pageMobile.waitForSelector('#main-content h1');
  await pageMobile.screenshot({ path: path.join(screenshotDir, 'mobile_preview.png'), fullPage: true });

  await browser.close();
  vite.kill();
  console.log('Screenshots generated successfully!');
})();
