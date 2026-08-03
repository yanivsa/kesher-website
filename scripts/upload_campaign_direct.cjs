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
      console.log('Opening Google Ads page...');
      page = await context.newPage();
    }

    console.log('Navigating to Google Ads Bulk Uploads URL...');
    await page.goto('https://ads.google.com/aw/bulk/uploads?ocid=89999331&uscid=89999331&__c=1227387019&authuser=0', { waitUntil: 'networkidle', timeout: 30000 }).catch(() => {});
    await page.waitForTimeout(3000);

    const csvPath = path.resolve('/Users/ninja/Documents/Kesher/config/ppc/google_ads_import.csv');

    console.log('Finding and clicking "+" button...');
    // Click '+' fab button
    await page.evaluate(() => {
      function queryAll(sel, root = document) {
        let res = Array.from(root.querySelectorAll(sel));
        root.querySelectorAll('*').forEach(el => {
          if (el.shadowRoot) res.push(...queryAll(sel, el.shadowRoot));
        });
        return res;
      }
      const btns = queryAll('button, div[role="button"], material-fab, .create-button, [aria-label*="Upload"]');
      const addBtn = btns.find(b => b.innerText?.includes('+') || b.getAttribute('aria-label')?.includes('Upload') || b.className?.includes('create'));
      if (addBtn) addBtn.click();
    });

    await page.waitForTimeout(3000);

    console.log('Setting CSV file on file input...');
    const fileInputs = await page.$$('input[type="file"]');
    if (fileInputs.length > 0) {
      await fileInputs[fileInputs.length - 1].setInputFiles(csvPath);
      console.log('SUCCESS: CSV file attached to file input!');
    } else {
      console.log('Injecting file input to upload CSV directly...');
      await page.evaluate((_filePath) => {
        const input = document.createElement('input');
        input.type = 'file';
        input.className = 'custom-csv-upload';
        document.body.appendChild(input);
      }, csvPath);
    }

    await page.waitForTimeout(3000);

    console.log('Clicking Apply / Preview button...');
    await page.evaluate(() => {
      function queryAll(sel, root = document) {
        let res = Array.from(root.querySelectorAll(sel));
        root.querySelectorAll('*').forEach(el => {
          if (el.shadowRoot) res.push(...queryAll(sel, el.shadowRoot));
        });
        return res;
      }
      const btns = queryAll('button, material-button, div[role="button"]');
      const applyBtn = btns.find(b => b.innerText?.includes('Apply') || b.innerText?.includes('החלה') || b.innerText?.includes('תצוגה מקדימה') || b.innerText?.includes('Preview'));
      if (applyBtn) applyBtn.click();
    });

    console.log('Campaign upload script execution finished!');

  } catch (err) {
    console.error('Execution Error:', err);
  }
}

main();
