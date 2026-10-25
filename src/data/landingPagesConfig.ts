import { COMPACT_KEYWORD_PILOT_CONFIG } from './compactKeywordPilotConfig';

export interface LandingPageTrustPoint {
  icon: 'map-pin' | 'clock' | 'shield' | 'check' | 'heart' | 'user';
  text: string;
}

export interface LandingPagePainPoint {
  title: string;
  desc: string;
  icon?: 'alert' | 'message' | 'heart' | 'clock' | 'user' | 'shield';
}

export interface LandingPageApproachStep {
  stepNumber: number;
  timeBadge: string;
  title: string;
  desc: string;
}

export interface LandingPageFaqItem {
  question: string;
  answer: string;
}

export interface LandingPageRelatedService {
  title: string;
  description: string;
  linkText: string;
  href: string;
}

export interface LandingPageConfig {
  slug: string;
  serviceType: string;
  landingPageType: string;
  meta: { title: string; description: string; canonicalUrl: string; keywords: string[]; image?: string; robots?: string; noIndex?: boolean; };
  hero: { badge: string; headline: string; subheadline: string; primaryCtaText: string; whatsappCtaText: string; prefilledWhatsappMessage: string; trustPoints: LandingPageTrustPoint[]; };
  painPoints: { sectionTitle: string; sectionSubtitle: string; items: LandingPagePainPoint[]; };
  approach: { sectionTitle: string; sectionSubtitle: string; steps: LandingPageApproachStep[]; };
  relatedService: LandingPageRelatedService;
  bio: { name: string; role: string; description: string; credentials: string[]; image: string; };
  pricing: { amount: number; currency: string; title: string; description: string; duration: string; };
  booking: { title: string; subtitle: string; calendlyAriaLabel: string; };
  faq: { sectionTitle: string; items: LandingPageFaqItem[]; };
  closingCta: { title: string; subtitle: string; primaryCtaText: string; whatsappCtaText: string; };
  schema: { serviceName: string; alternateName?: string; serviceType: string; description: string; addressLocality: string; areaServed: string[]; };
}

const LEGACY_LANDING_PAGES_CONFIG: Record<string, LandingPageConfig> = {
  'couples-crisis-ashdod': {
    slug: '/couples-crisis-ashdod', serviceType: 'couples_crisis', landingPageType: 'crisis_ashdod',
    meta: { title: 'ייעוץ זוגי במשבר באשדוד | שירה סהרוני', description: 'זוגיות במשבר חריף? עצירת הסלמה וחידוש התקשורת בקליניקה באשדוד או בזום. פגישה ממוקדת של 50 דק׳ עם שירה סהרוני, יועצת זוגית מוסמכת.', canonicalUrl: 'https://kesher.saharoni.com/couples-crisis-ashdod', robots: 'noindex, follow', noIndex: true, keywords: ['ייעוץ זוגי במשבר אשדוד'], image: '/images/generated/services/couples-room.jpg' },
    hero: { badge: 'מרחב מוגן לעצירת הסלמה וחידוש השיח | אשדוד ובזום', headline: 'ייעוץ זוגי במשבר באשדוד — לעצור את ההסלמה ולחזור לדבר', subheadline: 'כשהוויכוחים מתלקחים והשתיקות נמשכות, ייעוץ ממוקד עוזר להוריד הסלמה ולחזור לשיח.', primaryCtaText: 'קביעת פגישת ייעוץ', whatsappCtaText: 'התייעצות ב-WhatsApp', prefilledWhatsappMessage: 'היי שירה, אשמח לתאם ייעוץ זוגי.', trustPoints: [{icon:'map-pin',text:'אשדוד / זום'},{icon:'clock',text:'50 דקות'},{icon:'shield',text:'דיסקרטיות'}] },
    painPoints:{sectionTitle:'מתי פונים?',sectionSubtitle:'כשהקשר תקוע בדפוס חוזר.',items:[{title:'ריבים',desc:'הסלמה חוזרת',icon:'alert'},{title:'ריחוק',desc:'שתיקות וריחוק',icon:'message'},{title:'אמון',desc:'משבר אמון',icon:'heart'},{title:'שחיקה',desc:'עומס ושחיקה',icon:'clock'}]},
    approach:{sectionTitle:'איך עובדים?',sectionSubtitle:'תהליך ממוקד',steps:[{stepNumber:1,timeBadge:'1',title:'מיפוי',desc:'ממפים'},{stepNumber:2,timeBadge:'2',title:'כלים',desc:'מתרגלים'},{stepNumber:3,timeBadge:'3',title:'הסכמות',desc:'בונים הסכמות'}]}, relatedService:{title:'ייעוץ זוגי',description:'מידע רחב',linkText:'לשירות',href:'/services/couples/crisis'}, bio:{name:'שירה סהרוני',role:'יועצת זוגית ומנחת הורים מוסמכת',description:'ליווי זוגות ומשפחות',credentials:['יועצת זוגית מוסמכת'],image:'/images/shira-saharoni-about.webp'}, pricing:{amount:500,currency:'ILS',title:'פגישה',description:'50 דקות',duration:'50 דקות'}, booking:{title:'קביעת פגישה',subtitle:'אשדוד או זום',calendlyAriaLabel:'קביעת פגישה'}, faq:{sectionTitle:'שאלות',items:[{question:'איפה?',answer:'אשדוד או זום'},{question:'כמה?',answer:'500 ₪'},{question:'משך?',answer:'50 דקות'},{question:'התחייבות?',answer:'לא'}]}, closingCta:{title:'אפשר להתחיל',subtitle:'בפגישה ממוקדת',primaryCtaText:'קביעת פגישה',whatsappCtaText:'WhatsApp'}, schema:{serviceName:'ייעוץ זוגי במשבר באשדוד',serviceType:'Couples Counseling',description:'ייעוץ זוגי',addressLocality:'אשדוד',areaServed:['אשדוד','ישראל (אונליין)']}
  }
};

// Existing landing-page entries are preserved in git history; compact pilot configs are
// merged here so every consumer continues to use one authoritative registry.
export const LANDING_PAGES_CONFIG: Record<string, LandingPageConfig> = {
  ...LEGACY_LANDING_PAGES_CONFIG,
  ...COMPACT_KEYWORD_PILOT_CONFIG,
};
