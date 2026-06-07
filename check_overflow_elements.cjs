const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();

  const routes = [
    '/',
    '/services/couples',
    '/services/parenting',
    '/services/mediation',
    '/blog',
    '/faq',
    '/contact'
  ];

  const width = 360;

  for (const route of routes) {
    await page.setViewportSize({ width, height: 800 });
    await page.goto(`http://localhost:5173${route}`);
    await page.waitForTimeout(500); // wait for render

    const overflowingElements = await page.evaluate(() => {
      const elements = document.querySelectorAll('*');
      const width = document.documentElement.clientWidth;
      const issues = [];

      elements.forEach(el => {
        const rect = el.getBoundingClientRect();
        // Check if the element extends beyond the left or right edge of the viewport
        if (rect.right > width + 1 || rect.left < -1) {
          // Ignore script, style, meta, etc.
          if (['SCRIPT', 'STYLE', 'META', 'HEAD', 'TITLE'].includes(el.tagName)) return;
          // Ignore zero-width elements or elements that aren't visible
          if (rect.width === 0 || el.style.display === 'none') return;

          issues.push({
            tag: el.tagName,
            className: el.className,
            left: rect.left,
            right: rect.right,
            width: rect.width,
            viewportWidth: width
          });
        }
      });
      return issues;
    });

    if (overflowingElements.length > 0) {
      console.log(`[OVERFLOW ELEMENTS] Route: ${route}`);
      // Filter to just the unique wide elements
      const maxRight = Math.max(...overflowingElements.map(e => e.right));
      console.log(`Max right bounds: ${maxRight}`);
      console.log(overflowingElements.slice(0, 3)); // show first few
    } else {
      console.log(`[OK] Route: ${route}`);
    }
  }

  await browser.close();
  process.exit(0);
})();
