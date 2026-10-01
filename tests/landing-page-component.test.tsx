import React from 'react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { LANDING_PAGES_CONFIG } from '../src/data/landingPagesConfig';
import publishedPosts from '../src/data/publishedPosts';
import { LandingPageTemplate } from '../src/pages/Landing/LandingPageTemplate';
import { LandingCalloutBanner } from '../src/components/LandingCalloutBanner/LandingCalloutBanner';

vi.mock('../src/components/Booking/CalendlyBookingEmbed', () => ({
  default: () => <div data-testid="calendly-embed-mock">Calendly Embed</div>,
}));

beforeEach(() => {
  class MockIntersectionObserver {
    observe = vi.fn();
    unobserve = vi.fn();
    disconnect = vi.fn();
  }
  window.IntersectionObserver = MockIntersectionObserver as unknown as typeof IntersectionObserver;
});

afterEach(() => {
  cleanup();
});

describe('LandingPageTemplate Component', () => {
  const config = LANDING_PAGES_CONFIG['couples-crisis-ashdod'];

  it('renders above-the-fold hero with h1 and dual CTAs', () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/couples-crisis-ashdod']}>
        <LandingPageTemplate config={config} />
      </MemoryRouter>
    );

    const heading = screen.getByRole('heading', { level: 1 });
    expect(heading).toBeDefined();
    expect(heading.textContent).toBe(config.hero.headline);

    // Hero WhatsApp link
    const whatsappLinks = container.querySelectorAll('a[href*="wa.me"]');
    expect(whatsappLinks.length).toBeGreaterThan(0);
    const heroWhatsapp = whatsappLinks[0] as HTMLAnchorElement;
    expect(heroWhatsapp.href).toContain('wa.me');
    expect(heroWhatsapp.href).toContain(encodeURIComponent(config.hero.prefilledWhatsappMessage));

    // Direct phone links
    const phoneLinks = container.querySelectorAll('a[href^="tel:"]');
    expect(phoneLinks.length).toBeGreaterThan(0);
  });

  it('renders pain points, 3 steps, bio, and transparent pricing', () => {
    render(
      <MemoryRouter initialEntries={['/couples-crisis-ashdod']}>
        <LandingPageTemplate config={config} />
      </MemoryRouter>
    );

    // Pain points
    expect(screen.getByText(config.painPoints.sectionTitle)).toBeDefined();
    config.painPoints.items.forEach((item) => {
      expect(screen.getByText(item.title)).toBeDefined();
    });

    // 3 steps
    expect(screen.getByText(config.approach.sectionTitle)).toBeDefined();
    config.approach.steps.forEach((step) => {
      expect(screen.getByText(step.title)).toBeDefined();
    });

    // Bio
    const bioNameElements = screen.getAllByText(config.bio.name);
    expect(bioNameElements.length).toBeGreaterThan(0);
    expect(screen.getByText(config.bio.role)).toBeDefined();

    // Pricing
    expect(screen.getByText(/500 ₪/)).toBeDefined();
    expect(screen.getByText(config.pricing.title)).toBeDefined();
  });

  it('renders objection-handling FAQ items', () => {
    render(
      <MemoryRouter initialEntries={['/couples-crisis-ashdod']}>
        <LandingPageTemplate config={config} />
      </MemoryRouter>
    );

    expect(screen.getByText(config.faq.sectionTitle)).toBeDefined();
    config.faq.items.forEach((item) => {
      expect(screen.getByText(item.question)).toBeDefined();
    });
  });
});

