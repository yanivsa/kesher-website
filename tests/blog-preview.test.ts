import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import BlogPreview from '../src/pages/Home/BlogPreview';

describe('BlogPreview rendering', () => {
  it('renders the latest blog posts cleanly with images', () => {
    const html = renderToStaticMarkup(
      createElement(MemoryRouter, null, createElement(BlogPreview)),
    );
    expect(html).toContain('<article');
    expect(html).toContain('<img');
  });
});
