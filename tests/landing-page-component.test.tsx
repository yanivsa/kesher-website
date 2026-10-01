import React from 'react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { LANDING_PAGES_CONFIG } from '../src/data/landingPagesConfig';
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

    const link = screen.getByRole('link', { name: /לפרטים על ייעוץ זוגי במשבר באשדוד/i });
    expect(link.getAttribute('href')).toBe('/couples-crisis-ashdod');

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
