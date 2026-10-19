import posts from './posts.json';
import recentPosts from './postsRecent.json';
import { applyInternalLinkBackfill } from './internalLinkBackfill';

const allPosts = [...recentPosts, ...posts].map(applyInternalLinkBackfill) as typeof posts;

const wordCount = (html: string) =>
  html.replace(/<[^>]+>/g, ' ').trim().split(/\s+/).filter(Boolean).length;

export const isPublishablePost = (post: (typeof posts)[number]) =>
  wordCount(post.content) >= 500 &&
  (post.content.match(/<h3/g) || []).length >= 5;

const publishedPosts = allPosts.filter(isPublishablePost);

export default publishedPosts;
