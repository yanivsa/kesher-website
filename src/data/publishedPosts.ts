import posts from './posts.json';
import recentPosts from './postsRecent.json';
import giftedEditorialEnhancements from './giftedEditorialEnhancements.json';
import { applyInternalLinkBackfill } from './internalLinkBackfill';

type Post = (typeof posts)[number];
type EditorialEnhancement = {
  updatedAt?: string;
  appendContent?: string;
};

const editorialEnhancements = giftedEditorialEnhancements as Record<string, EditorialEnhancement>;

const applyEditorialEnhancement = (post: Post): Post => {
  const enhancement = editorialEnhancements[post.id];
  if (!enhancement) return post;

  return {
    ...post,
    content: `${post.content}${enhancement.appendContent ?? ''}`,
    updatedAt: enhancement.updatedAt ?? post.updatedAt,
  };
};

const combinedPosts = [...recentPosts, ...posts] as typeof posts;
const allPosts = combinedPosts
  .map(applyEditorialEnhancement)
  .map(applyInternalLinkBackfill) as typeof posts;

const wordCount = (html: string) =>
  html.replace(/<[^>]+>/g, ' ').trim().split(/\s+/).filter(Boolean).length;

export const isPublishablePost = (post: Post) =>
  wordCount(post.content) >= 500 &&
  (post.content.match(/<h3/g) || []).length >= 5;

const publishedPosts = allPosts.filter(isPublishablePost);

export default publishedPosts;
