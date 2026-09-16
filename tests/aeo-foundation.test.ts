import { describe, expect, it } from 'vitest';
import { SITE_CONFIG } from '../src/constants/siteConfig';
import { buildSitemap } from '../scripts/generate-sitemap.cjs';
import { getTodayIso, validatePostDates, validatePostAbsoluteClaims } from '../scripts/validate-content.cjs';

describe('AEO Foundation — Canonical Entity & Structured Data', () => {
  it('confirms canonical Shira Person ID and author URL in SITE_CONFIG', () => {
    expect(SITE_CONFIG.author).toBe('שירה סהרוני');
    expect(SITE_CONFIG.url).toBe('https://kesher.saharoni.com');
  });

  it('generates truthful sitemap lastmod using updatedAt when present and date otherwise', () => {
    const mockPosts = [
      {
        id: 'post-with-update',
        title: 'מאמר מעודכן עם תאריך אמת',
        date: '2026-06-01',
        updatedAt: '2026-09-15',
        category: 'זוגיות',
        content: '<h3>כותרת 1</h3><p>' + 'מילה '.repeat(150) + '</p>' +
                 '<h3>כותרת 2</h3><p>' + 'מילה '.repeat(150) + '</p>' +
                 '<h3>כותרת 3</h3><p>' + 'מילה '.repeat(150) + '</p>' +
                 '<h3>כותרת 4</h3><p>' + 'מילה '.repeat(150) + '</p>' +
                 '<h3>כותרת 5</h3><p>' + 'מילה '.repeat(150) + '</p>',
      },
      {
        id: 'post-without-update',
        title: 'מאמר מקורי ללא עדכון',
        date: '2026-05-10',
        category: 'הדרכת הורים',
        content: '<h3>כותרת 1</h3><p>' + 'מילה '.repeat(150) + '</p>' +
                 '<h3>כותרת 2</h3><p>' + 'מילה '.repeat(150) + '</p>' +
                 '<h3>כותרת 3</h3><p>' + 'מילה '.repeat(150) + '</p>' +
                 '<h3>כותרת 4</h3><p>' + 'מילה '.repeat(150) + '</p>' +
                 '<h3>כותרת 5</h3><p>' + 'מילה '.repeat(150) + '</p>',
      }
    ];

    const xml = buildSitemap(mockPosts);
    expect(xml).toContain('<loc>https://kesher.saharoni.com/blog/post-with-update</loc>');
    expect(xml).toContain('<lastmod>2026-09-15</lastmod>');
    expect(xml).toContain('<loc>https://kesher.saharoni.com/blog/post-without-update</loc>');
    expect(xml).toContain('<lastmod>2026-05-10</lastmod>');
  });
});

describe('AEO Foundation — Date Validation (Truthful & Deterministic)', () => {
  const fixedToday = '2026-09-16';

  it('formats getTodayIso in Asia/Jerusalem YYYY-MM-DD format', () => {
    const today = getTodayIso();
    expect(today).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it('passes valid same-day modification (updatedAt === today)', () => {
    const post = { id: 'p1', date: '2026-09-16', updatedAt: '2026-09-16' };
    expect(validatePostDates(post, fixedToday)).toEqual([]);
  });

  it('passes valid historical modification (date <= updatedAt <= today)', () => {
    const post = { id: 'p2', date: '2026-06-01', updatedAt: '2026-08-15' };
    expect(validatePostDates(post, fixedToday)).toEqual([]);
  });

  it('fails when updatedAt precedes datePublished (updatedAt < date)', () => {
    const post = { id: 'p3', date: '2026-09-16', updatedAt: '2026-09-10' };
    const errors = validatePostDates(post, fixedToday);
    expect(errors.length).toBe(1);
    expect(errors[0]).toContain('cannot be earlier than publish date');
  });

  it('fails when updatedAt is in the future relative to validation date', () => {
    const post = { id: 'p4', date: '2026-09-16', updatedAt: '2026-09-20' };
    const errors = validatePostDates(post, fixedToday);
    expect(errors.length).toBe(1);
    expect(errors[0]).toContain('cannot be in the future');
  });

  it('fails when updatedAt has invalid format', () => {
    const post = { id: 'p5', date: '2026-09-16', updatedAt: '16/09/2026' };
    const errors = validatePostDates(post, fixedToday);
    expect(errors.length).toBe(1);
    expect(errors[0]).toContain('Invalid updatedAt format (must be YYYY-MM-DD)');
  });
});

describe('AEO Foundation — Narrow Absolute Claim Validation', () => {
  it('does NOT reject legitimate professional credentials containing מוסמכת (e.g. מגשרת מוסמכת)', () => {
    const legitimateText = '<p>שירה סהרוני היא מגשרת מוסמכת בעלת ניסיון רב בליווי זוגות.</p>';
    expect(validatePostAbsoluteClaims(legitimateText)).toBe(true);

    const mediationText = '<p>ההליך מנוהל על ידי מגשרת מוסמכת בלשכת המגשרים.</p>';
    expect(validatePostAbsoluteClaims(mediationText)).toBe(true);
  });

  it('rejects unsupported absolute marketing superlatives and guarantees', () => {
    expect(validatePostAbsoluteClaims('<p>זוהי הדרך היחידה לפתור את הבעיה.</p>')).toBe(false);
    expect(validatePostAbsoluteClaims('<p>כידוע, טראומות לא נשכחות לעולם.</p>')).toBe(false);
    expect(validatePostAbsoluteClaims('<p>הסדנה מספקת פתרון קסם לכל משבר.</p>')).toBe(false);
    expect(validatePostAbsoluteClaims('<p>אנו מעניקים 100% הצלחה בכל תהליך.</p>')).toBe(false);
  });

  it('rejects unauthorized clinical credentials combined with מוסמכת', () => {
    expect(validatePostAbsoluteClaims('<p>פסיכולוגית מוסמכת מטעם משרד הבריאות</p>')).toBe(false);
    expect(validatePostAbsoluteClaims('<p>מטפלת מוסמכת בשיטת CBT</p>')).toBe(false);
    expect(validatePostAbsoluteClaims('<p>פסיכותרפיסטית מוסמכת</p>')).toBe(false);
  });
});

