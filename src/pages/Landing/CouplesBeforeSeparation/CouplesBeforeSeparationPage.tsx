import React, { useState, useEffect, useRef } from 'react';
import {
  FiClock,
  FiShield,
  FiMapPin,
  FiCheckCircle,
  FiHelpCircle,
  FiCompass,
  FiPhone,
  FiChevronDown,
  FiChevronUp,
  FiInfo,
} from 'react-icons/fi';
import { FaWhatsapp } from 'react-icons/fa';
import MetaTags from '../../../components/SEO/MetaTags';
import SchemaOrg from '../../../components/SEO/SchemaOrg';
import CalendlyBookingEmbed from '../../../components/Booking/CalendlyBookingEmbed';
import { SITE_CONFIG } from '../../../constants/siteConfig';
import { useLandingPageAnalytics } from '../../../hooks/useLandingPageAnalytics';
import styles from './CouplesBeforeSeparationPage.module.css';

interface FAQItem {
  q: string;
  a: string;
}

const FAQS: FAQItem[] = [
  {
    q: 'האם התהליך מיועד רק לזוגות שרוצים להישאר יחד בכל מחיר?',
    a: 'לא. המטרה היא בירור זוגי רגוע וכנה. אנחנו בודקים האם קיימת אפשרות ורצון הדדי לשיקום הקשר, ואם מחליטים להיפרד – איך לעשות זאת בהסכמה, בכבוד ובמינימום פגיעה בילדים.',
  },
  {
    q: 'מה ההבדל בין ייעוץ זוגי בצומת החלטה לבין ייעוץ משפטי?',
    a: 'הייעוץ אינו מהווה ייעוץ משפטי ואינו תחליף לייצוג משפטי. מטרתו היא בירור רגשי, זוגי ותקשורתי, וכן בניית הסכמות ענייניות במידה ופונים לנתיב גישור.',
  },
  {
    q: 'מה קורה אם צד אחד רוצה לנסות והצד השני כבר מיואש?',
    a: 'זהו מצב נפוץ מאוד בצמתים כאלה. הפגישה מאפשרת לשים את הפערים על השולחן בצורה מכבדת ולבחון ללא לחץ האם יש מקום להזדמנות אמיתית או להבנה משותפת.',
  },
  {
    q: 'כמה זמן נמשכת פגישה ומה עלותה?',
    a: 'פגישת ייעוץ ובירור אורכת 50 דקות מלאות. המחיר הוא 500 ₪ כולל מע״מ לפגישה, ללא כל התחייבות לסדרת מפגשים.',
  },
  {
    q: 'איפה מתקיימות הפגישות?',
    a: 'בקליניקה נעימה ודיסקרטית באשדוד, או בפגישת זום מאובטחת אונליין לפי העדפתכם.',
  },
];

