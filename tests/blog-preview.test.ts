import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import BlogPreview from '../src/pages/Home/BlogPreview';

describe('BlogPreview image-less fallback', () => {
  it('renders the current image-less post without an img element', () => {
    const html = renderToStaticMarkup(
      createElement(MemoryRouter, null, createElement(BlogPreview)),
    );
    const title = 'הדייט מרגיש כמו ראיון עבודה? איך לצאת מחקירות ולייצר היכרות אמיתית';
    const titleIndex = html.indexOf(title);
    expect(titleIndex).toBeGreaterThan(-1);

    const articleStart = html.lastIndexOf('<article', titleIndex);
    const articleEnd = html.indexOf('</article>', titleIndex);
    expect(articleStart).toBeGreaterThan(-1);
    expect(articleEnd).toBeGreaterThan(titleIndex);
    expect(html.slice(articleStart, articleEnd)).not.toContain('<img');
  });
});
