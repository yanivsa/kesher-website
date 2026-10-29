import posts from './posts.json';
import recentPosts from './postsRecent.json';
import giftedParentPosts from './giftedParentPosts.json';
import giftedParentPostsWave2 from './giftedParentPostsWave2.json';
import giftedParentOverrides from './giftedParentOverrides.json';
import giftedParentWave2Overrides from './giftedParentWave2Overrides.json';
import manualPostsOct2026 from './manualPostsOct2026';
import { applyInternalLinkBackfill } from './internalLinkBackfill';

type BasePost = (typeof posts)[number];
type PostOverride = Record<string, unknown>;

const topicPosts = [
  ...(giftedParentPosts as unknown as BasePost[]),
  ...(giftedParentPostsWave2 as unknown as BasePost[]),
];
const manualPosts = manualPostsOct2026 as unknown as BasePost[];
const topicOverrides = giftedParentOverrides as unknown as Record<string, PostOverride>;
const wave2TopicOverrides = giftedParentWave2Overrides as unknown as Record<string, PostOverride>;

const applyTopicOverride = (post: BasePost): BasePost => {
  const override = topicOverrides[post.id];
  const wave2Override = wave2TopicOverrides[post.id];
  return Object.assign(
    {},
    post as unknown as Record<string, unknown>,
    override ?? {},
    wave2Override ?? {},
  ) as unknown as BasePost;
};

const allPosts = [
  ...manualPosts,
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