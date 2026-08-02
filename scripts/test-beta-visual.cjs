/* global window */
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.setViewportSize({ width: 1440, height: 900 });

  const screenshotDir = path.join(__dirname, '../design-previews/scrollytelling-checks');
  fs.mkdirSync(screenshotDir, { recursive: true });

  console.log('Navigating to https://kesher.saharoni.com/beta...');
  await page.goto('https://kesher.saharoni.com/beta', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(screenshotDir, '01_top_hero.png') });

  // Scroll function helper
  const scrollTo = async (y) => {
    await page.evaluate((targetY) => {
      window.scrollTo(0, targetY);
      window.dispatchEvent(new Event('scroll'));
    }, y);
    await page.waitForTimeout(600);
  };

  // Scroll down to Scene 1 beats
  await scrollTo(500);
  await page.screenshot({ path: path.join(screenshotDir, '02_scene1.png') });

  // Scroll down to Scene 2 (Threat beat)
  await scrollTo(2400);
  await page.screenshot({ path: path.join(screenshotDir, '03_scene2_threat.png') });

  // Scroll down to Scene 2 Brand Reveal
  await scrollTo(3600);
  await page.screenshot({ path: path.join(screenshotDir, '04_scene2_brand_reveal.png') });

  // Scroll down to Scene 3
  await scrollTo(4800);
  await page.screenshot({ path: path.join(screenshotDir, '05_scene3.png') });

  // Scroll down to Part 2 Standard Marketing Page
  await scrollTo(6800);
  await page.screenshot({ path: path.join(screenshotDir, '06_part2_standard_hero.png') });

  console.log('Screenshots saved successfully!');
  await browser.close();
})();
