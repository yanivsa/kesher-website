import { describe, expect, it } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import financialPosts from '../src/data/financialGuidancePosts.json';
import summaries from '../src/data/postSummaries.json';
import { internalLinkBackfillRules } from '../src/data/internalLinkBackfill';
import { resolveContactService, CONTACT_SERVICE_OPTIONS } from '../src/lib/contactServices';

const service = '/services/family-financial-guidance';
const category = '/blog/category/family-finances';
const legacyIds = [
  'money-fights-communication',
  'marriage-preparation-money-fights',
  'marriage-prep-financial-expectations-2026-08-24',
];
const known = new Set([...financialPosts.map(p => p.id), ...legacyIds]);
const root = process.cwd();

describe('family finance content publishing contract', () => {
  it('retains intent on contact and appointment routes without passing sensitive data', () => {
    expect(resolveContactService('family-financial-guidance')).toBe('family-financial-guidance');
    expect(CONTACT_SERVICE_OPTIONS.some(x => x.value === 'family-financial-guidance')).toBe(true);
    const booking = readFileSync(path.join(root,'src/pages/Appointment/AppointmentPage.tsx'),'utf8');
    expect(booking).toContain('family_financial_guidance');
    const landing = readFileSync(path.join(root,'src/pages/Landing/Financial/FinancialLandingPage.tsx'),'utf8');
    expect(landing).toContain('/appointment?service=family-financial-guidance');
    const contact = readFileSync(path.join(root,'src/pages/Home/ContactSection.tsx'),'utf8');
    expect(contact).toContain('ללא מספרים או נתונים פיננסיים רגישים');
  });
  it('ships 17 new original articles and retains 3 distinct legacy URLs', () => {
    expect(financialPosts).toHaveLength(17);
    expect(new Set(financialPosts.map(p => p.id)).size).toBe(17);
    expect(new Set(financialPosts.map(p => p.title)).size).toBe(17);
    for (const id of legacyIds) expect(summaries.find(s => s.id === id)).toBeTruthy();
  });

  it.each(financialPosts)('$id has long-form useful content, relevant CTA, and source context', post => {
    expect(post.category).toBe('כלכלת המשפחה');
    expect(post.id).toBe(post.slug);
    expect(post.title.length).toBeGreaterThan(25);
    expect(post.directAnswer.length).toBeGreaterThan(40);
    expect(post.content.match(/<h3\b/g)?.length ?? 0).toBeGreaterThanOrEqual(5);
    const wordCount = post.content.replace(/<[^>]+>/g, ' ').trim().split(/\s+/).length;
    expect(wordCount).toBeGreaterThanOrEqual(500);
    expect(post.content).toContain(service);
    expect(post.content).toContain(category);
    expect(post.content).toContain('pop.education.gov.il');
    expect(post.relatedPostIds.length).toBeGreaterThan(0);
    for (const id of post.relatedPostIds) expect(known.has(id)).toBe(true);
    expect(summaries.filter(s => s.id === post.id)).toHaveLength(1);
  });

  it('provides distinctive local illustrations and meaningful Hebrew alt descriptions', () => {
    const images = new Set<string>();
    const contents = new Set<string>();
    for (const post of financialPosts) {
      expect(post.image).toMatch(/^\/images\/financial-guidance\/articles\/[a-z0-9-]+\.svg$/);
      expect(post.imageAlt.length).toBeGreaterThan(30);
      expect(images.has(post.image)).toBe(false);
      images.add(post.image);
      const file = path.join(root, 'public', post.image.replace(/^\//, ''));
      expect(existsSync(file)).toBe(true);
      const svg = readFileSync(file, 'utf8');
      expect(svg).toContain('<svg');
      expect(contents.has(svg)).toBe(false);
      contents.add(svg);
    }
  });

  it('excludes PPC-only landings from XML sitemap and retains approved static routes', () => {
    const policy = readFileSync(path.join(root, 'scripts/content-policy.cjs'), 'utf8');
    const generator = readFileSync(path.join(root, 'scripts/generate-sitemap.cjs'), 'utf8');
    for (const route of [service,category,'/financial-guidance-couples','/family-budget-guidance']) {
      expect(policy).toContain(route);
    }
    expect(generator).toContain("'/financial-guidance-couples'");
    expect(generator).toContain("'/family-budget-guidance'");
    const landing = readFileSync(path.join(root, 'src/pages/Landing/Financial/FinancialLandingPage.tsx'), 'utf8');
    expect(landing).toContain('robots="noindex, follow"');
    expect(internalLinkBackfillRules).toBeDefined();
  });

  it('offers two usable local no-login tools with consistent formulas', () => {
    const worksheet = path.join(root,'public/downloads/financial/money-conversation-worksheet.html');
    const budget = path.join(root,'public/downloads/financial/family-budget-template.csv');
    expect(existsSync(worksheet)).toBe(true);
    const html = readFileSync(worksheet,'utf8');
    expect(html).toContain('Ctrl+P');
    expect(html).not.toContain('onclick=');
    expect(existsSync(budget)).toBe(true);
    const csv = readFileSync(budget,'utf8').replace(/^\uFEFF/,'');
    const rows = csv.trim().split('\n');
    expect(rows[0]).toBe('sep=;');
    expect(rows[14]).toContain('=SUM(C2:C4)');
    expect(rows[15]).toContain('=SUM(C5:C13)');
    expect(rows[16]).toContain('=C14-C15');
    expect(rows[16]).toContain('=D14-D15');
  });
});
