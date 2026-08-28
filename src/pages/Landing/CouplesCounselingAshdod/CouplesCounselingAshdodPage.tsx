import React, { useEffect, useState } from 'react';
import { FaPhone, FaWhatsapp } from 'react-icons/fa';
import {
  FiCalendar,
  FiCheckCircle,
  FiClock,
  FiHeart,
  FiLock,
  FiMapPin,
  FiShield,
} from 'react-icons/fi';
import CalendlyBookingEmbed from '../../../components/Booking/CalendlyBookingEmbed';
import MetaTags from '../../../components/SEO/MetaTags';
import SchemaOrg from '../../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../../constants/siteConfig';
import { useLandingPageAnalytics } from '../../../hooks/useLandingPageAnalytics';
import styles from './CouplesCounselingAshdodPage.module.css';

const timelineSteps = [
  {
    time: '00–15 דק׳',
    title: 'מתחילים ממה שקורה עכשיו',
    desc: 'מבינים מה מביא אתכם לפגישה. כל אחד מקבל מקום לתאר איך הוא חווה את המצב ומה היה רוצה שייראה אחרת. המטרה היא ליצור תמונה משותפת — לא להכריע בין שתי גרסאות.',
  },
  {
    time: '15–35 דק׳',
    title: 'מזהים מה קורה כשהשיחה מסתבכת',
    desc: 'בודקים איך מתחילות השיחות שמסתיימות שוב באותו מקום, איפה נוצרת התגוננות או התרחקות ואיזה דפוס חוזר ביניכם גם כששניכם התכוונתם למשהו אחר.',
  },
  {
    time: '35–50 דק׳',
    title: 'יוצאים עם כיוון מעשי ראשון',
    desc: 'בוחרים דרך אחת שאפשר להתחיל לתרגל — למשל איך לפתוח שיחה אחרת, לעצור הסלמה או להקשיב לפני שמגיבים.',
  },
];

const faqItems = [
  {
    question: 'מה קורה בפגישה הראשונה?',
    answer: 'הפגישה הראשונה מיועדת להבין מה מעסיק אתכם, לשמוע את נקודת המבט של שני בני הזוג ולזהות את דפוסי השיחה שחוזרים ביניכם. המטרה היא להתחיל לעשות סדר ולבחון כיוון מעשי להמשך.',
  },
  {
    question: 'האם חייבים להגיע יחד?',
    answer: 'מומלץ להגיע יחד לפגישה הזוגית, משום שהייעוץ מתמקד בתקשורת ובדפוסים שבין בני הזוג. אם יש התלבטות או שאלה לפני הפגישה, אפשר להתייעץ מראש עם שירה.',
  },
  {
    question: 'מה אם בן או בת הזוג עדיין לא בטוחים לגבי ייעוץ?',
    answer: 'לא צריך להגיע מתוך הסכמה על מי צודק או מתוך אותה נקודת מבט על הבעיה. המטרה היא לא לבחור צד, אלא להבין מה קורה ביניכם כשהשיחה מסתבכת ולבדוק דרך אחרת לנהל אותה. אם יש חשש מסוים לפני שקובעים, אפשר לכתוב לשירה ב־WhatsApp ולשאול.',
  },
  {
    question: 'כמה זמן נמשכת פגישה?',
    answer: 'פגישת ייעוץ נמשכת 50 דקות.',
  },
  {
    question: 'האם אפשר לקיים את הפגישה אונליין?',
    answer: 'כן. לצד הפגישות בקליניקה באשדוד, קיימת אפשרות לקיים פגישה אונליין.',
  },
  {
    question: 'איפה מתקיימות הפגישות?',
    answer: 'הפגישות הפרונטליות מתקיימות בקליניקה באשדוד.',
  },
  {
    question: 'מה מחיר הפגישה?',
    answer: 'מחיר פגישת ייעוץ הוא 500 ₪.',
  },
  {
    question: 'איך קובעים פגישה?',
    answer: 'לוחצים על "קביעת פגישה", בוחרים מועד פנוי ביומן ומשלימים את ההזמנה. אם לא מצאתם מועד מתאים או שיש לכם שאלה לפני ההזמנה, אפשר לפנות לשירה ב־WhatsApp.',
  },
  {
    question: 'האם השיחה דיסקרטית?',
    answer: 'הפגישות מתקיימות במרחב פרטי ומכבד, בהתאם לכללי האתיקה המקצועית. מידע נוסף על אופן הטיפול בפרטים שנמסרים באתר מופיע במדיניות הפרטיות.',
  },
  {
    question: 'האם צריך להתחייב לתהליך ארוך?',
    answer: 'לא. אין מספר קבוע של פגישות שמתאים לכל זוג. לאחר הפגישה הראשונה אפשר להעריך יחד את הצרכים ואת דרך ההמשך.',
  },
];

