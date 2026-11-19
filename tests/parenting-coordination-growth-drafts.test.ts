import { describe, expect, it } from 'vitest';
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

import published from '../src/data/parentingCoordinationPosts.json';
import summaries from '../src/data/postSummaries.json';
import { PARENTING_COORDINATION_ARTICLE_IDS, isParentingCoordinationPath } from '../src/lib/parentingCoordination';

type EditorialDraft = {
  id: string;
  title: string;
  excerpt: string;
  directAnswer: string;
  primaryQuery: string;
  searchIntent: string;
  content: string;
  publicationState: string;
  date: string | null;
  updatedAt: string | null;
  image: string | null;
  imageAlt: string | null;
  category: string;
  relatedPostIds: string[];
  evidence: { title: string; url: string }[];
  serviceUrl: string;
};

const draftRoot = join(process.cwd(), 'src/data/parentingCoordinationDrafts');
const draftPaths = readdirSync(draftRoot).filter(name => name.endsWith('.json')).sort();
const drafts: EditorialDraft[] = draftPaths.map(filename =>
  JSON.parse(readFileSync(join(draftRoot, filename), 'utf8')) as EditorialDraft,
);
const publishedIds = new Set(published.map(post => post.id));
const summaryIds = new Set(summaries.map(post => post.id));
const baseUrls = new Set([
  '/services/parenting-coordination',
  '/parenting-guidance-divorce',
  ...published.map(post => '/blog/' + post.id),
]);

describe('unpublished parenting coordination editorial growth pack', () => {
  it('contains four researched distinct drafts, outside all public catalogs and sitemap inputs', () => {
    expect(drafts).toHaveLength(4);
    expect(new Set(drafts.map(d => d.id)).size).toBe(4);
    expect(new Set(drafts.map(d => d.primaryQuery)).size).toBe(4);
    for (const draft of drafts) {
      expect(publishedIds.has(draft.id), draft.id).toBe(false);
      expect(summaryIds.has(draft.id), draft.id).toBe(false);
      expect(PARENTING_COORDINATION_ARTICLE_IDS).not.toContain(draft.id);
      expect(isParentingCoordinationPath('/blog/' + draft.id)).toBe(false);
      expect(draft.publicationState).toBe('editorial_draft_unpublished');
      expect(draft.date).toBeNull();
      expect(draft.updatedAt).toBeNull();
      expect(draft.image).toBeNull();
      expect(draft.imageAlt).toBeNull();
      expect(draft.category).toBe('תיאום הורי');
    }
  });

  it.each(drafts)('$id meets minimum originality, source, linking and safety QA before editorial approval', draft => {
    expect(draft.id).toMatch(/^[a-z0-9-]+$/);
    expect(draft.title.length).toBeGreaterThan(30);
    expect(draft.title.length).toBeLessThan(95);
    expect(draft.excerpt.length).toBeGreaterThan(85);
    expect(draft.directAnswer.length).toBeGreaterThan(75);
    expect(draft.directAnswer.length).toBeLessThanOrEqual(350);
    expect(draft.serviceUrl).toBe('/services/parenting-coordination');
    const body = draft.content.replace(/<[^>]*>/g, ' ').replace(/&[^;]+;/g, ' ');
    expect(body.trim().split(/\s+/).length).toBeGreaterThanOrEqual(850);
    expect((draft.content.match(/<h3>/g) || []).length).toBeGreaterThanOrEqual(8);
    expect(draft.content).toMatch(/בטיחות|אלימות|סיכון|פגיעה/);
    expect(draft.content).not.toMatch(/100%|הצלחה מובטחת|מתאמת הורית מוסמכת|ממונה מטעם בית משפט/);
    expect(draft.content).not.toMatch(/<script|<iframe|<form|<style/i);
    expect(draft.content).not.toMatch(/href="https?:/);
    expect(draft.relatedPostIds.length).toBeGreaterThanOrEqual(2);
    for (const relatedId of draft.relatedPostIds) {
      expect(publishedIds.has(relatedId), relatedId).toBe(true);
    }
    for (const href of draft.content.matchAll(/href="(\/[^"]+)"/g)) {
      expect(baseUrls.has(href[1]), draft.id + ' broken internal link ' + href[1]).toBe(true);
    }
    expect(draft.evidence.length).toBeGreaterThanOrEqual(2);
    for (const source of draft.evidence) {
      expect(source.url).toMatch(/^https:\/\//);
      expect(source.title.length).toBeGreaterThan(15);
    }
  });

  it('keeps article bodies out of shared navigation chunks and generates routes from the published catalog', () => {
    const intakeSource = readFileSync('src/lib/parentingCoordination.ts', 'utf8');
    const generatorSource = readFileSync('scripts/generate-post-summaries.cjs', 'utf8');
    expect(intakeSource).toContain('parentingCoordinationArticleIds.json');
    expect(intakeSource).not.toContain('parentingCoordinationPosts.json');
    expect(generatorSource).toContain("post.category === 'תיאום הורי'");
    expect(generatorSource).toContain('parentingCoordinationArticleIds.json');
  });

  it('the source of truth automatically covers every future published coordination URL', () => {
    expect([...PARENTING_COORDINATION_ARTICLE_IDS].sort()).toEqual([...publishedIds].sort());
    for (const id of publishedIds) {
      expect(isParentingCoordinationPath('/blog/' + id)).toBe(true);
      expect(isParentingCoordinationPath('/blog/' + id + '/')).toBe(true);
    }
  });
});
