import { expect, test } from '@playwright/test';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const { loadPosts } = require('../../scripts/load-posts.cjs') as {
  loadPosts: () => Array<{ id: string; title: string; excerpt: string; content: string }>;
};
const publishedPosts = loadPosts();

test('prerendered articles load exact content without React recovery errors', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.route('https://news.google.com/**', (route) => route.fulfill({ status: 200, body: '' }));
  await page.route('https://assets.calendly.com/**', (route) => route.fulfill({ status: 200, body: '' }));

  for (const id of ['sleep-needs-10-year-old', 'child-after-school-restraint-collapse']) {
    const post = publishedPosts.find((candidate) => candidate.id === id)!;
    await page.goto(`/blog/${id}`, { waitUntil: 'networkidle' });
    await expect(page.locator('h1')).toHaveText(post.title);
    await expect(page.locator('meta[name="description"]')).toHaveAttribute('content', post.excerpt);
    await expect(page.locator('[data-kesher-article-body]')).toBeVisible();
    const expectedBody = await page.evaluate((html) =>
      new DOMParser().parseFromString(html, 'text/html').body.textContent || '', post.content);
    const renderedBody = await page.locator('[data-kesher-article-body]').textContent();
    expect(renderedBody?.replace(/\s+/g, ' ').trim()).toBe(expectedBody.replace(/\s+/g, ' ').trim());
    expect(errors).toEqual([]);
  }
});
