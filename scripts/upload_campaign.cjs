const { chromium } = require('playwright');
const http = require('http');
const path = require('path');

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
    console.log('Connecting via CDP WebSocket:', wsEndpoint);
    const browser = await chromium.connectOverCDP(wsEndpoint);
    const context = browser.contexts()[0];
    let page = context.pages().find(p => p.url().includes('ads.google.com'));

    if (!page) {
      console.log('Opening new Google Ads page...');
      page = await context.newPage();
    }

    console.log('Navigating to Google Ads Bulk Uploads page...');
    await page.goto('https://ads.google.com/aw/bulk/uploads?ocid=89999331&uscid=89999331&__c=1227387019&authuser=0', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(4000);

    const csvPath = path.resolve('/Users/ninja/Documents/Kesher/config/ppc/google_ads_import.csv');

    // Handle FileChooser event natively in Playwright
    const fileChooserPromise = page.waitForEvent('filechooser', { timeout: 10000 }).catch(() => null);

    // Click '+' button directly using DOM evaluate
    console.log('Clicking "+" add upload button...');
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button, div[role="button"], material-fab, .create-button'));
      const btn = btns.find(b => b.innerText?.includes('+') || b.getAttribute('aria-label')?.includes('Upload') || b.className?.includes('create'));
      if (btn) btn.click();
    });

    const fileChooser = await fileChooserPromise;
    if (fileChooser) {
      console.log('FileChooser triggered! Setting google_ads_import.csv...');
      await fileChooser.setFiles(csvPath);
      console.log('CSV file set successfully via FileChooser!');
    } else {
      console.log('Looking for file input in DOM...');
      const inputs = await page.$$('input[type="file"]');
      if (inputs.length > 0) {
        await inputs[inputs.length - 1].setInputFiles(csvPath);
        console.log('Set file on input element!');
      }
    }

    await page.waitForTimeout(3000);

    // Click Apply if present
    await page.evaluate(() => {
      const btns = Array.from(document.querySelectorAll('button, div[role="button"], material-button'));
      const applyBtn = btns.find(b => b.innerText?.includes('Apply') || b.innerText?.includes('החלה') || b.innerText?.includes('תצוגה מקדימה'));
      if (applyBtn) applyBtn.click();
    });

    console.log('Automation complete! Saved screenshot.');
    await page.screenshot({ path: '/Users/ninja/.gemini/antigravity/brain/2b7336e3-9a4e-47ca-97b9-998a5d0edecb/final_upload_result.png' });

  } catch (err) {
    console.error('Error:', err);
  }
}

main();