const schemaData = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'ProfessionalService',
      '@id': `${SITE_CONFIG.url}/couples-counseling-ashdod#service`,
      name: 'ייעוץ זוגי באשדוד | שירה סהרוני',
      url: `${SITE_CONFIG.url}/couples-counseling-ashdod`,
      image: `${SITE_CONFIG.url}/images/shira-saharoni.webp`,
      telephone: SITE_CONFIG.contact.phone,
      email: SITE_CONFIG.contact.email,
      priceRange: '₪500',
      description: 'ייעוץ זוגי מעשי וממוקד באשדוד או אונליין. הבנת דפוסי שיחה שחוזרים, תרגול תקשורת וכלים מעשיים להתמודדות עם מחלוקות.',
      address: {
        '@type': 'PostalAddress',
        addressLocality: 'אשדוד',
        addressCountry: 'IL',
      },
      provider: {
        '@type': 'LocalBusiness',
        '@id': `${SITE_CONFIG.url}/#business`,
      },
      areaServed: [
        {
          '@type': 'City',
          name: 'אשדוד',
        },
        {
          '@type': 'Country',
          name: 'ישראל (אונליין)',
        },
      ],
    },
    {
      '@type': 'BreadcrumbList',
      itemListElement: [
        {
          '@type': 'ListItem',
          position: 1,
          name: 'עמוד הבית',
          item: SITE_CONFIG.url,
        },
        {
          '@type': 'ListItem',
          position: 2,
          name: 'ייעוץ זוגי באשדוד',
          item: `${SITE_CONFIG.url}/couples-counseling-ashdod`,
        },
      ],
    },
    {
      '@type': 'FAQPage',
      mainEntity: faqItems.map((item) => ({
        '@type': 'Question',
        name: item.question,
        acceptedAnswer: {
          '@type': 'Answer',
          text: item.answer,
        },
      })),
    },
  ],
};

type VariantId = 'A' | 'B' | 'C';

const copyVariants: Record<VariantId, { h1: string; subtitle: string }> = {
  A: {
    h1: 'כשהשיחות חוזרות שוב ושוב לאותו ריב — אפשר ללמוד לדבר אחרת',
    subtitle: 'אם כל ניסיון לדבר נגמר שוב בוויכוח, בהתגוננות או בשתיקה, אפשר לעצור ולבדוק מה קורה ביניכם. בייעוץ זוגי ממוקד נבין את הדפוס שחוזר בשיחות ונתרגל דרך אחרת לדבר ולהתמודד עם מחלוקות — בלי לחפש מי אשם ומי צודק.',
  },
  B: {
    h1: 'לעצור את מעגל הריבים, להבין מה קורה ביניכם ולבנות דרך אחרת לדבר',
    subtitle: 'ייעוץ זוגי מסודר שמתמקד במה שקורה בשיחות שלכם עכשיו: מזהים את הדפוס שחוזר, מבינים איפה השיחה מסתבכת ומתרגלים כלים מעשיים שאפשר לקחת הביתה.',
  },
  C: {
    h1: 'גם כשכבר קשה לדבר בלי להיפגע — אפשר ליצור שיחה אחרת ביניכם',
    subtitle: 'כשיש עדיין רצון להבין, להתקרב או פשוט להפסיק לחזור שוב לאותו ויכוח, ייעוץ זוגי ממוקד יכול לעזור לעשות סדר במה שקורה ולבחון דרך אחרת להתמודד עם הרגעים הקשים.',
  },
};

