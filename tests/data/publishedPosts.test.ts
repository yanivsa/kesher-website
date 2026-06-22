import { describe, expect, it } from 'vitest';
import { isPublishablePost } from '../../src/data/publishedPosts';
import posts from '../../src/data/posts.json';

type Post = (typeof posts)[number];

describe('isPublishablePost', () => {
  it('returns true for a post with at least 500 words and 5 h3 tags', () => {
    const validPost = {
      id: 'valid-post',
      title: 'Valid Post',
      date: '2026-06-01',
      category: 'Test',
      excerpt: 'Test',
      content: '<h3>Heading 1</h3>' + '<h3>Heading 2</h3>' + '<h3>Heading 3</h3>' + '<h3>Heading 4</h3>' + '<h3>Heading 5</h3>' + ' word'.repeat(500),
      image: '/images/test.jpg'
    } as Post;

    expect(isPublishablePost(validPost)).toBe(true);
  });

  it('returns false for a post with less than 500 words but at least 5 h3 tags', () => {
    const invalidPost = {
      // The word count function removes tags and counts words.
      // 5 headings with 2 words each = 10 words.
      // adding 489 'word's makes it 499 words.
      content: '<h3>Heading 1</h3>' + '<h3>Heading 2</h3>' + '<h3>Heading 3</h3>' + '<h3>Heading 4</h3>' + '<h3>Heading 5</h3>' + ' word'.repeat(489),
    } as Post;

    expect(isPublishablePost(invalidPost)).toBe(false);
  });

  it('returns false for a post with at least 500 words but less than 5 h3 tags', () => {
    const invalidPost = {
      content: '<h3>Heading 1</h3>' + '<h3>Heading 2</h3>' + '<h3>Heading 3</h3>' + '<h3>Heading 4</h3>' + ' word'.repeat(500),
    } as Post;

    expect(isPublishablePost(invalidPost)).toBe(false);
  });

  it('returns false for a post with empty content', () => {
    const invalidPost = {
      content: '',
    } as Post;

    expect(isPublishablePost(invalidPost)).toBe(false);
  });

  it('handles HTML tags correctly when counting words', () => {
    // 5 h3 tags (each with 1 word) + 495 words = 500 words
    const content = '<h3>H</h3><h3>H</h3><h3>H</h3><h3>H</h3><h3>H</h3>' + '<p>word</p>'.repeat(495);
    const validPost = { content } as Post;

    expect(isPublishablePost(validPost)).toBe(true);
  });
});
