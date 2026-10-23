import posts from './posts.json';
import recentPosts from './postsRecent.json';
import giftedParentPosts from './giftedParentPosts.json';
import giftedParentPostsWave2 from './giftedParentPostsWave2.json';
import giftedParentOverrides from './giftedParentOverrides.json';
import { applyInternalLinkBackfill } from './internalLinkBackfill';

type BasePost = (typeof posts)[number];

const topicPosts = [
  ...(giftedParentPosts as unknown as BasePost[]),
  ...(giftedParentPostsWave2 as unknown as BasePost[]),
];
const topicOverrides = giftedParentOverrides as unknown as Record<string, Partial<BasePost>>;

const applyTopicOverride = (post: BasePost): BasePost => {
  const override = topicOverrides[post.id];
  return override ? ({ ...post, ...override } as BasePost) : post;
};

const allPosts = [
  ...topicPosts,
  ...(recentPosts as unknown as BasePost[]),
  ...posts,
]
  .map(applyTopicOverride)
  .map(applyInternalLinkBackfill) as typeof posts;

const wordCount = (html: string) =>
  html.replace(/<[^>]+>/g, ' ').trim().split(/\s+/).filter(Boolean).length;

export const isPublishablePost = (post: (typeof posts)[number]) =>
  wordCount(post.content) >= 500 &&
  (post.content.match(/<h3/g) || []).length >= 5;

const publishedPosts = allPosts.filter(isPublishablePost);

export default publishedPosts;
