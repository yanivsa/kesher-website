import { describe, expect, it } from 'vitest';
import { LANDING_PAGES_CONFIG } from '../src/data/landingPagesConfig';
import { validatePostAbsoluteClaims } from '../scripts/validate-content.cjs';

describe('Landing Pages Configuration (Compact Keywords / Conversion SEO)', () => {
  const configs = Object.values(LANDING_PAGES_CONFIG);

  it('defines all 4 required high-intent landing pages', () => {
    const keys = Object.keys(LANDING_PAGES_CONFIG);
    expect(keys).toContain('couples-crisis-ashdod');
    expect(keys).toContain('parenting-adhd-ashdod');
    expect(keys).toContain('couples-counseling-gan-yavne');
    expect(keys).toContain('couples-mediation-ashdod');
    expect(configs.length).toBe(4);
  });

  configs.forEach((config) => {
    describe(`Config: ${config.slug}`, () => {
      it('enforces SEO meta title under 60 chars and description under 155 chars', () => {
        expect(config.meta.title.length).toBeLessThan(60);
        expect(config.meta.description.length).toBeLessThan(155);
        expect(config.meta.canonicalUrl).toBe(`https://kesher.saharoni.com${config.slug}`);
      });

      it('has non-empty targeted keywords and hero copy', () => {
        expect(config.meta.keywords.length).toBeGreaterThanOrEqual(3);
        expect(config.hero.headline.length).toBeGreaterThan(10);
        expect(config.hero.subheadline.length).toBeGreaterThan(20);
        expect(config.hero.primaryCtaText).toBeTruthy();
        expect(config.hero.whatsappCtaText).toBeTruthy();
        expect(config.hero.prefilledWhatsappMessage).toBeTruthy();
        expect(config.hero.trustPoints.length).toBeGreaterThanOrEqual(3);
      });

      it('has 3–4 acute pain points', () => {
        expect(config.painPoints.items.length).toBeGreaterThanOrEqual(3);
        expect(config.painPoints.items.length).toBeLessThanOrEqual(5);
        config.painPoints.items.forEach((item) => {
          expect(item.title).toBeTruthy();
          expect(item.desc).toBeTruthy();
        });
      });

      it('has 3 practical approach steps', () => {
        expect(config.approach.steps.length).toBe(3);
        config.approach.steps.forEach((step, idx) => {
          expect(step.stepNumber).toBe(idx + 1);
          expect(step.title).toBeTruthy();
          expect(step.desc).toBeTruthy();
        });
      });

      it('has 4–6 objection-handling FAQ items', () => {
        expect(config.faq.items.length).toBeGreaterThanOrEqual(4);
        expect(config.faq.items.length).toBeLessThanOrEqual(6);
        config.faq.items.forEach((item) => {
          expect(item.question.length).toBeGreaterThan(5);
          expect(item.answer.length).toBeGreaterThan(15);
        });
      });

      it('has valid bio, pricing, and schema details', () => {
        expect(config.bio.name).toBe('שירה סהרוני');
        expect(config.pricing.amount).toBe(500);
        expect(config.pricing.currency).toBe('ILS');
        expect(config.schema.serviceName).toBeTruthy();
        expect(config.schema.areaServed.length).toBeGreaterThanOrEqual(3);
      });

      it('passes absolute claims and truthful boundary verification', () => {
        const fullText = [
          config.meta.title,
          config.meta.description,
          config.hero.headline,
          config.hero.subheadline,
          config.bio.description,
          ...config.bio.credentials,
          ...config.painPoints.items.map((i) => `${i.title} ${i.desc}`),
          ...config.approach.steps.map((s) => `${s.title} ${s.desc}`),
          ...config.faq.items.map((f) => `${f.question} ${f.answer}`),
        ].join(' ');

        expect(validatePostAbsoluteClaims(fullText)).toBe(true);
      });
    });
  });
});