const CouplesCounselingAshdodPage: React.FC = () => {
  const [isBookingInView, setIsBookingInView] = useState(false);
  const [variantId] = useState<VariantId>(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const v = (params.get('variant') || '').toUpperCase() as VariantId;
      if (v === 'B' || v === 'C') return v;
    }
    return 'A';
  });

  const {
    trackCtaClick,
    trackSecondaryCtaClick,
    trackPhoneClick,
    trackWhatsappClick,
  } = useLandingPageAnalytics(variantId);

  const whatsappMessage = encodeURIComponent(
    'היי שירה, הגעתי לעמוד הייעוץ הזוגי באשדוד ויש לי שאלה לפני שקובעים פגישה.',
  );
  const whatsappUrl = `https://wa.me/${SITE_CONFIG.contact.whatsapp}?text=${whatsappMessage}`;

  const scrollToBooking = (location: string) => {
    trackCtaClick('קביעת פגישה', location);
    const bookingEl = document.getElementById('booking');
    if (bookingEl) {
      bookingEl.scrollIntoView({ behavior: 'smooth' });
    }
  };

  const trackFaqInteraction = (index: number) => {
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({
      event: 'faq_interaction',
      faq_index: index,
      variant_id: variantId,
      landing_page_path: '/couples-counseling-ashdod',
      landing_page_type: 'ashdod',
      service_type: 'couples_counseling',
    });
  };

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          setIsBookingInView(entry.isIntersecting);
        });
      },
      { threshold: 0.1 },
    );

    const bookingEl = document.getElementById('booking');
    if (bookingEl) {
      observer.observe(bookingEl);
    }

    return () => {
      if (bookingEl) observer.unobserve(bookingEl);
    };
  }, []);

  return (
    <main id="main-content" className={styles.page} dir="rtl">
      <MetaTags
        title="ייעוץ זוגי באשדוד | שירה סהרוני"
        description="ייעוץ זוגי מעשי וממוקד באשדוד או אונליין. כשאותם ריבים ודפוסי שיחה חוזרים שוב ושוב, אפשר להבין מה קורה ולתרגל דרך אחרת לדבר. פגישה של 50 דקות, 500 ₪."
        canonical={`${SITE_CONFIG.url}/couples-counseling-ashdod`}
        image="/images/shira-saharoni.webp"
      />
      <SchemaOrg data={schemaData} />

      <header className={styles.header}>
        <div className={`container ${styles.headerInner}`}>
          <a href="/" className={styles.brand} aria-label="לדף הבית של שירה סהרוני">
            <div className={styles.brandText}>
              <span className={styles.brandTitle}>שירה סהרוני</span>
              <span className={styles.brandSubtitle}>קשר | ייעוץ זוגי באשדוד</span>
            </div>
          </a>
          <div className={styles.headerActions}>
            <a
              href={`tel:${SITE_CONFIG.contact.phone.replace(/-/g, '')}`}
              className={styles.phoneCallBtn}
              onClick={trackPhoneClick}
              aria-label="חיוג לשירה סהרוני"
            >
              <FaPhone aria-hidden="true" />
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

      <section className={styles.heroSection} aria-labelledby="couples-ashdod-title">
        <div className={`container ${styles.heroGrid}`}>
          <div className={styles.heroContent}>
            <div className={styles.heroTag}>
              <FiHeart aria-hidden="true" />
              <span>ייעוץ זוגי מעשי וממוקד באשדוד ובאונליין</span>
            </div>
            <h1 id="couples-ashdod-title" className={styles.heroTitle}>
              {copyVariants[variantId].h1}
            </h1>
            <p className={styles.heroSubtitle}>
              {copyVariants[variantId].subtitle}
            </p>

            <div className={styles.heroCtas}>
              <button
                type="button"
                className={styles.btnPrimary}
                onClick={() => scrollToBooking('hero_primary')}
              >
                קביעת פגישה
              </button>
              <a
                href={whatsappUrl}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.btnSecondary}
                onClick={() => {
                  trackSecondaryCtaClick('יש לי שאלה לפני שקובעים', 'hero_secondary');
                  trackWhatsappClick();
                }}
              >
                <FaWhatsapp aria-hidden="true" />
                יש לי שאלה לפני שקובעים
              </a>
            </div>

            <div className={styles.trustPoints} aria-label="פרטי הפגישה">
              <div className={styles.trustPoint}>
                <FiClock className={styles.trustIcon} aria-hidden="true" />
                <span>50 דקות</span>
              </div>
              <div className={styles.trustPoint}>
                <FiCheckCircle className={styles.trustIcon} aria-hidden="true" />
                <span>500 ₪</span>
              </div>
              <div className={styles.trustPoint}>
                <FiMapPin className={styles.trustIcon} aria-hidden="true" />
                <span>קליניקה באשדוד או אונליין</span>
              </div>
              <div className={styles.trustPoint}>
                <FiLock className={styles.trustIcon} aria-hidden="true" />
                <span>מרחב פרטי ומכבד</span>
              </div>
            </div>
          </div>

          <div className={styles.heroImageWrapper}>
            <img
              src="/images/shira-saharoni.webp"
              alt="שירה סהרוני, יועצת זוגית באשדוד"
              className={styles.heroImage}
              width="1271"
              height="1280"
              fetchPriority="high"
            />
            <div className={styles.heroImageBadge}>
              שירה סהרוני | יועצת זוגית ומנחת הורים
            </div>
          </div>
        </div>
      </section>

      <section className={styles.sectionAlt} aria-labelledby="recognition-title">
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2 id="recognition-title">כשהבעיה כבר לא היא על מה רבים — אלא איך השיחה מתנהלת</h2>
            <p>
              לפעמים זה מתחיל ממשהו קטן. מנסים להסביר משהו חשוב, ותוך כמה דקות שוב נמצאים בדיוק באותו ויכוח. לפעמים כבר מעדיפים לא לפתוח נושאים מסוימים, רק כדי לא להיכנס שוב לאותו מעגל.
            </p>
          </div>
          <div className={styles.identificationGrid}>
            <div className={styles.identCard}>
              <div className={styles.identIcon} aria-hidden="true">↻</div>
              <p>הנושא משתנה, אבל השיחה כמעט תמיד מגיעה לאותו מקום.</p>
            </div>
            <div className={styles.identCard}>
              <div className={styles.identIcon} aria-hidden="true">↔</div>
              <p>ככל שאחד מנסה להסביר יותר, השני נסגר, מתרחק או מתגונן.</p>
            </div>
            <div className={styles.identCard}>
              <div className={styles.identIcon} aria-hidden="true">!</div>
              <p>שיחה שהתחילה בעניין יומיומי הופכת מהר מאוד למאבק.</p>
            </div>
            <div className={styles.identCard}>
              <div className={styles.identIcon} aria-hidden="true">…</div>
              <p>מדברים על הבית, הילדים והמשימות — אבל פחות על מה שקורה ביניכם.</p>
            </div>
            <div className={styles.identCard}>
              <div className={styles.identIcon} aria-hidden="true">○</div>
              <p>יש דברים שכבר לא מעלים, כי לא רוצים עוד ערב של מתח.</p>
            </div>
            <div className={styles.identCard}>
              <div className={styles.identIcon} aria-hidden="true">→</div>
              <p>רוצים שיהיה אחרת, אבל לא יודעים איך לצאת מהדפוס שנוצר.</p>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.section} aria-labelledby="hope-title">
        <div className="container">
          <div className={styles.localBox}>
            <h2 id="hope-title">לא צריך לפתור את כל הזוגיות בשיחה אחת</h2>
            <p>
              אפשר להתחיל ממשהו פשוט יותר: לעצור רגע את הדפוס שחוזר ביניכם, להבין מה קורה בשיחה לפני שהיא הופכת לעימות, ולתרגל דרך אחרת להגיב, להקשיב ולדבר.
            </p>
            <p>
              המטרה אינה לייצר זוגיות בלי מחלוקות. המטרה היא ללמוד לנהל את המחלוקות בצורה שמאפשרת לשניכם להישאר בשיחה.
            </p>
            <button
              type="button"
              className={styles.btnPrimary}
              onClick={() => scrollToBooking('hope')}
            >
              קביעת פגישה
            </button>
          </div>
        </div>
      </section>

      <section className={styles.sectionAlt} aria-labelledby="process-title">
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2 id="process-title">דרך מסודרת להבין מה קורה ולנסות משהו אחרת</h2>
            <p>
              הייעוץ מתמקד במה שקורה ביניכם עכשיו ובצעדים שאפשר לבחון בחיים עצמם.
            </p>
          </div>

          <div className={styles.stepsGrid}>
            <article className={styles.stepCard}>
              <span className={styles.stepNumber}>שלב 1</span>
              <h3>מתחילים במה שקורה עכשיו</h3>
              <p>ממפים את הקושי ואת הרגעים שבהם השיחה נתקעת או הופכת למתוחה.</p>
            </article>
            <article className={styles.stepCard}>
              <span className={styles.stepNumber}>שלב 2</span>
              <h3>מבינים את הדפוס</h3>
              <p>מזהים מה מפעיל כל אחד ומה גורם לשיחה לחזור שוב לאותו מקום.</p>
            </article>
            <article className={styles.stepCard}>
              <span className={styles.stepNumber}>שלב 3</span>
              <h3>מתרגלים דרך אחרת</h3>
              <p>בוחרים כלים מעשיים שאפשר לנסות בבית ולבדוק מה עוזר ומה עדיין דורש דיוק.</p>
            </article>
          </div>

          <div className={styles.sessionsNote}>
            אין מספר קבוע של פגישות שמתאים לכל זוג. דרך ההמשך נקבעת לפי מה שעולה בפגישה ולפי הצרכים שלכם.
          </div>
        </div>
      </section>

      <section className={styles.section} aria-labelledby="about-shira-title">
        <div className={`container ${styles.aboutGrid}`}>
          <div className={styles.aboutImageWrapper}>
            <img
              src="/images/shira-saharoni.webp"
              alt="שירה סהרוני"
              className={styles.aboutImage}
              width="1271"
              height="1280"
              loading="lazy"
              decoding="async"
            />
          </div>
          <div className={styles.aboutContent}>
            <h2 id="about-shira-title">כדי לדבר על הדברים הכי רגישים, צריך להרגיש שיש מקום לשני הצדדים</h2>
            <span className={styles.aboutRole}>שירה סהרוני | יועצת זוגית ומנחת הורים</span>
            <p>
              הגישה של שירה משלבת הקשבה לשתי נקודות המבט, הסתכלות מסודרת על מה שקורה בין בני הזוג וכלים מעשיים שאפשר לקחת גם לחיים בבית.
            </p>
            <p>
              המטרה אינה לקבוע מי צודק, אלא לעזור לכם להבין את הדפוס שנוצר ביניכם, לפרק שיחות עמוסות למשהו שאפשר להבין ולעבוד איתו, ולבחון דרך תקשורת מכבדת ומועילה יותר.
            </p>
            <ul className={styles.fitList}>
              <li>מקום לשתי נקודות המבט</li>
              <li>בהירות וסדר במקום שיחה שמסתבכת</li>
              <li>כלים מעשיים שאפשר לתרגל גם בבית</li>
            </ul>
          </div>
        </div>
      </section>

      <section className={styles.timelineSection} aria-labelledby="first-session-title">
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2 id="first-session-title">מה קורה ב־50 הדקות של הפגישה הראשונה?</h2>
            <p>
              50 דקות ממוקדות שנותנות מקום לשני בני הזוג ומאפשרות להתחיל לעשות סדר במה שקורה ביניכם. לא מגיעים כדי להוכיח מי צודק.
            </p>
          </div>

          <div className={styles.timelineGrid}>
            {timelineSteps.map((step) => (
              <article key={step.time} className={styles.timelineCard}>
                <div className={styles.timeBadge}>{step.time}</div>
                <h3>{step.title}</h3>
                <p>{step.desc}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className={styles.sectionAlt} aria-labelledby="partner-objection-title">
        <div className="container">
          <div className={styles.localBox}>
            <h2 id="partner-objection-title">ומה אם אחד מאיתנו פחות רוצה להגיע?</h2>
            <p>
              זה לא חריג שאחד מבני הזוג יוזם את הפנייה והשני פחות משוכנע. לפעמים עצם הרעיון של ייעוץ זוגי מעלה חשש שיחליטו מי צודק, שיצביעו על אחד מכם כבעיה או שתיכנסו לתהליך ארוך בלי לדעת לאן הוא הולך.
            </p>
            <p>
              זו לא מטרת הפגישה. המטרה היא להבין מה קורה ביניכם כשהשיחה מסתבכת, לתת מקום לשתי נקודות המבט ולבדוק אם אפשר לנהל את אותם רגעים בצורה אחרת.
            </p>
            <a
              href={whatsappUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={styles.btnSecondary}
              onClick={() => {
                trackSecondaryCtaClick('יש לי שאלה לפני שקובעים', 'partner_objection');
                trackWhatsappClick();
              }}
            >
              <FaWhatsapp aria-hidden="true" />
              יש לי שאלה לפני שקובעים
            </a>
          </div>
        </div>
      </section>

      <section className={styles.section} aria-labelledby="trust-title">
        <div className="container">
          <div className={styles.localBox}>
            <h2 id="trust-title">מה חשוב לדעת לפני שמגיעים</h2>
            <div className={styles.localFeatures}>
              <div className={styles.localBadge}>
                <FiHeart aria-hidden="true" />
                <span>מקום לשני בני הזוג</span>
              </div>
              <div className={styles.localBadge}>
                <FiCheckCircle aria-hidden="true" />
                <span>גישה ממוקדת ומעשית</span>
              </div>
              <div className={styles.localBadge}>
                <FiMapPin aria-hidden="true" />
                <span>קליניקה באשדוד</span>
              </div>
              <div className={styles.localBadge}>
                <FiClock aria-hidden="true" />
                <span>אפשרות לפגישה אונליין</span>
              </div>
              <div className={styles.localBadge}>
                <FiLock aria-hidden="true" />
                <span>מרחב פרטי ומכבד</span>
              </div>
            </div>
          </div>

          <div className={styles.fitGrid}>
            <div className={styles.cautionCard}>
              <h3>
                <FiShield aria-hidden="true" />
                מתי נדרש מענה אחר?
              </h3>
              <p>
                במצבים הכוללים סכנה מיידית, אלימות, איום, משבר נפשי חריף או צורך באבחון ובטיפול קליני, יש לפנות לגורם חירום או לאיש מקצוע טיפולי מתאים.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.sectionAlt} aria-labelledby="practical-title">
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2 id="practical-title">כל מה שצריך לדעת לפני שקובעים</h2>
            <p>המחיר, משך הפגישה ואופן הקביעה מוצגים מראש כדי שתדעו למה לצפות.</p>
          </div>

          <div className={styles.detailsCard}>
            <div className={styles.priceTag}>500 ₪</div>
            <div className={styles.detailsList}>
              <div className={styles.detailsItem}>
                <strong>מחיר הפגישה:</strong>
                <span>500 ₪</span>
              </div>
              <div className={styles.detailsItem}>
                <strong>משך הפגישה:</strong>
                <span>50 דקות</span>
              </div>
              <div className={styles.detailsItem}>
                <strong>מיקום:</strong>
                <span>קליניקה באשדוד</span>
              </div>
              <div className={styles.detailsItem}>
                <strong>אפשרות נוספת:</strong>
                <span>פגישה אונליין</span>
              </div>
              <div className={styles.detailsItem}>
                <strong>קביעת מועד:</strong>
                <span>בוחרים מועד פנוי ביומן באתר ומשלימים את ההזמנה</span>
              </div>
              <div className={styles.detailsItem}>
                <strong>שינוי או ביטול:</strong>
                <span>באמצעות הקישור שמתקבל באישור ההזמנה</span>
              </div>
            </div>
          </div>

          <div className={styles.sessionsNote}>
            אין צורך להתחייב מראש למספר קבוע של פגישות. אחרי הפגישה הראשונה אפשר להבין יחד מה נכון להמשך.
          </div>
        </div>
      </section>

      <section className={styles.section} aria-labelledby="faq-title">
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2 id="faq-title">שאלות שכדאי לדעת עליהן לפני הפגישה</h2>
          </div>
          <div className={styles.faqAccordion}>
            {faqItems.map((item, index) => (
              <div key={item.question} className={styles.faqItem}>
                <details
                  onToggle={(event) => {
                    if (event.currentTarget.open) trackFaqInteraction(index);
                  }}
                >
                  <summary>{item.question}</summary>
                  <p className={styles.faqAnswer}>{item.answer}</p>
                </details>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="booking" className={`${styles.sectionAlt} ${styles.bookingSection}`} aria-labelledby="booking-title">
        <div className="container">
          <div className={styles.sectionHeader}>
            <FiCalendar aria-hidden="true" style={{ fontSize: '2rem', color: 'var(--color-accent)' }} />
            <h2 id="booking-title">אפשר להתחיל מפגישה אחת מסודרת</h2>
            <p>
              אם השיחות חוזרות שוב לאותו מקום ואתם רוצים לבדוק דרך אחרת להתמודד עם זה, אפשר לבחור מועד לפגישת ייעוץ. 50 דקות · 500 ₪ · אשדוד או אונליין.
            </p>
          </div>

          <div className={styles.calendlyWrapper}>
            <CalendlyBookingEmbed
              ariaLabel="לוח זמנים לקביעת פגישת ייעוץ זוגי באשדוד עם שירה סהרוני"
              serviceType="couples_counseling"
              bookingPagePath="/couples-counseling-ashdod"
              landingPageType="ashdod"
              variantId={variantId}
              value={500}
              currency="ILS"
            />
          </div>

          <div className={styles.bookingHelp}>
            <span>לא בטוחים לגבי משהו לפני ההזמנה?</span>
            <a
              href={whatsappUrl}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => {
                trackSecondaryCtaClick('יש לי שאלה לפני שקובעים', 'booking_help');
                trackWhatsappClick();
              }}
            >
              <FaWhatsapp aria-hidden="true" />
              יש לי שאלה לפני שקובעים
            </a>
          </div>
        </div>
      </section>

      <section className={styles.closingCta} aria-labelledby="closing-title">
        <div className="container">
          <h2 id="closing-title">לא חייבים לדעת כבר עכשיו איך לפתור הכול</h2>
          <p>מספיק להתחיל מלהבין מה קורה בשיחות שלכם — ולבדוק אם אפשר לעשות משהו אחרת.</p>
          <button
            type="button"
            className={styles.btnPrimary}
            onClick={() => scrollToBooking('closing_cta')}
          >
            קביעת פגישה
          </button>
        </div>
      </section>

      <footer className={styles.footer}>
        <div className={`container ${styles.footerGrid}`}>
          <div className={styles.footerBrand}>שירה סהרוני — קשר</div>
          <div className={styles.footerContact}>
            <a href={`tel:${SITE_CONFIG.contact.phone.replace(/-/g, '')}`} onClick={trackPhoneClick}>
              טלפון: {SITE_CONFIG.contact.phone}
            </a>
            <a href={`mailto:${SITE_CONFIG.contact.email}`}>
              דוא״ל: {SITE_CONFIG.contact.email}
            </a>
            <span>ייעוץ זוגי באשדוד / אונליין</span>
          </div>
          <div className={styles.footerLinks}>
            <a href="/privacy">מדיניות פרטיות</a>
            <a href="/accessibility">הצהרת נגישות</a>
            <a href="/terms">תנאי שימוש</a>
            <a href="/">לדף הבית של האתר</a>
          </div>
          <div className={styles.copyright}>
            © {new Date().getFullYear()} שירה סהרוני. כל הזכויות שמורות.
          </div>
        </div>
      </footer>

      {!isBookingInView && (
        <div className={styles.mobileStickyBar}>
          <button
            type="button"
            className={styles.mobileStickyBtn}
            onClick={() => scrollToBooking('mobile_sticky')}
          >
            <FiCheckCircle aria-hidden="true" />
            קביעת פגישה
          </button>
        </div>
      )}
    </main>
  );
};

export default CouplesCounselingAshdodPage;
