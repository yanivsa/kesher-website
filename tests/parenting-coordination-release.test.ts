import { describe, expect, it } from 'vitest';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import posts from '../src/data/parentingCoordinationPosts.json';
import {
  isParentingCoordinationPath,
  PARENTING_COORDINATION_ARTICLE_IDS,
  PARENTING_COORDINATION_CONTACT_URL,
  PARENTING_COORDINATION_WHATSAPP_MESSAGE,
} from '../src/lib/parentingCoordination';
import { CONTACT_SERVICE_OPTIONS, resolveContactService } from '../src/lib/contactServices';

describe('Parenting coordination release regression checks', () => {
  it('executes the dedicated structural, editorial, source and asset contract', () => {
    const stdout = execFileSync(process.execPath, ['tests/parenting-coordination.test.cjs'], {
      cwd: process.cwd(),
      encoding: 'utf8',
    });
    expect(stdout).toContain('Parenting coordination service, editorial catalog, route and policy checks passed.');
  });

  it('maintains a complete and unique list of published topic articles for route-specific intake', () => {
    const actualIds = posts.map((post) => post.id).sort();
    expect([...PARENTING_COORDINATION_ARTICLE_IDS].sort()).toEqual(actualIds);
    expect(new Set(actualIds).size).toBe(5);
    expect(posts.every((post) => post.category === 'תיאום הורי')).toBe(true);
    expect(posts.every((post) => post.relatedPostIds.length >= 2)).toBe(true);
  });

  it('routes all specialty pages, including trailing slashes, into pre-screening', () => {
    const paths = [
      '/services/parenting-coordination',
      '/blog/category/parenting-coordination',
      ...PARENTING_COORDINATION_ARTICLE_IDS.map((id) => '/blog/' + id),
    ];
    for (const path of paths) {
      expect(isParentingCoordinationPath(path)).toBe(true);
      expect(isParentingCoordinationPath(path + '/')).toBe(true);
    }
    for (const path of ['/blog', '/blog/sleep-needs-10-year-old', '/services/parenting', '/services/mediation', '/appointment']) {
      expect(isParentingCoordinationPath(path)).toBe(false);
    }
  });

  it('uses a valid, privacy-conscious dedicated contact service', () => {
    expect(PARENTING_COORDINATION_CONTACT_URL).toBe('/contact?service=parenting_coordination');
    expect(resolveContactService('parenting_coordination')).toBe('parenting_coordination');
    expect(CONTACT_SERVICE_OPTIONS).toContainEqual({
      value: 'parenting_coordination',
      label: 'תיאום הורי — בירור התאמה',
    });
    expect(PARENTING_COORDINATION_WHATSAPP_MESSAGE).not.toMatch(/שם הילד|תעודת זהות|כתובת מגורים|אבחנה|הליך משפטי/);
  });

  it('keeps CTA routing and the privacy-sensitive form coupled to pre-screening', () => {
    const read = (path: string) => readFileSync(path, 'utf8');
    const article = read('src/pages/Blog/BlogPost.tsx');
    const sticky = read('src/components/Layout/MobileStickyBar.tsx');
    const header = read('src/components/Layout/Header.tsx');
    const footer = read('src/components/Layout/Footer.tsx');
    const floating = read('src/components/Layout/FloatingWhatsApp.tsx');
    const contact = read('src/pages/Home/ContactSection.tsx');
    expect(article).toContain('isCoordinationArticle ? PARENTING_COORDINATION_CONTACT_URL : SITE_CONFIG.links.appointment');
    expect(sticky).toContain('coordinationInquiry ? PARENTING_COORDINATION_CONTACT_URL : SITE_CONFIG.links.appointment');
    expect(header).toContain('coordinationInquiry ? PARENTING_COORDINATION_CONTACT_URL : SITE_CONFIG.links.appointment');
    expect(footer).toContain('coordinationInquiry ? PARENTING_COORDINATION_CONTACT_URL : SITE_CONFIG.links.appointment');
    expect(floating).toContain('PARENTING_COORDINATION_WHATSAPP_MESSAGE');
    expect(contact).toContain("formData.service === 'parenting_coordination'");
    expect(contact).toContain('ללא פרטי ילדים או פרטים רגישים');
    expect(contact).toContain('!isLectureInquiry && !isCoordinationInquiry');
  });
});
