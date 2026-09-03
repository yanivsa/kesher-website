import { test, expect } from '@playwright/test';

const title = 'רשימת הדרישות והמציאות';

test.describe('Article image rendering', () => {
  test('detail renders image markup and Article schema image', async ({ page }) => {
    await page.goto('/blog/dating-second-chance-criteria');

    const article = page.locator('article', { has: page.locator('h1', { hasText: title }) });
    await expect(article).toHaveCount(1);
    await expect(article.locator('img[src^="/images/"]')).toHaveCount(1);

    const schemas = await page.locator('script[type="application/ld+json"]').allTextContents();
    const nodes = schemas.flatMap((content) => {
      const schema = JSON.parse(content);
      return Array.isArray(schema?.['@graph']) ? schema['@graph'] : [schema];
    });
    const articleSchema = nodes.find((node: Record<string, unknown>) =>
      node['@type'] === 'Article' && String(node.headline || '').includes(title)
    );
    expect(articleSchema).toBeDefined();
    expect(articleSchema).toHaveProperty('image');
  });

  test('blog list renders the card image', async ({ page }) => {
    await page.goto('/blog');
    const article = page.locator('article', { has: page.locator('h2', { hasText: title }) });
    await expect(article).toHaveCount(1);
    await expect(article.locator('img')).toHaveCount(1);
  });
});
