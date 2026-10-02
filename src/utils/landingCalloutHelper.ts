import { LandingTarget } from '../components/LandingCalloutBanner/LandingCalloutBanner';

export const ADHD_LANDING_POST_SLUGS = new Set([
  'adhd-morning-conflict-dopamine-myth',
  'adhd-morning-routine',
  'adhd-first-grade-preparation',
  'smart-youth-focus-tasks-organization',
  'adhd-waiting-mode',
]);

export const CRISIS_LANDING_POST_SLUGS = new Set([
  'relationship-crisis-flydubai-lessons',
  'breaking-silent-treatment-relationship',
  'communication-breakdown',
  'relationship-after-childbirth',
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
 * Editorial opt-in mapping of blog posts to high-intent service callouts.
 * Returns null by default. A post is mapped only when its reader intent
 * strongly matches the destination service.
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
