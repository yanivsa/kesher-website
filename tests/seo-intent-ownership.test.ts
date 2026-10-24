import fs from 'node:fs';
import path from 'node:path';
import { describe, expect, it } from 'vitest';

const readSource = (relativePath: string) =>
  fs.readFileSync(path.resolve(process.cwd(), relativePath), 'utf8');

describe('SEO intent ownership for compact keyword landing pages', () => {
  it('keeps the generic couples service focused on broad/online intent instead of Ashdod local intent', () => {
    const source = readSource('src/pages/Services/Couples/CouplesCounseling.tsx');

    expect(source).toContain('title="ייעוץ זוגי | תקשורת, משבר וריחוק"');
    expect(source).toContain('<h1>ייעוץ זוגי — להבין מה קורה ביניכם ולחזור לדבר</h1>');
    expect(source).not.toContain('title="ייעוץ זוגי באשדוד ואונליין"');
  });

  it('keeps the generic parenting service focused on broad/online intent instead of Ashdod local intent', () => {
    const source = readSource('src/pages/Services/Parenting/ParentingGuidance.tsx');

    expect(source).toContain('title="הדרכת הורים | ADHD, מחוננים, גבולות ומעברים"');
    expect(source).toContain('<h1>הדרכת הורים — להבין מה מקשה ולבחור תגובה שעוזרת</h1>');
    expect(source).not.toContain('title="הדרכת הורים באשדוד ואונליין | ADHD, מחוננים וכיתה א׳"');
  });

  it('preserves the dedicated Ashdod landing pages as the owners of local intent', () => {
    const couplesLanding = readSource(
      'src/pages/Landing/CouplesCounselingAshdod/CouplesCounselingAshdodPage.tsx',
    );
    const parentingLanding = readSource(
      'src/pages/Landing/ParentingGuidanceAshdod/ParentingGuidanceAshdodPage.tsx',
    );

    expect(couplesLanding).toContain('title="ייעוץ זוגי באשדוד | שירה סהרוני"');
    expect(couplesLanding).toContain('h1: \'ייעוץ זוגי באשדוד');
    expect(parentingLanding).toContain('title="הדרכת הורים באשדוד | שירה סהרוני"');
    expect(parentingLanding).toContain('הדרכת הורים באשדוד');
  });
});