describe('LandingCalloutBanner Component', () => {
  it('renders couples_crisis preset with matching landing page link', () => {
    const { container } = render(
      <MemoryRouter>
        <LandingCalloutBanner target="couples_crisis" />
      </MemoryRouter>
    );

    const link = screen.getByRole('link', { name: /למידע על ייעוץ זוגי במשבר/i });
    expect(link.getAttribute('href')).toBe('/services/couples/crisis');

    const whatsapp = container.querySelector('a[href*="wa.me"]') as HTMLAnchorElement;
    expect(whatsapp).toBeDefined();
    expect(whatsapp.href).toContain('wa.me');
  });

  it('renders parenting_adhd preset with matching landing page link', () => {
    render(
      <MemoryRouter>
        <LandingCalloutBanner target="parenting_adhd" />
      </MemoryRouter>
    );

    const link = screen.getByRole('link', { name: /לפרטים על הדרכת הורים ל-ADHD באשדוד/i });
    expect(link.getAttribute('href')).toBe('/parenting-adhd-ashdod');
  });

  it('renders couples_gan_yavne preset with matching landing page link', () => {
    render(
      <MemoryRouter>
        <LandingCalloutBanner target="couples_gan_yavne" />
      </MemoryRouter>
    );

    const link = screen.getByRole('link', { name: /לייעוץ זוגי בגן יבנה והסביבה/i });
    expect(link.getAttribute('href')).toBe('/couples-counseling-gan-yavne');
  });

  it('renders couples_mediation preset with matching landing page link', () => {
    render(
      <MemoryRouter>
        <LandingCalloutBanner target="couples_mediation" />
      </MemoryRouter>
    );

    const link = screen.getByRole('link', { name: /למידע על גישור ושלום בית באשדוד/i });
    expect(link.getAttribute('href')).toBe('/couples-mediation-ashdod');
  });
});

describe('getLandingTargetForPost Blog Routing Policy', () => {
  it('maps specific ADHD posts to parenting_adhd', async () => {
    const { getLandingTargetForPost } = await import('../src/utils/landingCalloutHelper');
    expect(getLandingTargetForPost({ id: 'adhd-morning-conflict-dopamine-myth' })).toBe('parenting_adhd');
    expect(getLandingTargetForPost({ id: 'adhd-morning-routine' })).toBe('parenting_adhd');
    expect(getLandingTargetForPost({ id: 'smart-youth-focus-tasks-organization' })).toBe('parenting_adhd');
    expect(getLandingTargetForPost({ id: 'adhd-waiting-mode' })).toBe('parenting_adhd');
  });

  it('maps specific high-conflict couple crisis posts to couples_crisis', async () => {
    const { getLandingTargetForPost } = await import('../src/utils/landingCalloutHelper');
    expect(getLandingTargetForPost({ id: 'relationship-crisis-flydubai-lessons' })).toBe('couples_crisis');
    expect(getLandingTargetForPost({ id: 'communication-breakdown' })).toBe('couples_crisis');
    expect(getLandingTargetForPost({ id: 'breaking-silent-treatment-relationship' })).toBe('couples_crisis');
    expect(getLandingTargetForPost({ id: 'relationship-after-childbirth' })).toBe('couples_crisis');
  });

  it('returns null for non-ADHD parenting and kindergarten separation posts', async () => {
    const { getLandingTargetForPost } = await import('../src/utils/landingCalloutHelper');
    // Critical defect check: kindergarten morning separation anxiety is NOT divorce mediation or ADHD!
    expect(getLandingTargetForPost({
      id: 'separation-anxiety-morning-dropoff',
      title: 'הוא בוכה בשער הגן ואתם נשברים? הדרך הנכונה להתמודד עם חרדת פרידה בבוקר',
      category: 'הדרכת הורים',
    })).toBeNull();

    expect(getLandingTargetForPost({
      id: 'siblings-fairness-vs-equality',
      title: 'מריבות אחים: למה הוא קיבל יותר?',
      category: 'הדרכת הורים',
    })).toBeNull();
  });

  it('returns null for dating or general posts without explicit landing mapping', async () => {
    const { getLandingTargetForPost } = await import('../src/utils/landingCalloutHelper');
    expect(getLandingTargetForPost({ id: 'why-is-it-so-hard-to-find-love' })).toBeNull();
    expect(getLandingTargetForPost({ id: 'couples-adhd-partner' })).toBeNull();
    expect(getLandingTargetForPost(null)).toBeNull();
    expect(getLandingTargetForPost(undefined)).toBeNull();
  });
});

