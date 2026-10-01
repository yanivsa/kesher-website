import { LandingTarget } from '../components/LandingCalloutBanner/LandingCalloutBanner';

export const ADHD_LANDING_POST_SLUGS = new Set([
  'adhd-morning-conflict-dopamine-myth',
  'adhd-morning-routine',
  'adhd-and-screen-addiction-strategies',
  'adhd-first-grade-preparation',
  'smart-youth-focus-tasks-organization',
  'couples-adhd-partner',
]);

export const CRISIS_LANDING_POST_SLUGS = new Set([
  'relationship-crisis-flydubai-lessons',
  'breaking-silent-treatment-relationship',
  'marriage-after-trust-leak',
  'communication-breakdown',
  'repairing-relationship-after-resentment',
  'relationship-after-childbirth',
  'stop-keeping-score-relationship',
  'gottman-perpetual-problems-69-percent',
  'couples-communication-distance',
  'newlywed-first-year-conflicts',
]);

export interface PostLike {
  id: string;
  title?: string;
  category?: string;
  subcategory?: string;
  tags?: string[];
  excerpt?: string;
}

/**
 * Opt-in mapping of blog posts to high-intent conversion landing banners.
 * Returns null by default so general informational posts do NOT receive an irrelevant banner.
 */
export const getLandingTargetForPost = (post: PostLike | null | undefined): LandingTarget | null => {
  if (!post || !post.id) {
    return null;
  }

  if (ADHD_LANDING_POST_SLUGS.has(post.id)) {
    return 'parenting_adhd';
  }

  if (CRISIS_LANDING_POST_SLUGS.has(post.id)) {
    return 'couples_crisis';
  }

  return null;
};
