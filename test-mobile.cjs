const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 } // Mobile width
  });

  const page = await context.newPage();
  const routes = [
    '/',
    '/services/couples',
    '/services/parenting',
    '/services/mediation',
    '/blog',
    '/faq',
    '/contact'
  ];

  for (const route of routes) {
    const url = `http://localhost:4173${route}`;
    await page.goto(url);

    // Check horizontal overflow
    const hasOverflow = await page.evaluate(() => {
      const docWidth = document.documentElement.scrollWidth;
      const winWidth = window.innerWidth;
      return docWidth > winWidth;
    });

    console.log(`Route ${route}: ${hasOverflow ? 'HAS HORIZONTAL OVERFLOW' : 'OK'} (scrollWidth: ${await page.evaluate(() => document.documentElement.scrollWidth)}, innerWidth: ${await page.evaluate(() => window.innerWidth)})`);

    if (hasOverflow) {
        console.log(`Checking elements causing overflow on ${route}...`);
        const overflowElements = await page.evaluate(() => {
             const result = [];
             const elements = document.querySelectorAll('*');
             const docWidth = document.documentElement.scrollWidth;
             for (const el of elements) {
                 const rect = el.getBoundingClientRect();
                 if (rect.right > window.innerWidth || rect.left < 0) {
                     let identifier = el.tagName;
                     if (el.className && typeof el.className === 'string') {
                         identifier += '.' + el.className.split(' ').join('.');
                     }
                     if (el.id) {
                         identifier += '#' + el.id;
                     }
                     result.push({
                         identifier,
                         right: rect.right,
                         left: rect.left,
                         width: rect.width,
                         scrollWidth: el.scrollWidth,
                         outerHTML: el.outerHTML.substring(0, 100)
                     });
                 }
             }
             return result;
        });

        console.log(overflowElements.slice(0, 10)); // print top 10
    }
  }

  await browser.close();
})();