describe('Compact callout distribution', () => {
  it('keeps mappings explicit, publishable, and conservative', async () => {
    const { getLandingTargetForPost, ADHD_LANDING_POST_SLUGS, CRISIS_LANDING_POST_SLUGS } = await import('../src/utils/landingCalloutHelper');
    const publishedIds = new Set(publishedPosts.map((post) => post.id));

    [...ADHD_LANDING_POST_SLUGS, ...CRISIS_LANDING_POST_SLUGS].forEach((id) => {
      expect(publishedIds.has(id)).toBe(true);
    });

    const counts = publishedPosts.reduce(
      (acc, post) => {
        const target = getLandingTargetForPost(post);
        if (target === 'parenting_adhd') acc.parenting_adhd += 1;
        else if (target === 'couples_crisis') acc.couples_crisis += 1;
        else acc.none += 1;
        return acc;
      },
      { parenting_adhd: 0, couples_crisis: 0, none: 0 },
    );

    expect(counts.parenting_adhd).toBe(5);
    expect(counts.couples_crisis).toBe(4);
    expect(counts.none).toBe(publishedPosts.length - 9);
  });
});

describe('Remediation Sprint A Quality & Safety Gates', () => {
  it('renders authentic hero image and badge in LandingPageTemplate', () => {
    const config = LANDING_PAGES_CONFIG['couples-crisis-ashdod'];
    render(
      <MemoryRouter initialEntries={['/couples-crisis-ashdod']}>
        <LandingPageTemplate config={config} />
      </MemoryRouter>
    );

    const heroImages = screen.getAllByAltText(`${config.bio.name} - ${config.bio.role}`);
    expect(heroImages.length).toBeGreaterThan(0);
    const heroImg = heroImages[0] as HTMLImageElement;
    expect(heroImg.src).toContain('shira-saharoni');
  });

  it('renders top objection FAQs visibly open by default', () => {
    const config = LANDING_PAGES_CONFIG['couples-crisis-ashdod'];
    const { container } = render(
      <MemoryRouter initialEntries={['/couples-crisis-ashdod']}>
        <LandingPageTemplate config={config} />
      </MemoryRouter>
    );

    const detailsElements = container.querySelectorAll('details');
    expect(detailsElements.length).toBeGreaterThanOrEqual(2);
    expect(detailsElements[0].open).toBe(true);
    expect(detailsElements[1].open).toBe(true);
  });

  it('verifies indexing holding status for cannibalizing routes', () => {
    expect(LANDING_PAGES_CONFIG['couples-crisis-ashdod'].meta.noIndex).toBe(true);
    expect(LANDING_PAGES_CONFIG['couples-crisis-ashdod'].meta.robots).toBe('noindex, follow');

    expect(LANDING_PAGES_CONFIG['couples-counseling-gan-yavne'].meta.noIndex).toBe(true);
    expect(LANDING_PAGES_CONFIG['couples-counseling-gan-yavne'].meta.robots).toBe('noindex, follow');
  });

  it('verifies that step timeBadges use structured stages instead of minute intervals', () => {
    Object.values(LANDING_PAGES_CONFIG).forEach((config) => {
      config.approach.steps.forEach((step, idx) => {
        expect(step.timeBadge).toBe(`שלב ${idx + 1}`);
        expect(step.timeBadge).not.toMatch(/דק׳|דקות/);
      });
    });
  });

  it('verifies ethical boundaries and absence of absolute claims in copy', () => {
    const allConfigJson = JSON.stringify(LANDING_PAGES_CONFIG);

    // Absolute claims banned in Sprint A
    expect(allConfigJson).not.toContain('דיסקרטיות מלאה ומוחלטת');
    expect(allConfigJson).not.toContain('מקלים בכל בית');
    expect(allConfigJson).not.toContain('שיוצר הקלה מיידית');
    expect(allConfigJson).not.toContain('מונע מאבקים הרסניים');
    expect(allConfigJson).not.toContain('מומחית לאתגרי קשב ותפקודים ניהוליים');
    expect(allConfigJson).not.toContain('חניה צמודה ודיסקרטית');

    // Judicial enforceability clarification in mediation
    expect(LANDING_PAGES_CONFIG['couples-mediation-ashdod'].faq.items[1].answer).toContain(
      'בית המשפט לענייני משפחה או בית הדין הרבני'
    );
  });
});
