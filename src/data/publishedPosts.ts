import posts from './posts.json';
import recentPosts from './postsRecent.json';
import giftedParentPosts from './giftedParentPosts.json';
import giftedPostOverrides from './giftedPostOverrides.json';
import { applyInternalLinkBackfill } from './internalLinkBackfill';

type Post = (typeof posts)[number];
const overrideById = giftedPostOverrides as Record<string, Partial<Post>>;
const giftedCatalog = giftedParentPosts as Post[];

const allPosts = [...recentPosts, ...giftedCatalog, ...posts]
  .map((post) => ({ ...post, ...(overrideById[post.id] || {}) } as Post))
  .map(applyInternalLinkBackfill) as typeof posts;

const wordCount = (html: string) =>
  html.replace(/<[^>]+>/g, ' ').trim().split(/\s+/).filter(Boolean).length;

export const isPublishablePost = (post: (typeof posts)[number]) =>
  wordCount(post.content) >= 500 &&
  (post.content.match(/<h3/g) || []).length >= 5;

const publishedPosts = allPosts.filter(isPublishablePost);

export default publishedPosts;
