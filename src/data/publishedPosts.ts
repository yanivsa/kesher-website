import posts from './posts.json';
import recentPosts from './postsRecent.json';
import giftedEditorialEnhancements from './giftedEditorialEnhancements.json';
import { applyInternalLinkBackfill } from './internalLinkBackfill';

type EditorialEnhancement = {
  updatedAt?: string;
  appendContent?: string;
};

const editorialEnhancements = giftedEditorialEnhancements as Record<string, EditorialEnhancement>;

const applyEditorialEnhancement = <T extends { id: string; content: string; updatedAt?: string }>(post: T): T => {
  const enhancement = editorialEnhancements[post.id];
  if (!enhancement) return post;

  return {
    ...post,
    content: `${post.content}${enhancement.appendContent ?? ''}`,
    updatedAt: enhancement.updatedAt ?? post.updatedAt,
  };
};

const allPosts = [...recentPosts, ...posts]
  .map((post) => applyEditorialEnhancement(post))
  .map(applyInternalLinkBackfill) as typeof posts;

const wordCount = (html: string) =>
  html.replace(/<[^>]+>/g, ' ').trim().split(/\s+/).filter(Boolean).length;

export const isPublishablePost = (post: (typeof posts)[number]) =>
  wordCount(post.content) >= 500 &&
  (post.content.match(/<h3/g) || []).length >= 5;

const publishedPosts = allPosts.filter(isPublishablePost);

export default publishedPosts;
