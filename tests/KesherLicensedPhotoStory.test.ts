import {describe, expect, it} from 'vitest';
import {readFileSync} from 'node:fs';
import {validateLicensedPhotoStory, type LicensedPhotoStory} from '../remotion-kesher/src/licensedPhotoStory';

const source = {
  slug: 'vantage-sensitivity-sensitive-gifted-children',
  contentSha256: 'e264d2962b9028afc73463edcd2718b37539212762b0a72e35507d33dcb270ea',
};

const photo = (i: number, startFrame: number, endFrame: number) => ({
  assetPath: `images/blog/kesher-parenting-scene-${i}.jpg`,
  assetSha256: String(i).repeat(64),
  licenseEvidenceUrl: 'https://kesher.saharoni.com/licensing/owned-photo-evidence',
  altHebrew: 'הורה מקשיב לילד בסביבה טבעית',
  startFrame,
  endFrame,
});

const good = (): LicensedPhotoStory => ({
  sourceSlug: source.slug,
  contentSha256: source.contentSha256,
  scenes: [photo(1, 0, 180), photo(2, 180, 360), photo(3, 360, 540)],
});

describe('licensed source-bound photographic Remotion Overview', () => {
  it('accepts full-length 3-scene plan with immutable source and provenance', () => {
    expect(() => validateLicensedPhotoStory(good(), source, 540, 30)).not.toThrow();
  });
  it('rejects a story for a different approved article', () => {
    expect(() => validateLicensedPhotoStory({...good(), contentSha256: 'a'.repeat(64)}, source, 540, 30))
      .toThrow('PHOTO_STORY_SOURCE_IDENTITY_MISMATCH');
  });
  it('rejects 1-photo pseudo-cinema instead of a real visual story', () => {
    const bad = good(); bad.scenes = [photo(1, 0, 540)];
    expect(() => validateLicensedPhotoStory(bad, source, 540, 30))
      .toThrow('PHOTO_STORY_INCOMPLETE_VISUAL_PLAN');
  });
  it('rejects duplicate images across time segments', () => {
    const bad = good(); bad.scenes[1].assetPath = bad.scenes[0].assetPath;
    expect(() => validateLicensedPhotoStory(bad, source, 540, 30))
      .toThrow('PHOTO_STORY_DUPLICATE_IMAGE');
  });
  it('rejects missing license evidence or asset hash', () => {
    const bad = good(); bad.scenes[0].licenseEvidenceUrl = '';
    expect(() => validateLicensedPhotoStory(bad, source, 540, 30))
      .toThrow('PHOTO_STORY_MISSING_IMAGE_OR_LICENSE_PROVENANCE');
  });
  it('rejects remote URLs and traversal in source assets', () => {
    const bad = good(); bad.scenes[0].assetPath = '../secrets/source.png';
    expect(() => validateLicensedPhotoStory(bad, source, 540, 30))
      .toThrow('PHOTO_STORY_MISSING_IMAGE_OR_LICENSE_PROVENANCE');
  });
  it('rejects missing ranges, overlaps and incomplete timeline coverage', () => {
    const bad = good(); bad.scenes[1].startFrame = 190;
    expect(() => validateLicensedPhotoStory(bad, source, 540, 30))
      .toThrow('PHOTO_STORY_TIMELINE_GAP_OR_BAD_DURATION');
    const short = good(); short.scenes[2].endFrame = 520;
    expect(() => validateLicensedPhotoStory(short, source, 540, 30))
      .toThrow('PHOTO_STORY_INCOMPLETE_TIMELINE');
  });
  it('rejects segments too short for a natural shot', () => {
    const bad = good(); bad.scenes[0].endFrame = 60;
    expect(() => validateLicensedPhotoStory(bad, source, 540, 30))
      .toThrow('PHOTO_STORY_TIMELINE_GAP_OR_BAD_DURATION');
  });
  it('preserves source video audio and never invokes a new uploader', () => {
    const code = readFileSync('remotion-kesher/src/KesherVideo.tsx', 'utf8');
    expect(code).toContain('<Video');
    expect(code).toContain('validateLicensedPhotoStory(');
    expect(code).toContain('licensedPhotoStory.scenes.map');
    expect(code).not.toMatch(/(?:youtube\.videos\.insert|upload_to_youtube|execSync|child_process)/);
  });
});
