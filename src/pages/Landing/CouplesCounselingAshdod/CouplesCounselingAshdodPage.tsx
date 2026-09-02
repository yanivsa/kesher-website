import React, { useEffect, useState } from 'react';
import { FaPhone, FaWhatsapp } from 'react-icons/fa';
import {
  FiCalendar,
  FiCheckCircle,
  FiClock,
  FiHeart,
  FiLock,
  FiMapPin,
  FiUserCheck,
} from 'react-icons/fi';
import CalendlyBookingEmbed from '../../../components/Booking/CalendlyBookingEmbed';
import MetaTags from '../../../components/SEO/MetaTags';
import SchemaOrg from '../../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../../constants/siteConfig';
import { useLandingPageAnalytics } from '../../../hooks/useLandingPageAnalytics';
import styles from './CouplesCounselingAshdodPage.module.css';

type VariantId = 'A' | 'B' | 'C';

const copyVariants: Record<VariantId, { eyebrow: string; h1: string; subtitle: string }> = {
  A: {
    eyebrow: 'ייעוץ זוגי באשדוד / אונליין',
    h1: 'כשהשיחות חוזרות שוב ושוב לאותו ריב — אפשר ללמוד לדבר אחרת',
    subtitle: 'אם כל ניסיון לדבר נגמר בוויכוח, בהתגוננות או בשתיקה — אפשר לעצור ולהבין מה קורה ביניכם. תהליך מעשי וממוקד לזיהוי הדפוס שחוזר ביחסים, הפחתת הסלמה ולמידת דרך אחרת לדבר ולהקשיב.',
  },
  B: {
    eyebrow: 'ייעוץ זוגי באשדוד | תהליך ממוקד ומעשי',
    h1: 'לעצור את מעגל הריבים, להבין מה קורה ביניכם ולבנות דרך אחרת לדבר',
    subtitle: 'ייעוץ זוגי מסודר שמתמקד במה שקורה בשיחות שלכם עכשיו: מזהים את הדפוס שחוזר, מבינים איפה השיחה מסתבכת ומתרגלים כלים מעשיים שאפשר לקחת הביתה.',
  },
  C: {
    eyebrow: 'ייעוץ זוגי באשדוד ובאונליין',
    h1: 'גם כשכבר קשה לדבר בלי להיפגע — אפשר ליצור שיחה אחרת ביניכם',
    subtitle: 'כשיש עדיין רצון להבין, להתקרב או פשוט להפסיק לחזור שוב לאותו ויכוח, ייעוץ זוגי ממוקד יכול לעזור לעשות סדר במה שקורה ולבחון דרך אחרת להתמודד עם הרגעים הקשים.',
  },
};

const recognitionItems = [
  {
    title: 'שוב אותו ויכוח',
    desc: 'הנושא משתנה, אבל השיחה כמעט תמיד מגיעה לאותה נקודת פיצוץ או תסכול.',
  },
  {
    title: 'אחד מדבר, השני נסגר',
    desc: 'ככל שאחד מנסה להסביר ולהילחם על הקשר, השני מתרחק, מתגונן או משתתק.',
  },
  {
    title: 'ריחוק, עייפות ואובדן אמון',
    desc: 'התחושה שאין כוח לעוד שיחה עמוסה, והספקות מתחילים לחלחל עמוק יותר.',
  },
  {
    title: 'דברים קטנים מתפוצצים מהר',
    desc: 'שיחה שהתחילה בעניין יומיומי תמים הופכת במהירות למאבק על מי צודק.',
  },
  {
    title: 'מדברים על המשימות — לא על היחסים',
    desc: 'מתפקדים מעולה כצוות לניהול הבית והילדים, אבל חשים בדידות עמוקה בתוך הזוגיות.',
  },
  {
    title: 'רוצים שינוי, אבל מרגישים תקועים',
    desc: 'שניכם רוצים שיהיה אחרת, אבל לא יודעים איך לצאת מהדפוס השוחק שנוצר ביניכם.',
  },
];

