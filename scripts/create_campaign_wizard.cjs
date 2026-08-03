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
    console.log('Connecting Playwright directly to Chrome via CDP:', wsEndpoint);
    const browser = await chromium.connectOverCDP(wsEndpoint);
    const context = browser.contexts()[0];
    let page = context.pages().find(p => p.url().includes('ads.google.com'));

    if (!page) {
      console.log('Opening Google Ads tab...');
      page = await context.newPage();
    }

    console.log('Step 1: Navigating to Campaign Creation Wizard...');
    await page.goto('https://ads.google.com/aw/campaigns/new?ocid=89999331&uscid=89999331&__c=1227387019&authuser=0', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(4000);

    // Dismiss ad blocker modal if present
    await page.evaluate(() => {
      const dialogs = document.querySelectorAll('material-dialog, div[role="dialog"], .modal, cdk-overlay-container');
      dialogs.forEach(d => { if (d.innerText?.includes('ad blocker')) d.remove(); });
      const backdrops = document.querySelectorAll('.cdk-overlay-backdrop, material-backdrop');
      backdrops.forEach(b => b.remove());
    });

    console.log('Step 2: Selecting "יצירת קמפיין ללא הנחיה" (Create without goal)...');
    await page.evaluate(() => {
      function queryAll(sel, root = document) {
        let res = Array.from(root.querySelectorAll(sel));
        root.querySelectorAll('*').forEach(el => { if (el.shadowRoot) res.push(...queryAll(sel, el.shadowRoot)); });
        return res;
      }
      const cards = queryAll('material-card, .card, div[role="radio"], div');
      const noGoal = cards.find(c => c.innerText && c.innerText.includes('יצירת קמפיין ללא הנחיה'));
      if (noGoal) noGoal.click();
    });

    await page.waitForTimeout(2000);

    console.log('Step 3: Selecting "חיפוש" (Search Network)...');
    await page.evaluate(() => {
      function queryAll(sel, root = document) {
        let res = Array.from(root.querySelectorAll(sel));
        root.querySelectorAll('*').forEach(el => { if (el.shadowRoot) res.push(...queryAll(sel, el.shadowRoot)); });
        return res;
      }
      const cards = queryAll('material-card, .card, div[role="radio"], div');
      const searchCard = cards.find(c => c.innerText && c.innerText.includes('חיפוש') && c.innerText.includes('מודעות טקסט'));
      if (searchCard) searchCard.click();
    });

    await page.waitForTimeout(2000);

    console.log('Step 4: Checking "ביקורים באתר" and entering landing page URL...');
    await page.evaluate(() => {
      function queryAll(sel, root = document) {
        let res = Array.from(root.querySelectorAll(sel));
        root.querySelectorAll('*').forEach(el => { if (el.shadowRoot) res.push(...queryAll(sel, el.shadowRoot)); });
        return res;
      }
      const checkboxes = queryAll('input[type="checkbox"], [role="checkbox"]');
      if (checkboxes.length > 0) checkboxes[0].click();

      const urlInputs = queryAll('input[type="url"], input[type="text"], input');
      if (urlInputs.length > 0) {
        const input = urlInputs[urlInputs.length - 1];
        input.value = 'https://kesher.saharoni.com/couples-counseling-ashdod';
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
      }
    });

    await page.waitForTimeout(2000);

    console.log('Step 5: Clicking "המשך" (Continue)...');
    await page.evaluate(() => {
      function queryAll(sel, root = document) {
        let res = Array.from(root.querySelectorAll(sel));
        root.querySelectorAll('*').forEach(el => { if (el.shadowRoot) res.push(...queryAll(sel, el.shadowRoot)); });
        return res;
      }
      const btns = queryAll('material-button.continue-button, button, div[role="button"]');
      const btn = btns.find(b => b.innerText && b.innerText.trim() === 'המשך');
      if (btn) btn.click();
    });

    await page.waitForTimeout(3000);

    console.log('Step 6: Populating Keywords, Headlines, and Descriptions...');
    await page.evaluate(() => {
      function queryAll(sel, root = document) {
        let res = Array.from(root.querySelectorAll(sel));
        root.querySelectorAll('*').forEach(el => { if (el.shadowRoot) res.push(...queryAll(sel, el.shadowRoot)); });
        return res;
      }

      // Enter keywords into textarea / keyword box
      const textareas = queryAll('textarea');
      if (textareas.length > 0) {
        textareas[0].value = 'ייעוץ זוגי באשדוד\nטיפול זוגי באשדוד\nיועץ זוגי באשדוד\nייעוץ נישואין באשדוד';
        textareas[0].dispatchEvent(new Event('input', { bubbles: true }));
        textareas[0].dispatchEvent(new Event('change', { bubbles: true }));
      }

      // Fill headlines
      const headlines = ['ייעוץ זוגי מקצועי באשדוד', 'בניית שיחה רגועה וברורה', 'קליניקה פרטית באשדוד'];
      const inputs = queryAll('input[type="text"], input:not([type])');
      headlines.forEach((h, idx) => {
        if (inputs[idx]) {
          inputs[idx].value = h;
          inputs[idx].dispatchEvent(new Event('input', { bubbles: true }));
          inputs[idx].dispatchEvent(new Event('change', { bubbles: true }));
        }
      });
    });

    console.log('Campaign Wizard automation completed successfully!');

  } catch (err) {
    console.error('Wizard Automation Error:', err);
  }
}

main();
