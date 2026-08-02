import fs from "node:fs";
import path from "node:path";
import playwright from "playwright";

const { chromium } = playwright;
const notebookUrl = "https://notebooklm.google.com/notebook/e101e7d7-5305-45b3-a611-21a5475ceb63?hl=en";
const profileDir = "/Users/ninja/Library/Application Support/notebooklm-mcp/chrome_profile";

async function main() {
  const context = await chromium.launchPersistentContext(profileDir, {
    headless: true,
    acceptDownloads: true,
    viewport: { width: 1280, height: 900 },
  });
  const page = context.pages()[0] || (await context.newPage());
  try {
    await page.goto(notebookUrl, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(5000);

    // Find all menu buttons (three dots) in the Studio section
    const menuButtons = await page.locator('button:has-text("more_vert"), [aria-label*="More"], mat-icon:has-text("more_vert")').all();
    console.log(`Found ${menuButtons.length} menu buttons`);

    // Let's get parent text for each menu button
    const cardInfo = [];
    for (let i = 0; i < menuButtons.length; i++) {
      const btn = menuButtons[i];
      const info = await btn.evaluate((el) => {
        let parent = el.parentElement;
        while (parent && parent.textContent.trim().length < 10) {
          parent = parent.parentElement;
        }
        return parent ? parent.textContent.replace(/\s+/g, ' ').trim() : '';
      });
      cardInfo.push({ index: i, text: info });
    }
    console.log("Card Info:", JSON.stringify(cardInfo, null, 2));

    // Try clicking the first menu button
    if (menuButtons.length > 0) {
      await menuButtons[0].click();
      await page.waitForTimeout(1000);
      const menuItems = await page.locator('[role="menuitem"], button, a').evaluateAll((els) =>
        els.map((e) => ({ text: e.textContent.trim(), role: e.getAttribute('role'), aria: e.getAttribute('aria-label') }))
           .filter((e) => e.text.length > 0 && e.text.length < 50)
      );
      console.log("Menu items visible after click:", JSON.stringify(menuItems, null, 2));
    }
  } finally {
    await context.close();
  }
}

main().catch(console.error);
