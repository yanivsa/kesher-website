import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import NowPage from '../src/pages/Now/NowPage';

describe('NowPage rendering', () => {
  it('renders a personal current-focus page without a booking call to action', () => {
    const html = renderToStaticMarkup(
      createElement(MemoryRouter, null, createElement(NowPage)),
    );

    expect(html).toContain('מה מעסיק אותי עכשיו');
    expect(html).toContain('https://nownownow.com/about');
    expect(html).not.toContain('href="/appointment"');
  });
});