const CouplesBeforeSeparationPage: React.FC = () => {
  const [openFaq, setOpenFaq] = useState<number | null>(null);
  const [isBookingInView, setIsBookingInView] = useState(false);
  const bookingRef = useRef<HTMLDivElement>(null);

  const {
    trackCtaClick,
    trackSecondaryCtaClick,
    trackPhoneClick,
    trackWhatsappClick,
    trackCalendlyOpen,
  } = useLandingPageAnalytics({
    variantId: 'A',
    landingPagePath: '/services/couples/before-separation',
    landingPageType: 'before_separation',
    serviceType: 'couples_before_separation',
  });

  const whatsappPhone = SITE_CONFIG.contact.phone.replace(/[^0-9]/g, '');
  const whatsappUrl = `https://wa.me/${whatsappPhone}?text=${encodeURIComponent(
    'היי שירה, אנחנו בצומת החלטה משמעותי בזוגיות ונשמח לתאם פגישת בירור וייעוץ.',
  )}`;

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        setIsBookingInView(entry.isIntersecting);
      },
      { threshold: 0.15 }
    );

    if (bookingRef.current) {
      observer.observe(bookingRef.current);
    }

    return () => {
      observer.disconnect();
    };
  }, []);

  const toggleFaq = (index: number) => {
    setOpenFaq((prev) => (prev === index ? null : index));
  };

  const scrollToBooking = (location: string) => {
    trackCtaClick('קביעת פגישה', location);
    trackCalendlyOpen();
    if (bookingRef.current) {
      bookingRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const schemaData = {
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'Service',
        name: 'ייעוץ ובירור זוגי בצומת החלטה ולפני פרידה',
        serviceType: 'Couples Discernment and Counseling',
        provider: {
          '@type': 'Person',
          name: 'שירה סהרוני',
          jobTitle: 'יועצת זוגית, מנחת הורים ומגשרת מוסמכת',
          url: 'https://kesher.saharoni.com',
          telephone: '+972-50-2763802',
        },
        areaServed: [
          { '@type': 'City', name: 'אשדוד' },
          { '@type': 'Country', name: 'ישראל' },
        ],
        offers: {
          '@type': 'Offer',
          price: '500',
          priceCurrency: 'ILS',
          availability: 'https://schema.org/InStock',
        },
      },
      {
        '@type': 'FAQPage',
        mainEntity: FAQS.map((faq) => ({
          '@type': 'Question',
          name: faq.q,
          acceptedAnswer: {
            '@type': 'Answer',
            text: faq.a,
          },
        })),
      },
      {
        '@type': 'BreadcrumbList',
        itemListElement: [
          {
            '@type': 'ListItem',
            position: 1,
            name: 'עמוד הבית',
            item: 'https://kesher.saharoni.com',
          },
          {
            '@type': 'ListItem',
            position: 2,
            name: 'בירור זוגי בצומת החלטה ולפני פרידה',
            item: 'https://kesher.saharoni.com/services/couples/before-separation',
          },
        ],
      },
    ],
  };

  return (
    <main id="main-content" className={styles.page}>
      <MetaTags
        title="בירור זוגי לפני החלטות כבדות | שירה סהרוני – ייעוץ זוגי וגישור"
        description="מתלבטים לגבי עתיד הקשר? לפני שמקבלים החלטות כבדות, מרחב בירור זוגי רגוע וממוקד לבדיקת מרחב השינוי והאפשרויות להמשך. 500 ₪ לפגישה באשדוד או בזום."
        canonical="https://kesher.saharoni.com/services/couples/before-separation"
      />
      <SchemaOrg data={schemaData} />

      {/* Minimal Header */}
      <header className={styles.header}>
        <div className={`container ${styles.headerInner}`}>
          <a href="/" className={styles.brand} aria-label="מעבר לדף הבית של שירה סהרוני">
            <img src="/logo-kesher.svg" alt="קשר - שירה סהרוני" className={styles.brandLogo} width="40" height="40" />
            <div className={styles.brandText}>
              <span className={styles.brandTitle}>שירה סהרוני</span>
              <span className={styles.brandSubtitle}>ייעוץ זוגי, הנחיית הורים וגישור</span>
            </div>
          </a>

          <div className={styles.headerActions}>
            <a
              href={`tel:${whatsappPhone}`}
              className={styles.phoneCallBtn}
              onClick={() => trackPhoneClick()}
              aria-label="התקשרות טלפונית לשירה סהרוני"
            >
              <FiPhone aria-hidden="true" />
            </a>
            <button
              type="button"
              className={styles.headerCtaBtn}
              onClick={() => scrollToBooking('header')}
            >
              קביעת פגישה
            </button>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className={styles.hero}>
        <div className={`container ${styles.heroContent}`}>
          <div className={styles.heroBadge}>
            <FiCompass aria-hidden="true" />
            <span>צומת החלטה זוגי – מרחב לבירור מעמיק ורגוע</span>
          </div>

          <h1 className={styles.heroTitle}>
            לפני שמקבלים החלטה כבדה – בירור זוגי רגוע וממוקד
          </h1>

          <p className={styles.heroSubtitle}>
            כשהספקות מכבידים והעתיד לא ברור, לא חייבים למהר להחלטות חד-צדדיות. מרחב מקצועי ומאפשר להבין איפה אתם עומדים, מה ניתן לשנות, ואיך לקבל החלטות נכונות ואחראיות עבור שניכם ועבור המשפחה.
          </p>

          <div className={styles.heroCtaGroup}>
            <button
              type="button"
              className={styles.primaryCta}
              onClick={() => scrollToBooking('hero_primary')}
            >
              <FiCheckCircle aria-hidden="true" />
              <span>קביעת פגישת בירור</span>
            </button>

            <a
              href={whatsappUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={styles.secondaryCta}
              onClick={() => {
                trackSecondaryCtaClick('WhatsApp פתיח', 'hero');
                trackWhatsappClick();
              }}
              aria-label="שיחת התייעצות דיסקרטית ב-WhatsApp עם שירה סהרוני"
            >
              <FaWhatsapp aria-hidden="true" />
              <span>התייעצות דיסקרטית ב-WhatsApp</span>
            </a>
          </div>

          <div className={styles.heroTrustRow}>
            <div className={styles.trustItem}>
              <FiMapPin className={styles.trustIcon} aria-hidden="true" />
              <span>קליניקה באשדוד / אונליין בזום</span>
            </div>
            <div className={styles.trustItem}>
              <FiClock className={styles.trustIcon} aria-hidden="true" />
              <span>50 דקות לפגישה</span>
            </div>
            <div className={styles.trustItem}>
              <FiShield className={styles.trustIcon} aria-hidden="true" />
              <span>דיסקרטיות מלאה וללא שיפוטיות</span>
            </div>
          </div>
        </div>
      </section>

      {/* Decision Dilemmas Section */}
      <section className={styles.sectionAlt}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>למי מתאימה פגישת בירור זוגי?</h2>
            <p className={styles.sectionSubtitle}>
              המרחב מיועד לזוגות שנמצאים בצומת דרכים משמעותי ומבקשים לעשות סדר במחשבות לפני צעדים בלתי הפיכים.
            </p>
          </div>

          <div className={styles.grid3}>
            <div className={styles.clarityCard}>
              <FiHelpCircle className={styles.clarityIcon} aria-hidden="true" />
              <h3 className={styles.clarityTitle}>התלבטות האם לנסות שוב</h3>
              <p className={styles.clarityDesc}>
                בדיקה אמיתית האם נשארה מוטיבציה הדדית, אילו שינויים נדרשים כדי שזה יעבוד, והאם שניכם מוכנים להתגייס לתהליך.
              </p>
            </div>

            <div className={styles.clarityCard}>
              <FiCompass className={styles.clarityIcon} aria-hidden="true" />
              <h3 className={styles.clarityTitle}>פערים בעמדות ובכוונות</h3>
              <p className={styles.clarityDesc}>
                מצבים שבהם אחד מבני הזוג נוטה לסיום הקשר והשני מבקש הזדמנות, ויש צורך בשיח כן, רגיש וללא לחץ כדי לראות את התמונה המלאה.
              </p>
            </div>

            <div className={styles.clarityCard}>
              <FiShield className={styles.clarityIcon} aria-hidden="true" />
              <h3 className={styles.clarityTitle}>שמירה על כבוד ועל הילדים</h3>
              <p className={styles.clarityDesc}>
                הבנה שכל החלטה שתתקבל – שיקום הקשר או פרידה בהסכמה – חייבת להתבצע באחריות, בכבוד הדדי ובמניעת מלחמות מזיקות.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* 3 Step Pathway */}
      <section className={styles.section}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>שלושת השלבים בתהליך הבירור</h2>
            <p className={styles.sectionSubtitle}>
              תהליך מובנה ומאפשר שמעניק לכם בהירות ומתווה דרך להמשך.
            </p>
          </div>

          <div className={styles.stepsGrid}>
            <div className={styles.stepCard}>
              <div className={styles.stepNumber}>1</div>
              <h3 className={styles.stepTitle}>בירור צרכים ועמדות</h3>
              <p className={styles.stepDesc}>
                מיפוי הרגשות, הקשיים והציפיות של כל צד במרחב ניטרלי, המאפשר לכל אחד להציג את נקודת מבטו ללא מתקפות.
              </p>
            </div>

            <div className={styles.stepCard}>
              <div className={styles.stepNumber}>2</div>
              <h3 className={styles.stepTitle}>בחינת מרחב השינוי</h3>
              <p className={styles.stepDesc}>
                בדיקה כנה של התנאים הנדרשים לשיקום הקשר לעומת המשמעויות של פרידה, תוך בחינת היכולת לייצר הסכמות מעשיות.
              </p>
            </div>

            <div className={styles.stepCard}>
              <div className={styles.stepNumber}>3</div>
              <h3 className={styles.stepTitle}>בחירת הנתיב הנכון</h3>
              <p className={styles.stepDesc}>
                החלטה מודעת ומשותפת: יציאה לתהליך ייעוץ זוגי לשיקום הקשר, או מעבר לתהליך גישור מכבד ורגוע לבניית הסכמות.
              </p>
            </div>
          </div>

          {/* Non-legal Disclaimer */}
          <div className={styles.disclaimerBox}>
            <FiInfo className={styles.disclaimerIcon} aria-hidden="true" />
            <p className={styles.disclaimerText}>
              <strong>הבהרה מקצועית:</strong> המפגש מיועד לבירור זוגי, רגשי ותקשורתי ואינו מהווה ייעוץ משפטי או חוות דעת משפטית. שירה סהרוני היא יועצת זוגית ומגשרת מוסמכת (עורכת דין בהכשרתה). במידת הצורך בייצוג משפטי או עריכת הסכמים משפטיים פורמליים, מומלץ לפנות לעו״ד מייצג.
            </p>
          </div>
        </div>
      </section>

      {/* Bio Section */}
      <section className={styles.sectionAlt}>
        <div className="container">
          <div className={styles.bioCard}>
            <div className={styles.bioHeader}>
              <img
                src="/images/shira-saharoni.webp"
                alt="שירה סהרוני - יועצת זוגית ומגשרת מוסמכת"
                className={styles.bioAvatar}
                width="90"
                height="90"
                loading="lazy"
              />
              <div>
                <h2 className={styles.bioName}>שירה סהרוני</h2>
                <p className={styles.bioRole}>יועצת זוגית, מנחת הורים ומגשרת מוסמכת</p>
              </div>
            </div>

            <p className={styles.bioText}>
              בעלת רקע משפטי כעורכת דין בהכשרתי, בחרתי להתמקד בעולמות ההנחיה, הייעוץ הזוגי והגישור. אני פוגשת זוגות ברגעי ההכרעה הרגישים ביותר ומסייעת להם לייצר שקט ובהירות. הניסיון מלמד כי שיח רגוע ומובנה בצומת החלטה חוסך כאב רב, מאפשר הבנה עמוקה ומגן על עתיד המשפחה.
            </p>

            <div className={styles.credentialsList}>
              <span className={styles.credentialPill}>✓ יועצת זוגית מוסמכת</span>
              <span className={styles.credentialPill}>✓ מגשרת מוסמכת</span>
              <span className={styles.credentialPill}>✓ מנחת הורים מוסמכת</span>
              <span className={styles.credentialPill}>✓ עורכת דין בהכשרתה</span>
              <span className={styles.credentialPill}>✓ קליניקה באשדוד ובזום</span>
            </div>
          </div>
        </div>
      </section>

      {/* Transparent Pricing Card */}
      <section className={styles.section}>
        <div className="container">
          <div className={styles.priceCard}>
            <h2 className={styles.priceTitle}>פגישת בירור וייעוץ זוגי</h2>
            <div className={styles.priceAmount}>500 ₪</div>
            <p className={styles.priceNote}>
              לפגישה בת 50 דקות מלאות (כולל מע״מ כחוק). ללא תשלום מראש וללא התחייבות להמשך תהליך.
            </p>
          </div>

          {/* Booking Embed Section */}
          <div ref={bookingRef} className={styles.bookingContainer}>
            <div className={styles.sectionHeader}>
              <h2 className={styles.sectionTitle}>קביעת מועד לפגישה</h2>
              <p className={styles.sectionSubtitle}>
                בחרו את המועד המתאים לכם ביומן לפגישת בירור וייעוץ באשדוד או אונליין בזום.
              </p>
            </div>

            <CalendlyBookingEmbed
              ariaLabel="לוח זמנים לקביעת פגישת בירור וייעוץ זוגי עם שירה סהרוני"
              bookingPagePath="/services/couples/before-separation"
              serviceType="couples_before_separation"
              landingPageType="before_separation"
            />
          </div>
        </div>
      </section>

      {/* FAQ Section */}
      <section className={styles.sectionAlt}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>שאלות נפוצות על צומת החלטה זוגי</h2>
          </div>

          <div className={styles.faqList}>
            {FAQS.map((faq, index) => (
              <div key={faq.q} className={styles.faqItem}>
                <button
                  type="button"
                  className={styles.faqQuestion}
                  onClick={() => toggleFaq(index)}
                  aria-expanded={openFaq === index}
                >
                  <span>{faq.q}</span>
                  {openFaq === index ? <FiChevronUp aria-hidden="true" /> : <FiChevronDown aria-hidden="true" />}
                </button>
                {openFaq === index && (
                  <div className={styles.faqAnswer}>
                    <p>{faq.a}</p>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Minimal Footer */}
      <footer className={styles.footer}>
        <div className="container">
          <div className={styles.footerLinks}>
            <a href="/">דף הבית</a>
            <a href="/about">אודות</a>
            <a href="/services/couples">ייעוץ זוגי</a>
            <a href="/services/mediation">גישור</a>
            <a href="/faq">שאלות נפוצות</a>
            <a href="/privacy">מדיניות פרטיות</a>
            <a href="/accessibility">הצהרת נגישות</a>
          </div>
          <p>© {new Date().getFullYear()} שירה סהרוני. כל הזכויות שמורות.</p>
        </div>
      </footer>

      {/* Mobile Sticky Bar */}
      {!isBookingInView && (
        <div className={styles.mobileStickyBar}>
          <a
            href={whatsappUrl}
            target="_blank"
            rel="noopener noreferrer"
            className={styles.mobileStickyWhatsappBtn}
            onClick={() => {
              trackSecondaryCtaClick('WhatsApp סרגל מובייל', 'mobile_sticky');
              trackWhatsappClick();
            }}
            aria-label="הודעה ב-WhatsApp לשירה סהרוני"
          >
            <FaWhatsapp aria-hidden="true" />
            <span>WhatsApp</span>
          </a>
          <button
            type="button"
            className={styles.mobileStickyBtn}
            onClick={() => scrollToBooking('mobile_sticky')}
          >
            <FiCheckCircle aria-hidden="true" />
            <span>קביעת פגישה – 500 ₪</span>
          </button>
        </div>
      )}
    </main>
  );
};

export default CouplesBeforeSeparationPage;
