const { chromium } = require('playwright');
const http = require('http');

function getWsUrl() {
  return new Promise((resolve, reject) => {
    http.get('http://localhost:9222/json/version', (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          resolve(json.webSocketDebuggerUrl);
        } catch (e) {
          reject(e);
        }
      });
    }).on('error', reject);
  });
}

async function main() {
  try {
    const wsEndpoint = await getWsUrl();
    console.log('Connecting to WebSocket:', wsEndpoint);
    const browser = await chromium.connectOverCDP(wsEndpoint);
    console.log('Successfully connected Playwright directly to Chrome!');

    const contexts = browser.contexts();
    const context = contexts[0];
    const pages = context.pages();
    console.log(`Open tabs count: ${pages.length}`);

    for (const page of pages) {
      console.log(`Tab Title: "${await page.title()}" | URL: ${page.url()}`);
    }

    // Find or navigate to Google Ads tab
    let gadsPage = pages.find(p => p.url().includes('ads.google.com'));
    if (!gadsPage) {
      gadsPage = await context.newPage();
      await gadsPage.goto('https://ads.google.com/aw/campaigns/new?ocid=89999331&uscid=89999331&__c=1227387019&authuser=0');
    }

    console.log('Active Google Ads Page URL:', gadsPage.url());

    // Take screenshot of Google Ads page state for verification
    await gadsPage.screenshot({ path: '/Users/ninja/.gemini/antigravity/brain/2b7336e3-9a4e-47ca-97b9-998a5d0edecb/gads_state.png' });
    console.log('Saved screenshot to gads_state.png');

  } catch (err) {
    console.error('Automation Error:', err);
  }
}

main();
