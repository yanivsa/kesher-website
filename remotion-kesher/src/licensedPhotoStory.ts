/**
 * Opt-in, source-bound photographic story for KESHER Overview.
 * Asset and legal evidence are prerequisites, not an automatic rights approval.
 * The canonical OWNER media quality gate still requires actual editorial review.
 */
export type LicensedPhotoScene = {
  assetPath: string;
  assetSha256: string;
  licenseEvidenceUrl: string;
  altHebrew: string;
  startFrame: number;
  endFrame: number;
};

export type LicensedPhotoStory = {
  sourceSlug: string;
  contentSha256: string;
  scenes: LicensedPhotoScene[];
};

export type ApprovedSourceIdentity = {
  slug: string;
  contentSha256: string;
};

const HEX_64 = /^[a-f0-9]{64}$/;
const SAFE_LOCAL_IMAGE = /^images\/(?:blog|generated\/blog)\/[a-z0-9][a-z0-9-]*\.(?:jpg|jpeg|png|webp)$/;
const HEBREW = /[\u0590-\u05ff]/;

/**
 * A cinematic path may be selected ONLY with 3+ distinct, existing, locally
 * committed source-bound photos. In particular, do not turn a single hero
 * photo into a 110-second pseudo-cinematic video and call it QA_PASSED.
 */
export function validateLicensedPhotoStory(
  story: LicensedPhotoStory,
  source: ApprovedSourceIdentity | undefined,
  durationInFrames: number,
  fps: number,
): void {
  if (!source || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(source.slug) ||
      !HEX_64.test(source.contentSha256) ||
      story.sourceSlug !== source.slug ||
      story.contentSha256 !== source.contentSha256) {
    throw new Error('PHOTO_STORY_SOURCE_IDENTITY_MISMATCH');
  }
  if (!Number.isInteger(durationInFrames) || durationInFrames <= 0 ||
      !Number.isInteger(fps) || fps <= 0 ||
      !Array.isArray(story.scenes) ||
      story.scenes.length < 3 || story.scenes.length > 12) {
    throw new Error('PHOTO_STORY_INCOMPLETE_VISUAL_PLAN');
  }
  let expectedStart = 0;
  const assets = new Set<string>();
  for (const scene of story.scenes) {
    if (!SAFE_LOCAL_IMAGE.test(scene.assetPath) ||
        !HEX_64.test(scene.assetSha256) ||
        !/^https:\/\/[^\s/?#]+\.[^\s]+/.test(scene.licenseEvidenceUrl) ||
        !HEBREW.test(scene.altHebrew)) {
      throw new Error('PHOTO_STORY_MISSING_IMAGE_OR_LICENSE_PROVENANCE');
    }
    if (assets.has(scene.assetPath)) {
      throw new Error('PHOTO_STORY_DUPLICATE_IMAGE');
    }
    assets.add(scene.assetPath);
    if (!Number.isInteger(scene.startFrame) ||
        !Number.isInteger(scene.endFrame) ||
        scene.startFrame !== expectedStart ||
        scene.endFrame - scene.startFrame < fps * 4 ||
        scene.endFrame > durationInFrames) {
      throw new Error('PHOTO_STORY_TIMELINE_GAP_OR_BAD_DURATION');
    }
    expectedStart = scene.endFrame;
  }
  if (expectedStart !== durationInFrames) {
    throw new Error('PHOTO_STORY_INCOMPLETE_TIMELINE');
  }
}
