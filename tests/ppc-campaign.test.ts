import fs from 'fs';
import path from 'path';
import { describe, expect, it } from 'vitest';

const PPC_DIR = path.resolve(process.cwd(), 'config/ppc');

interface CampaignConfig {
  campaign_name: string;
  keywords: {
    exact_and_phrase: string[];
    negative: string[];
  };
  ads: Array<{
    type: string;
    headlines: string[];
    descriptions: string[];
    final_url: string;
  }>;
}

interface GtmConfig {
  gtm_container_id: string;
  events_mapping: Array<{
    event_name: string;
    trigger: string;
    tags: string[];
    type: string;
  }>;
}

describe('PPC Campaign Configurations & Conversion Tracking', () => {
  const jsonFiles = [
    'google_ads_ashdod_campaign.json',
    'google_ads_crisis_campaign.json',
    'google_ads_before_separation_campaign.json',
  ];

  jsonFiles.forEach((fileName) => {
    describe(`JSON Config: ${fileName}`, () => {
      const filePath = path.join(PPC_DIR, fileName);
      const content = fs.readFileSync(filePath, 'utf-8');
      const config: CampaignConfig = JSON.parse(content);

      it('has valid campaign name and keywords', () => {
        expect(config.campaign_name).toBeTruthy();
        expect(config.keywords.exact_and_phrase.length).toBeGreaterThan(0);
        expect(config.keywords.negative.length).toBeGreaterThan(0);
      });

      it('enforces character length constraints on ad headlines (<= 30) and descriptions (<= 90)', () => {
        config.ads.forEach((ad) => {
          ad.headlines.forEach((headline) => {
            expect(headline.length).toBeLessThanOrEqual(30);
          });
          ad.descriptions.forEach((desc) => {
            expect(desc.length).toBeLessThanOrEqual(90);
          });
        });
      });

      it('enforces canonical landing page URLs and required UTM parameters', () => {
        config.ads.forEach((ad) => {
          const url = new URL(ad.final_url);
          expect(url.origin).toBe('https://kesher.saharoni.com');
          expect(url.pathname.endsWith('/')).toBe(false);
          expect(url.pathname).toMatch(/^\/services\/couples\/(ashdod|crisis|before-separation)$/);

          expect(url.searchParams.get('utm_source')).toBe('google');
          expect(url.searchParams.get('utm_medium')).toBe('cpc');
          expect(url.searchParams.get('utm_campaign')).toBeTruthy();
          expect(url.searchParams.get('utm_content')).toBeTruthy();
        });
      });
    });
  });

  describe('CSV Import: google_ads_import.csv', () => {
    const csvPath = path.join(PPC_DIR, 'google_ads_import.csv');
    const rawCsv = fs.readFileSync(csvPath, 'utf-8');
    const lines = rawCsv.trim().split('\n');
    const header = lines[0].split(',');

    it('has correct header columns', () => {
      expect(header).toContain('Campaign');
      expect(header).toContain('Ad Group');
      expect(header).toContain('Keyword');
      expect(header).toContain('Criterion Type');
      expect(header).toContain('Final URL');
    });

    it('includes all 3 search campaigns', () => {
      const campaigns = new Set(lines.slice(1).map((l) => l.split(',')[0]));
      expect(campaigns).toContain('Search_CouplesCounseling_Ashdod_V1');
      expect(campaigns).toContain('Search_CouplesCounseling_Crisis_V1');
      expect(campaigns).toContain('Search_CouplesCounseling_BeforeSeparation_V1');
    });

    it('validates responsive search ad headlines, descriptions, and canonical Final URLs', () => {
      const rsaRows = lines.slice(1).filter((l) => l.includes('Responsive search ad'));
      expect(rsaRows.length).toBe(3);

      rsaRows.forEach((row) => {
        const parts = row.split(',');
        const finalUrlStr = parts[parts.length - 1];
        const headlines = parts.slice(4, 9).filter(Boolean);
        const descriptions = parts.slice(9, 11).filter(Boolean);

        headlines.forEach((h) => expect(h.length).toBeLessThanOrEqual(30));
        descriptions.forEach((d) => expect(d.length).toBeLessThanOrEqual(90));

        const url = new URL(finalUrlStr);
        expect(url.origin).toBe('https://kesher.saharoni.com');
        expect(url.pathname.endsWith('/')).toBe(false);
        expect(url.pathname).toMatch(/^\/services\/couples\/(ashdod|crisis|before-separation)$/);
        expect(url.searchParams.get('utm_source')).toBe('google');
        expect(url.searchParams.get('utm_medium')).toBe('cpc');
        expect(url.searchParams.get('utm_campaign')).toBeTruthy();
      });
    });
  });

  describe('GTM Tag Configuration: gtm_tags_ppc_config.json', () => {
    const gtmPath = path.join(PPC_DIR, 'gtm_tags_ppc_config.json');
    const gtmConfig: GtmConfig = JSON.parse(fs.readFileSync(gtmPath, 'utf-8'));

    it('maps macro and micro conversion events to Google Ads tags', () => {
      const bookingEvent = gtmConfig.events_mapping.find(
        (e) => e.event_name === 'booking_confirmed',
      );
      expect(bookingEvent).toBeDefined();
      expect(bookingEvent?.tags).toContain('GoogleAds_Conversion_Booking');

      const whatsappEvent = gtmConfig.events_mapping.find(
        (e) => e.event_name === 'whatsapp_click',
      );
      expect(whatsappEvent).toBeDefined();
      expect(whatsappEvent?.tags).toContain('GoogleAds_Conversion_WhatsAppClick');

      const phoneEvent = gtmConfig.events_mapping.find(
        (e) => e.event_name === 'phone_click',
      );
      expect(phoneEvent).toBeDefined();
      expect(phoneEvent?.tags).toContain('GoogleAds_Conversion_PhoneClick');
    });
  });
});
