const { chromium } = require('playwright');

async function main() {
  console.log('Connecting to Chrome via CDP on port 9222...');
  try {
    const browser = await chromium.connectOverCDP('http://localhost:9222');
    const contexts = browser.contexts();
    const pages = contexts[0].pages();
    console.log(`Connected to Chrome! Open pages count: ${pages.length}`);
    for (const page of pages) {
      console.log(`Page: ${await page.title()} -> ${page.url()}`);
    }
  } catch (err) {
    console.log('CDP port 9222 not active yet. Starting Chrome with remote debugging port 9222...');
  }
}

main();
