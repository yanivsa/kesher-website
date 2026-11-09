import posts from './posts.json';
import recentPosts from './postsRecent.json';
import giftedParentPosts from './giftedParentPosts.json';
import giftedParentPostsWave2 from './giftedParentPostsWave2.json';
import giftedParentOverrides from './giftedParentOverrides.json';
import giftedParentWave2Overrides from './giftedParentWave2Overrides.json';
import manualPostsOct2026 from './manualPostsOct2026';
import { applyInternalLinkBackfill } from './internalLinkBackfill';

type BasePost = (typeof posts)[number];

const topicPosts: BasePost[] = [
  ...(giftedParentPosts as unknown as BasePost[]),
  ...(giftedParentPostsWave2 as unknown as BasePost[]),
];
const manualPosts = manualPostsOct2026 as unknown as BasePost[];
const topicOverrides = giftedParentOverrides as unknown as Record<string, Partial<BasePost>>;
const wave2TopicOverrides = giftedParentWave2Overrides as unknown as Record<string, Partial<BasePost>>;

const applyTopicOverride = (post: BasePost): BasePost => {
  const override: Partial<BasePost> = topicOverrides[post.id] ?? {};
  const wave2Override: Partial<BasePost> = wave2TopicOverrides[post.id] ?? {};
  return Object.assign({}, post, override, wave2Override) as BasePost;
};

const allPosts: BasePost[] = [
  ...manualPosts,
  ...topicPosts,
  ...(recentPosts as unknown as BasePost[]),
  ...(posts as unknown as BasePost[]),
]
  .map(applyTopicOverride)
  .map(applyInternalLinkBackfill) as unknown as BasePost[];

const wordCount = (html: string) =>
  html.replace(/<[^>]+>/g, ' ').trim().split(/\s+/).filter(Boolean).length;

export const isPublishablePost = (post: BasePost) =>
  wordCount(post.content) >= 500 &&
  (post.content.match(/<h3/g) || []).length >= 5;

const publishedPosts = allPosts.filter(isPublishablePost);

export default publishedPosts;