const timelineSteps = [
  {
    time: 'שלב 1 | 00–15 דק׳',
    title: 'ממפים את דפוס השיחה ומבינים מה קורה',
    desc: 'נבין מה מביא אתכם לפגישה. כל אחד מקבל מקום בטוח להשמיע את נקודת מבטו. נמפה את דפוס השיחה שחוזר ביניכם בלי לחפש אשמים ובלי להכריע מי צודק.',
  },
  {
    time: 'שלב 2 | 15–35 דק׳',
    title: 'מזהים את נקודות ההסלמה ומפחיתים מתח',
    desc: 'נבדוק איפה השיחה מסתבכת, מה מפעיל את ההתגוננות והשתיקה, ואיך להאט את ההסלמה ברגע שהיא מתחילה כדי להחזיר את האפשרות לדבר.',
  },
  {
    time: 'שלב 3 | 35–50 דק׳',
    title: 'יוצאים עם צעד מעשי ראשון לבית',
    desc: 'נבחר תרגול מעשי אחד ממוקד — דרך שונה לפתוח שיחה, לעצור התדרדרות או להקשיב למה שנאמר מתחת לכעס — כדי לצאת עם כיוון ברור ליישום.',
  },
];

const faqItems = [
  {
    question: 'האם חייבים ששני בני הזוג יגיעו?',
    answer: 'מומלץ מאוד להגיע יחד משום שהייעוץ מתמקד בדפוסי השיחה והתקשורת שבין שני בני הזוג. אם צד אחד מתלבט, ניתן להגיע למפגש ראשוני לבירור והבנת התהליך.',
  },
  {
    question: 'מה אם אחד מבני הזוג לא רוצה טיפול?',
    answer: 'חשש או הסתייגות מפני טיפול הם טבעיים. המטרה בפגישה אינה לשפוט, להכריע מי אשם או לכפות תהליך ארוך, אלא להבין איפה השיחה נתקעת ולבדוק דרך מעשית להקל על המתח. אפשר גם לכתוב לשירה ב-WhatsApp ולהתייעץ לפני ההחלטה.',
  },
  {
    question: 'האם זה מתאים לפני החלטה על פרידה?',
    answer: 'כן. לפני שמקבלים החלטות כבדות או שמפרקים את הקשר, פגישת ייעוץ ובירור זוגי מציעה מרחב רגוע להבין אם ומה ניתן לשנות ביחסים, ולבחון את האפשרויות בבהירות ובאחריות.',
  },
  {
    question: 'האם הפגישה דיסקרטית?',
    answer: 'בהחלט. כל הפגישות והשיחות מתנהלות בדיסקרטיות מלאה, בסביבה פרטית, תומכת ומכבדת בהתאם לקוד האתי המקצועי.',
  },
  {
    question: 'האם אפשר אונליין?',
    answer: 'כן. לצד המפגשים הפרונטליים בקליניקה באשדוד, ניתן לקיים פגישות ייעוץ אונליין ב-Zoom מכל מקום.',
  },
  {
    question: 'כמה זמן נמשכת פגישה?',
    answer: 'פגישת ייעוץ זוגי נמשכת 50 דקות מלאות וממוקדות. המחיר הוא 500 ₪ כולל מע״מ.',
  },
  {
    question: 'איפה מתקיימות הפגישות?',
    answer: 'הפגישות הפרונטליות מתקיימות בקליניקה נעימה ונגישה באשדוד.',
  },
  {
    question: 'איך קובעים פגישה?',
    answer: 'ניתן ללחוץ על "קביעת פגישה", לבחור מועד פנוי ביומן ולהבטיח את המקום. לחלופין ניתן לפנות ישירות ב-WhatsApp לשיחה קצרה ודיסקרטית.',
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
      image: `${SITE_CONFIG.url}/images/shira-saharoni-sea.webp`,
      telephone: SITE_CONFIG.contact.phone,
      email: SITE_CONFIG.contact.email,
      priceRange: '₪500',
      description: 'ייעוץ זוגי ממוקד ומעשי באשדוד או אונליין. כשאותם ריבים ודפוסי שיחה חוזרים שוב ושוב, אפשר להבין מה קורה ולתרגל דרך אחרת לדבר. פגישה של 50 דקות, 500 ₪.',
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
    trackFaqInteraction,
  } = useLandingPageAnalytics(variantId);

  const whatsappMessage = encodeURIComponent(
    'היי שירה, הגעתי לעמוד ייעוץ זוגי באשדוד ויש לי שאלה לפני שקובעים.',
  );
  const whatsappUrl = `https://wa.me/${SITE_CONFIG.contact.whatsapp}?text=${whatsappMessage}`;

  const scrollToBooking = (location: string) => {
    trackCtaClick('קביעת פגישה', location);
    const bookingEl = document.getElementById('booking');
    if (bookingEl) {
      bookingEl.scrollIntoView({ behavior: 'smooth' });
    }
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
    <main id="main-content" className={styles.page}>
      <MetaTags
        title="ייעוץ זוגי באשדוד | שירה סהרוני – תקשורת זוגית וכלים מעשיים"
        description="ייעוץ זוגי באשדוד ואונליין. כשהשיחות חוזרות שוב ושוב לאותו ויכוח, מבינים את הדפוס ומתרגלים תקשורת אחרת. התחלה קצרה ודיסקרטית. 50 דקות, 500 ₪."
        canonical={`${SITE_CONFIG.url}/couples-counseling-ashdod`}
        image="/images/shira-saharoni-sea.webp"
      />
      <SchemaOrg data={schemaData} />

      {/* 1. Header מצומצם */}
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

      {/* 2. אזור Hero */}
      <section className={styles.heroSection} aria-labelledby="couples-ashdod-title">
        <div className={`container ${styles.heroGrid}`}>
          <div className={styles.heroContent}>
            <div className={styles.heroTag}>
              <FiHeart aria-hidden="true" />
              <span>{copyVariants[variantId].eyebrow}</span>
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
                className={styles.btnPrimaryBooking}
                onClick={() => scrollToBooking('hero_primary')}
              >
                קביעת פגישה
              </button>
              <a
                href={whatsappUrl}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.btnSecondaryWhatsapp}
                onClick={() => {
                  trackSecondaryCtaClick('יש לי שאלה לפני שקובעים', 'hero_secondary');
                  trackWhatsappClick();
                }}
              >
                <FaWhatsapp aria-hidden="true" />
                יש לי שאלה לפני שקובעים
              </a>
            </div>
            <div className={styles.heroMicrocopy}>
              התחלה קצרה ודיסקרטית · 50 דקות · 500 ₪ כולל מע״מ
            </div>

            <div className={styles.trustPoints} aria-label="יתרונות ודגשים">
              <div className={styles.trustPoint}>
                <FiMapPin className={styles.trustIcon} aria-hidden="true" />
                <span>אשדוד</span>
              </div>
              <div className={styles.trustPoint}>
                <FiUserCheck className={styles.trustIcon} aria-hidden="true" />
                <span>אונליין ב-Zoom</span>
              </div>
              <div className={styles.trustPoint}>
                <FiClock className={styles.trustIcon} aria-hidden="true" />
                <span>פגישה 50 דקות</span>
              </div>
              <div className={styles.trustPoint}>
                <FiLock className={styles.trustIcon} aria-hidden="true" />
                <span>דיסקרטיות מלאה</span>
              </div>
            </div>
          </div>
          <div className={styles.heroImageWrapper}>
            <img
              src="/images/shira-saharoni-sea.webp"
              alt="שירה סהרוני - ייעוץ זוגי באשדוד"
              className={styles.heroImage}
              width="477"
              height="1024"
              fetchPriority="high"
            />
            <div className={styles.heroImageBadge}>
              שירה סהרוני | יועצת זוגית, מנחת הורים ומגשרת מוסמכת
            </div>
          </div>
        </div>
      </section>

      {/* 3. PROBLEM Section */}
      <section className={styles.sectionAlt}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>כשהבעיה כבר לא היא על מה רבים — אלא איך השיחה מתנהלת</h2>
            <p>
              ויכוחים חוזרים ונשנים, שתיקות מתוחות, תחושת שחיקה ועייפות — כשזה קורה שוב ושוב, נוצר ריחוק עמוק ואובדן אמון.
            </p>
          </div>
          <div className={styles.recognitionGrid}>
            {recognitionItems.map((item, index) => (
              <article key={index} className={styles.recognitionCard}>
                <h3 className={styles.cardTitle}>{item.title}</h3>
                <p className={styles.cardDesc}>{item.desc}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* 4. SOLUTION Section */}
      <section className={styles.section}>
        <div className="container">
          <div className={styles.hopeBox}>
            <h2>ממפים את הדפוס, מבינים מה קורה ויוצאים עם צעד מעשי אחד</h2>
            <div className={styles.hopeContent}>
              <p>
                בייעוץ זוגי ממוקד לא צריך לפתור את כל משקעי העבר בשיחה אחת. הצעד הראשון הוא להבין איך השיחה ביניכם מסתבכת, מה מפעיל את ההסלמה, וכיצד ניתן ליצור עצירה בזמן אמת.
              </p>
              <p>
                מתוך התהליך מקבלים כלים מעשיים לפתיחת שיחה אחרת, להקשבה ללא התגוננות ולתרגול צעד אחד קטן בכל פעם בבית — כדי לבחון תקשורת רגועה ומקרבת יותר.
              </p>
            </div>
            <div className={styles.detailsCtas}>
              <button
                type="button"
                className={styles.btnPrimaryBooking}
                onClick={() => scrollToBooking('solution_section')}
              >
                קביעת פגישה
              </button>
              <a
                href={whatsappUrl}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.btnSecondaryWhatsapp}
                onClick={() => {
                  trackSecondaryCtaClick('יש לי שאלה לפני שקובעים', 'solution_section');
                  trackWhatsappClick();
                }}
              >
                <FaWhatsapp aria-hidden="true" />
                יש לי שאלה לפני שקובעים
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* 5. PROCESS Section (3 steps) */}
      <section className={styles.timelineSection}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>מה קורה בפגישת הייעוץ הראשונה?</h2>
            <p>
              50 דקות מסודרות וממוקדות הנותנות מקום שווה לשני בני הזוג, ללא שיפוטיות וללא בחירת צדדים.
            </p>
          </div>

          <div className={styles.timelineGrid}>
            {timelineSteps.map((step, index) => (
              <div key={index} className={styles.timelineCard}>
                <div className={styles.timeBadge}>{step.time}</div>
                <h3>{step.title}</h3>
                <p>{step.desc}</p>
              </div>
            ))}
          </div>

          <div className={styles.sessionsNote}>
            אין התחייבות לסדרת פגישות מראש. בסיום הפגישה הראשונה מעריכים יחד מה נכון לכם להמשך.
          </div>

          <div className={styles.centerCta}>
            <button
              type="button"
              className={styles.btnPrimaryBooking}
              onClick={() => scrollToBooking('process_section')}
            >
              קביעת פגישה
            </button>
          </div>
        </div>
      </section>

      {/* 6. Partner Resistance Section */}
      <section className={styles.resistanceSection}>
        <div className="container">
          <div className={styles.resistanceBox}>
            <h2>ומה אם אחד מבני הזוג פחות בטוח לגבי התהליך?</h2>
            <div className={styles.resistanceBody}>
              <p>
                זה טבעי שלפעמים אחד מבני הזוג חושש מהפגישה: חשש ש"יואשם" בבעיות, שהשיחה תהפוך לעוד עימות או שייכנסו לתהליך ארוך ומורכב.
              </p>
              <p>
                הייעוץ מתנהל בדיסקרטיות ובכבוד הדדי. המטרה אינה להוכיח מי צודק, אלא ליצור מרחב בטוח לשניכם להבין איפה השיחה נתקעת ולמצוא דרך מועילה יותר להתקדם.
              </p>
            </div>
            <a
              href={whatsappUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={styles.btnSecondaryWhatsapp}
              onClick={() => {
                trackSecondaryCtaClick('יש לי שאלה לפני שקובעים', 'resistance_section');
                trackWhatsappClick();
              }}
            >
              <FaWhatsapp aria-hidden="true" />
              יש לי שאלה לפני שקובעים
            </a>
          </div>
        </div>
      </section>

      {/* 7. WHY SHIRA Section */}
      <section className={styles.sectionAlt}>
        <div className={`container ${styles.aboutGrid}`}>
          <div className={styles.aboutImageWrapper}>
            <img
              src="/images/generated/services/couples-room.jpg"
              alt="מרחב שיחה וייעוץ זוגי באשדוד - שירה סהרוני"
              className={styles.aboutImage}
              width="1600"
              height="900"
              loading="lazy"
            />
          </div>
          <div className={styles.aboutContent}>
            <h2>למה לפנות לשירה סהרוני?</h2>
            <span className={styles.aboutRole}>
              יועצת זוגית, מנחת הורים ומגשרת מוסמכת, עורכת דין בהכשרתה
            </span>
            <p>
              הגישה המקצועית שלי משלבת הקשבה עמוקה, ראייה מערכתית וכלים מעשיים ותקשורתיים המותאמים למציאות היומיומית בבית.
            </p>
            <p>
              אני מאמינה כי גם כשהתקשורת עמוסה ומורכבת, עבודה מסודרת וממוקדת במרחב בטוח מאפשרת לעצור את ההסלמה ולפתוח אפשרות לשיחה אחרת.
            </p>

            <ul className={styles.trustPointsList}>
              <li>
                <strong>מקום בטוח ושווה לשני הצדדים:</strong>
                <span>כל אחד מבני הזוג מקבל הקשבה מלאה ללא שיפוטיות וללא בחירת צד.</span>
              </li>
              <li>
                <strong>מיפוי מסודר של הדפוס:</strong>
                <span>מזהים איפה השיחות נתקעות ומה מפעיל את הריחוק והכעס.</span>
              </li>
              <li>
                <strong>כלים מעשיים לבית:</strong>
                <span>יוצאים עם צעדים ישימים לתרגול יומיומי בתקשורת ביניכם.</span>
              </li>
            </ul>

            <a href="/about" className={styles.aboutLink}>
              קראו עוד על שירה סהרוני והרקע המקצועי ←
            </a>
          </div>
        </div>
      </section>

      {/* 8. Practical Details Card */}
      <section className={styles.section}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>מידע מעשי על פגישת הייעוץ</h2>
          </div>

          <div className={styles.detailsCard}>
            <div className={styles.priceTag}>500 ₪</div>
            <div className={styles.detailsList}>
              <div className={styles.detailsItem}>
                <strong>עלות הפגישה:</strong>
                <span>500 ₪ (כולל מע״מ)</span>
              </div>
              <div className={styles.detailsItem}>
                <strong>משך הפגישה:</strong>
                <span>50 דקות ממוקדות</span>
              </div>
              <div className={styles.detailsItem}>
                <strong>מיקום:</strong>
                <span>קליניקה באשדוד</span>
              </div>
              <div className={styles.detailsItem}>
                <strong>אפשרות נוספת:</strong>
                <span>פגישה אונליין (Zoom)</span>
              </div>
              <div className={styles.detailsItem}>
                <strong>סוג המפגש:</strong>
                <span>דיסקרטי, ממוקד וללא התחייבות מראש</span>
              </div>
            </div>

            <div className={styles.detailsClosing}>
              אפשר להתחיל מפגישה אחת בלבד כדי להבין מה קורה ביניכם ולהחליט יחד על המשך הדרך.
            </div>

            <div className={styles.detailsCtas}>
              <button
                type="button"
                className={styles.btnPrimaryBooking}
                onClick={() => scrollToBooking('details_card')}
              >
                קביעת פגישה
              </button>
              <a
                href={whatsappUrl}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.btnSecondaryWhatsapp}
                onClick={() => {
                  trackSecondaryCtaClick('יש לי שאלה לפני שקובעים', 'details_card');
                  trackWhatsappClick();
                }}
              >
                <FaWhatsapp aria-hidden="true" />
                יש לי שאלה לפני שקובעים
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* 9. FAQ Section */}
      <section className={styles.sectionAlt}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>שאלות נפוצות על ייעוץ זוגי באשדוד</h2>
          </div>
          <div className={styles.faqAccordion}>
            {faqItems.map((item, index) => (
              <div key={item.question} className={styles.faqItem}>
                <details onToggle={(e) => {
                  if ((e.target as HTMLDetailsElement).open) {
                    trackFaqInteraction(index);
                  }
                }}>
                  <summary>{item.question}</summary>
                  <p className={styles.faqAnswer}>{item.answer}</p>
                </details>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 10. Booking Section */}
      <section id="booking" className={`${styles.section} ${styles.bookingSection}`}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <FiCalendar aria-hidden="true" style={{ fontSize: '2rem', color: 'var(--color-accent)' }} />
            <h2>קביעת פגישת ייעוץ זוגי</h2>
            <p>
              בחרו ביומן את המועד המתאים לכם לפגישה בקליניקה באשדוד או אונליין בזום.
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
            <span>רוצים להתייעץ או לשאול לפני שקובעים?</span>
            <a
              href={whatsappUrl}
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => {
                trackSecondaryCtaClick('WhatsApp עזרה בהזמנה', 'booking_help');
                trackWhatsappClick();
              }}
            >
              <FaWhatsapp aria-hidden="true" />
              פנייה ב-WhatsApp
            </a>
          </div>
        </div>
      </section>

      {/* 11. FINAL CTA Section */}
      <section className={styles.closingCta}>
        <div className="container">
          <h2>אפשר להתחיל משיחה אחת רגועה</h2>
          <p>התחלה קצרה ודיסקרטית להבנת הדפוס ולפתיחת דרך אחרת לדבר.</p>
          <div className={styles.closingCtas}>
            <button
              type="button"
              className={styles.btnPrimaryBooking}
              onClick={() => scrollToBooking('closing_cta')}
            >
              קביעת פגישה
            </button>
            <a
              href={whatsappUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={styles.btnSecondaryWhatsapp}
              onClick={() => {
                trackSecondaryCtaClick('יש לי שאלה לפני שקובעים', 'closing_cta');
                trackWhatsappClick();
              }}
            >
              <FaWhatsapp aria-hidden="true" />
              יש לי שאלה לפני שקובעים
            </a>
          </div>
        </div>
      </section>

      {/* 12. Footer מצומצם */}
      <footer className={styles.footer}>
        <div className={`container ${styles.footerGrid}`}>
          <div className={styles.footerBrand}>
            שירה סהרוני — קשר | ייעוץ זוגי, הנחיית הורים וגישור
          </div>
          <div className={styles.footerContact}>
            <a href={`tel:${SITE_CONFIG.contact.phone.replace(/-/g, '')}`} onClick={trackPhoneClick}>
              טלפון: {SITE_CONFIG.contact.phone}
            </a>
            <a href={`mailto:${SITE_CONFIG.contact.email}`}>
              דוא״ל: {SITE_CONFIG.contact.email}
            </a>
            <span>קליניקה באשדוד / אונליין</span>
          </div>
          <div className={styles.footerLinks}>
            <a href="/privacy">מדיניות פרטיות</a>
            <a href="/accessibility">הצהרת נגישות</a>
            <a href="/terms">תנאי שימוש</a>
            <a href="/">לדף הבית</a>
          </div>
          <div className={styles.copyright}>
            © {new Date().getFullYear()} שירה סהרוני. כל הזכויות שמורות.
          </div>
        </div>
      </footer>

      {/* 13. Mobile Sticky Bar */}
      {!isBookingInView && (
        <div className={styles.mobileStickyBar}>
          <button
            type="button"
            className={styles.mobileStickyBookingBtn}
            onClick={() => scrollToBooking('mobile_sticky')}
          >
            <FiCheckCircle aria-hidden="true" />
            קביעת פגישה
          </button>
          <a
            href={whatsappUrl}
            target="_blank"
            rel="noopener noreferrer"
            className={styles.mobileStickyWhatsappBtn}
            aria-label="פנייה לשירה ב-WhatsApp"
            onClick={() => {
              trackSecondaryCtaClick('WhatsApp Sticky', 'mobile_sticky');
              trackWhatsappClick();
            }}
          >
            <FaWhatsapp aria-hidden="true" />
          </a>
        </div>
      )}
    </main>
  );
};

export default CouplesCounselingAshdodPage;
