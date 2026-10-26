import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';

const require = createRequire(import.meta.url);
const { loadPosts } = require('../scripts/load-posts.cjs');

const TARGET_IDS = [
  'gifted-test-first-emotional-preparation-parents',
  'child-not-selected-gifted-program-parent-response',
  'after-gifted-identification-next-steps-family',
  'how-to-talk-to-child-about-being-gifted',
  'gifted-child-pressure-to-achieve-parent-guide',
  'gifted-child-bored-at-school-parent-guide',
  'gifted-child-emotional-sensitivity-myths',
  'child-argues-every-request-boundaries',
  'child-meltdown-after-school',
  'prepare-for-first-grade',
  'first-grade-readiness',
  'potty-training-age-3-problems',
  'nighttime-potty-training',
  'potty-training-regression',
  'child-refuses-homework',
  'premarital-counseling-divorced-parents',
] as const;

describe('legacy article exact-source hero contract', () => {
  it('gives every legacy target a distinct generated blog hero with descriptive Hebrew alt text', () => {
    const posts = loadPosts();
    const selected = TARGET_IDS.map((id) => posts.find((post: { id: string }) => post.id === id));

    for (const [index, post] of selected.entries()) {
      expect(post, TARGET_IDS[index]).toBeTruthy();
      expect(post.image, TARGET_IDS[index]).toMatch(/^\/images\/generated\/blog\/[A-Za-z0-9._-]+\.(?:png|jpe?g|webp)$/i);
      expect(String(post.imageAlt || '').trim().length, TARGET_IDS[index]).toBeGreaterThanOrEqual(20);
      expect(/[\u0590-\u05FF]/.test(String(post.imageAlt || '')), TARGET_IDS[index]).toBe(true);
      expect(fs.existsSync(path.join(process.cwd(), 'public', post.image.replace(/^\//, ''))), TARGET_IDS[index]).toBe(true);
    }

    const images = selected.map((post) => post.image);
    expect(new Set(images).size).toBe(TARGET_IDS.length);
  });
});
