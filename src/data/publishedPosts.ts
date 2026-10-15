import posts from './posts.json';
import recentPosts from './postsRecent.json';
import seoQueryEnhancements from './seoQueryEnhancements.json';

type BasePost = (typeof posts)[number];
type SeoOverride = Partial<BasePost> & {
  contentPrefix?: string;
  contentSuffix?: string;
  [key: string]: unknown;
};

const basePosts = [...recentPosts, ...posts] as typeof posts;
const overrides = seoQueryEnhancements.overrides as Record<string, SeoOverride>;
const additionalPosts = seoQueryEnhancements.additionalPosts as unknown as typeof posts;

const applySeoEnhancement = (post: BasePost): BasePost => {
  const override = overrides[post.id];
  if (!override) return post;

  const {
    contentPrefix = '',
    contentSuffix = '',
    ...fields
  } = override;
  const content = [contentPrefix, post.content, contentSuffix]
    .filter((part): part is string => typeof part === 'string' && part.trim().length > 0)
    .join('\n');

  return {
    ...post,
    ...fields,
    content,
  } as BasePost;
};

const enhancedPosts = basePosts.map(applySeoEnhancement);
const existingIds = new Set(enhancedPosts.map((post) => post.id));
const additions = additionalPosts.filter((post) => !existingIds.has(post.id));
const allPosts = [...additions, ...enhancedPosts] as typeof posts;

const wordCount = (html: string) =>
  html.replace(/<[^>]+>/g, ' ').trim().split(/\s+/).filter(Boolean).length;

export const isPublishablePost = (post: (typeof posts)[number]) =>
  wordCount(post.content) >= 500 &&
  (post.content.match(/<h3/g) || []).length >= 5;

const publishedPosts = allPosts.filter(isPublishablePost);

export default publishedPosts;
