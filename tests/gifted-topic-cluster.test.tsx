import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import posts from '../src/data/posts.json';
import BlogPost from '../src/pages/Blog/BlogPost';

const pillar = posts.find((post) => post.id === 'how-to-identify-a-gifted-child-parents-guide');

describe('gifted-child SEO topic cluster', () => {
  it('targets the broad "מה זה ילד מחונן" search intent on the pillar page', () => {
    expect(pillar).toBeDefined();
    expect(pillar?.title).toContain('מה זה ילד מחונן');
    expect(`${pillar?.directAnswer ?? ''} ${pillar?.content ?? ''}`).toContain('מה זה ילד מחונן');
  });

  it('supports the pillar with authoritative evidence', () => {
    const evidence = pillar && 'evidence' in pillar && Array.isArray(pillar.evidence) ? pillar.evidence : [];
    const urls = evidence.map((item) => item.url).filter(Boolean).join(' ');

    expect(urls).toContain('nagc.org');
    expect(urls).toMatch(/education\.gov\.il|gov\.il/);
  });

  it('links from the pillar to distinct existing gifted-child subtopics', () => {
    const relatedPostIds = pillar && 'relatedPostIds' in pillar && Array.isArray(pillar.relatedPostIds)
      ? pillar.relatedPostIds
      : [];
    const supportingIds = [
      'gifted-children-social-difficulties',
      'child-starting-school-high-cognition',
      'gifted-children-perfectionism-tears',
      'gifted-adhd-executive-functions-struggle',
    ];

    for (const id of supportingIds) {
      expect(relatedPostIds).toContain(id);
      expect(posts.some((post) => post.id === id)).toBe(true);
    }
  });

  it('renders the gifted-child supporting articles as crawlable internal links', () => {
    render(
      <MemoryRouter initialEntries={['/blog/how-to-identify-a-gifted-child-parents-guide']}>
        <Routes>
          <Route path="/blog/:id" element={<BlogPost />} />
        </Routes>
      </MemoryRouter>,
    );

    const socialLink = screen.getByRole('link', { name: /ילדים מחוננים וקשיים חברתיים/ });
    expect(socialLink.getAttribute('href')).toBe('/blog/gifted-children-social-difficulties');
  });

  it('links a gifted-child supporting article back to the pillar page', () => {
    render(
      <MemoryRouter initialEntries={['/blog/gifted-children-social-difficulties']}>
        <Routes>
          <Route path="/blog/:id" element={<BlogPost />} />
        </Routes>
      </MemoryRouter>,
    );

    const pillarLink = screen.getByRole('link', { name: /מה זה ילד מחונן/ });
    expect(pillarLink.getAttribute('href')).toBe('/blog/how-to-identify-a-gifted-child-parents-guide');
  });
});
