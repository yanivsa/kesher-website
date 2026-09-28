const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();

  const routes = [
    '/',
    '/services/couples',
    '/services/parenting',
    '/blog',
    '/faq',
    '/contact'
  ];
  const viewports = [360, 390, 430];

  for (const route of routes) {
    console.log(`\nChecking route: ${route}`);
    for (const width of viewports) {
      const context = await browser.newContext({ viewport: { width, height: 800 } });
      const page = await context.newPage();
      await page.goto(`http://localhost:4173${route}`, { waitUntil: 'networkidle' });

      const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
      const viewportWidth = width;

      if (scrollWidth > viewportWidth) {
        console.log(`[!] OVERFLOW DETECTED on ${route} at ${width}px (scrollWidth: ${scrollWidth})`);

        // Find elements causing overflow
        const overflowElements = await page.evaluate((viewportWidth) => {
          const elements = document.querySelectorAll('*');
          const overflowing = [];
          for (let i = 0; i < elements.length; i++) {
            const rect = elements[i].getBoundingClientRect();
            if (rect.right > viewportWidth || rect.width > viewportWidth) {
              const className = elements[i].className;
              const tagName = elements[i].tagName;
              // ignore scripts, styles, etc.
              if (['SCRIPT', 'STYLE', 'HTML', 'BODY'].includes(tagName)) continue;
              overflowing.push(`<${tagName.toLowerCase()} class="${typeof className === 'string' ? className : ''}"> (right: ${rect.right}, width: ${rect.width})`);
            }
          }
          return overflowing;
        }, viewportWidth);

        if (overflowElements.length > 0) {
          console.log(`    Elements causing overflow (sample):`);
          overflowElements.slice(0, 5).forEach(el => console.log(`      ${el}`));
        }
      } else {
        console.log(`[OK] No overflow on ${route} at ${width}px (scrollWidth: ${scrollWidth})`);
      }
      await context.close();
    }
  }

  await browser.close();
})();
