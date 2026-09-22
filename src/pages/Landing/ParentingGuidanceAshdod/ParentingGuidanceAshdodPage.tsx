import React, { useEffect, useState } from 'react';
import { FaPhone, FaWhatsapp } from 'react-icons/fa';
import {
  FiCalendar,
  FiCheckCircle,
  FiClock,
  FiHeart,
  FiLock,
  FiUserCheck,
} from 'react-icons/fi';
import CalendlyBookingEmbed from '../../../components/Booking/CalendlyBookingEmbed';
import MetaTags from '../../../components/SEO/MetaTags';
import SchemaOrg from '../../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../../constants/siteConfig';
import { useLandingPageAnalytics } from '../../../hooks/useLandingPageAnalytics';
import styles from './ParentingGuidanceAshdodPage.module.css';

const recognitionItems = [
  {
    title: 'מאבקים יומיומיים סביב שגרה',
    desc: 'התארגנות הבוקר, הכנת שיעורים, זמן מסכים והשכבה הופכים למוקד חיכוך קבוע.',
  },
  {
    title: 'תחושה ששום דבר לא עובד בלי צעקות',
    desc: 'מנסים להסביר בנועם ובסבלנות, אבל שיתוף הפעולה מתחיל רק כשהטונים עולים.',
  },
  {
    title: 'חילוקי דעות בין ההורים',
    desc: 'הורה אחד מחמיר והשני מוותר, מה שיוצר מתח ביניכם ומסרים סותרים לילדים.',
  },
  {
    title: 'רגשות אשם ותסכול מתמשך',
    desc: 'מסיימים את היום בתחושת מועקה על הדרך שבה הדברים התנהלו ומבטיחים שמחר יהיה אחרת.',
  },
  {
    title: 'קושי בהצבת גבולות עקביים',
    desc: 'מציבים גבול ברור אך נסוגים כשהילד מגיב בהתקף זעם, מחאה חריפה או בכי ממושך.',
  },
  {
    title: 'רוצים שקט, אבל תקועים בדפוס',
    desc: 'שניכם שואפים לאווירה נעימה ומכבדת, אך לא בטוחים איך לשבור את מעגל המאבקים.',
  },
];

const timelineSteps = [
  {
    time: '00–15 דק׳',
    title: 'מיפוי האתגרים המרכזיים בבית',
    desc: 'נבין מה הרגעים שבהם הקושי מתעורר במיוחד (בוקר, מסכים, מעברים או גבולות) ואיך כל אחד מההורים חווה את המצב. המטרה היא לקבל תמונה ברורה ומדויקת של היומיום שלכם.',
  },
  {
    time: '15–35 דק׳',
    title: 'זיהוי מעגל התגובות שמזין את המאבק',
    desc: 'נבדוק מה קורה ברגעי התסכול, איפה הגבול נסדק ומדוע התגובות הנוכחיות לא משיגות את שיתוף הפעולה הרצוי. נבין את הצרכים שמאחורי ההתנהגות של הילד ואת מקור החיכוך.',
  },
  {
    time: '35–50 דק׳',
    title: 'יוצאים עם כלי מעשי ראשון ליישום בבית',
    desc: 'נבחר דרך פעולה קונקרטית אחת שאפשר להתחיל לתרגל כבר מהיום בבית. המטרה היא לצאת מהפגישה עם צעד ברור, ישים וממוקד שיחזיר את הרוגע לשגרה.',
  },
];

const faqItems = [
  {
    question: 'מה קורה בפגישה הראשונה של הדרכת הורים?',
    answer: 'בפגישה הראשונה ממפים את האתגרים העיקריים בשגרת הבית, מבינים את הדינמיקה בין ההורים לילדים, ומזהים את מוקדי החיכוך המרכזיים. כבר בפגישה זו מגבשים כיוון מעשי ראשון להתמודדות.',
  },
  {
    question: 'האם הילדים מגיעים לפגישות?',
    answer: 'לא. פגישות הדרכת הורים נערכות עם ההורים בלבד. הדבר מאפשר שיחה פתוחה, כנה ומעמיקה על הקשיים והאתגרים ללא נוכחות הילד.',
  },
  {
    question: 'האם שני ההורים חייבים להגיע יחד?',
    answer: 'מומלץ מאוד ששני ההורים יגיעו יחד כדי לגבש שפה אחידה ולחזק את החזית ההורית. עם זאת, אם יש קושי בתיאום או התלבטות של אחד הצדדים, ניתן בהחלט להתחיל בהורה אחד.',
  },
  {
    question: 'מה אם בן או בת הזוג פחות מאמינים בהדרכת הורים?',
    answer: 'זהו מצב נפוץ. הפגישה אינה מקום לשיפוטיות או להטלת אשמה, אלא מרחב פרקטי למציאת פתרונות שמקלים על שני ההורים. אפשר להתייעץ עם שירה מראש ב-WhatsApp כדי לבחון כיצד לפתוח את הנושא.',
  },
  {
    question: 'האם ההדרכה מתאימה גם לאתגרי קשב וריכוז (ADHD) או ילדים מחוננים?',
    answer: 'כן. לשירה סהרוני ניסיון רב בליווי הורים לילדים עם קשיי קשב וריכוז (ADHD), תפקודים ניהוליים וילדים מחוננים, תוך התאמת כלים ספציפיים למאפיינים הייחודיים שלהם.',
  },
  {
    question: 'כמה זמן נמשכת פגישה ומה עלותה?',
    answer: 'פגישת הדרכת הורים נמשכת 50 דקות מלאות. עלות הפגישה היא 500 ₪ כולל מע״מ.',
  },
  {
    question: 'איפה מתקיימות הפגישות?',
    answer: 'הפגישות הפרונטליות מתקיימות בקליניקה באשדוד. כמו כן, ניתן לקיים פגישות מקוונות (Zoom) מכל מקום.',
  },
  {
    question: 'האם צריך להתחייב לסדרת פגישות מראש?',
    answer: 'לא. אין התחייבות למספר פגישות מראש. לאחר הפגישה הראשונה אפשר להעריך יחד מהו המוקד, אילו צעדים כדאי לנסות ומהי דרך ההמשך שמתאימה למשפחה.',
  },
];

const schemaData = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': ['LocalBusiness', 'ProfessionalService'],
      '@id': `${SITE_CONFIG.url}/parenting-guidance-ashdod#service`,
      name: 'הדרכת הורים באשדוד | שירה סהרוני',
      alternateName: 'קשר - הדרכת הורים באשדוד',
      url: `${SITE_CONFIG.url}/parenting-guidance-ashdod`,
      image: `${SITE_CONFIG.url}/images/generated/services/parenting-room.jpg`,
      telephone: '+972-50-2763802',
      email: SITE_CONFIG.contact.email,
      priceRange: '₪500',
      description: 'הדרכת הורים מעשית וממוקדת באשדוד או אונליין. כלים ליצירת סמכות רגועה, הצבת גבולות בלי מאבקים וחיזוק שיתוף הפעולה בבית. פגישה של 50 דקות, 500 ₪.',
      address: {
        '@type': 'PostalAddress',
        streetAddress: 'אשדוד',
        addressLocality: 'אשדוד',
        addressRegion: 'מחוז הדרום',
        postalCode: '77100',
        addressCountry: 'IL',
      },
      geo: {
        '@type': 'GeoCoordinates',
        latitude: 31.8014,
        longitude: 34.6435,
      },
      openingHoursSpecification: [
        {
          '@type': 'OpeningHoursSpecification',
          dayOfWeek: ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday'],
          opens: '09:00',
          closes: '20:00',
        },
      ],
      provider: {
        '@type': 'LocalBusiness',
        '@id': `${SITE_CONFIG.url}/#business`,
        name: 'שירה סהרוני — קשר',
      },
      areaServed: [
        {
          '@type': 'City',
          name: 'אשדוד',
        },
        {
          '@type': 'AdministrativeArea',
          name: 'אשדוד והסביבה',
        },
        {
          '@type': 'Country',
          name: 'ישראל (אונליין)',
        },
      ],
      sameAs: [
        SITE_CONFIG.links.facebook,
        SITE_CONFIG.links.instagram,
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
          name: 'הדרכת הורים באשדוד',
          item: `${SITE_CONFIG.url}/parenting-guidance-ashdod`,
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

const ParentingGuidanceAshdodPage: React.FC = () => {
  const [isBookingInView, setIsBookingInView] = useState(false);
  const variantId = 'A';

  const {
    trackCtaClick,
    trackSecondaryCtaClick,
    trackPhoneClick,
    trackWhatsappClick,
    trackFaqInteraction,
  } = useLandingPageAnalytics(variantId);

  const whatsappMessage = encodeURIComponent(
    'היי שירה, הגעתי לעמוד הדרכת הורים באשדוד ויש לי שאלה לפני שקובעים פגישה.',
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
        title="הדרכת הורים באשדוד | שירה סהרוני"
        description="הדרכת הורים מעשית וממוקדת באשדוד או אונליין. כלים ליצירת סמכות רגועה, הצבת גבולות בלי מאבקים וחיזוק שיתוף הפעולה בבית. פגישה של 50 דקות, 500 ₪."
        canonical={`${SITE_CONFIG.url}/parenting-guidance-ashdod`}
        image="/images/generated/services/parenting-room.jpg"
      />
      <SchemaOrg data={schemaData} />

      {/* 1. Header מצומצם */}
      <header className={styles.header}>
        <div className={`container ${styles.headerInner}`}>
          <a href="/" className={styles.brand} aria-label="לדף הבית של שירה סהרוני">
            <div className={styles.brandText}>
              <span className={styles.brandTitle}>שירה סהרוני</span>
              <span className={styles.brandSubtitle}>קשר | הדרכת הורים באשדוד</span>
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
      <section className={styles.heroSection} aria-labelledby="parenting-ashdod-title">
        <div className={`container ${styles.heroGrid}`}>
          <div className={styles.heroContent}>
            <div className={styles.heroTag}>
              <FiHeart aria-hidden="true" />
              <span>קליניקה באשדוד ובאונליין | שירה סהרוני</span>
            </div>
            <h1 id="parenting-ashdod-title" className={styles.heroTitle}>
              הדרכת הורים באשדוד – כלים מעשיים ושקט בבית
            </h1>
            <p className={styles.heroSubtitle}>
              הדרכת הורים באשדוד עם שירה סהרוני מתאימה להורים שמתמודדים עם מאבקי כוח, גבולות, מסכים, התארגנות או פערים בין ההורים. בפגישה ממפים את הדפוסים שחוזרים בבית ובוחרים כלי מעשי שאפשר לנסות בשגרה; אפשר להתחיל בקביעת פגישה או בשאלה קצרה ב-WhatsApp.
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
            <div className={styles.heroMicrocopy}>
              50 דקות · קליניקה באשדוד או פגישה אונליין · ללא התחייבות לתהליך ארוך
            </div>

            <div className={styles.trustPoints} aria-label="נקודות אמון">
              <div className={styles.trustPoint}>
                <FiUserCheck className={styles.trustIcon} aria-hidden="true" />
                <span>סמכות הורית רגועה</span>
              </div>
              <div className={styles.trustPoint}>
                <FiClock className={styles.trustIcon} aria-hidden="true" />
                <span>כלים מעשיים לשגרה</span>
              </div>
              <div className={styles.trustPoint}>
                <FiLock className={styles.trustIcon} aria-hidden="true" />
                <span>מרחב מקצועי ומכבד</span>
              </div>
            </div>
          </div>
          <div className={styles.heroImageWrapper}>
            <img
              src="/images/generated/services/parenting-room.jpg"
              alt="שירה סהרוני - הדרכת הורים באשדוד"
              className={styles.heroImage}
              width="1600"
              height="900"
              fetchPriority="high"
            />
            <div className={styles.heroImageBadge}>
              שירה סהרוני | מנחת הורים ויועצת זוגית
            </div>
          </div>
        </div>
      </section>

      {/* 3. אזור הזדהות עם הצורך (Recognition) */}
      <section className={styles.sectionAlt}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>התמודדות עם קשיי התנהגות ומעברים – כשכל משימה הופכת למאבק</h2>
            <p>
              שגרת הבית לא אמורה להרגיש כמו שדה קרב. מנסים לבקש בנועם, לחזור שוב, להסביר בהיגיון — אבל לעיתים קרובות שום דבר לא זז עד שהטונים עולים. בסוף מוצאים את עצמכם מתעמתים סביב מסכים, מקלחות או התארגנות בוקר, והולכים לישון מותשים ועם מועקה בלב. אפשר לשנות את הדינמיקה הזו.
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

      {/* 4. אזור תקווה ומעבר מעשי (Hope / Transition) */}
      <section className={styles.section}>
        <div className="container">
          <div className={styles.hopeBox}>
            <h2>כלים להצבת גבולות ברורים ברוגע – לא צריך להיות הורים מושלמים</h2>
            <div className={styles.hopeContent}>
              <p>
                הורות רגועה אינה דורשת שינוי קיצוני של כל הבית ביום אחד. אפשר להתחיל מהבנה מדויקת של מה שמפעיל את מעגל המאבקים, ולבחור תגובה הורית אחת שמחזירה את השליטה והרוגע.
              </p>
              <p>
                כשמציבים גבול ברור ללא כעס ומגבים אותו בנוכחות בטוחה, הילדים מרגישים מוגנים ופנויים יותר לשתף פעולה. המטרה אינה להכניע, אלא לבנות סמכות מכבדת ומקרבת.
              </p>
            </div>
            <button
              type="button"
              className={styles.btnPrimary}
              onClick={() => scrollToBooking('hope_section')}
            >
              קביעת פגישה
            </button>
          </div>
        </div>
      </section>

      {/* 5. מה קורה בפגישה הראשונה? (Process / 3 Steps) */}
      <section className={styles.timelineSection}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>מה קורה בפגישה הראשונה?</h2>
            <p>
              50 דקות ממוקדות שמעניקות סדר ובהירות במה שקורה בבית. נפגשים כהורים במרחב פתוח ולא שיפוטי, מזהים את מוקדי החיכוך המרכזיים ויוצאים עם כיוון מעשי וברור שאפשר להתחיל לתרגל מיד.
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
            אין מספר קבוע של פגישות שמתאים לכל משפחה. לעיתים מספר מפגשים קצר וממוקד מספיק כדי לייצר שינוי עמוק בשגרה.
          </div>

          <div className={styles.centerCta}>
            <button
              type="button"
              className={styles.btnPrimary}
              onClick={() => scrollToBooking('first_session')}
            >
              קביעת פגישה
            </button>
          </div>
        </div>
      </section>

      {/* 6. התמודדות עם התלבטות בן/בת הזוג */}
      <section className={styles.resistanceSection}>
        <div className="container">
          <div className={styles.resistanceBox}>
            <h2>ומה אם אחד מאיתנו פחות מאמין בהדרכת הורים?</h2>
            <div className={styles.resistanceBody}>
              <p>
                זה טבעי לחלוטין שהורה אחד ייזום את הפנייה והשני ירגיש ספקנות או חשש מביקורת. לעיתים יש פחד שמישהו מבחוץ יחלק ״ציונים״ להורות שלכם או יציע תיאוריות שאינן תואמות את החיים האמיתיים.
              </p>
              <p>
                הדרכת הורים אינה עוסקת במציאת אשמים. המטרה היא להבין יחד את היומיום שלכם, להוריד את מפלס הלחץ בבית ולגבש כלים פרקטיים ששניכם תרגישו איתם בנוח ובטוח.
              </p>
              <p>
                אם יש שאלה או התלבטות לפני שמתאמים, שירה זמינה להתייעצות ישירה ב-WhatsApp.
              </p>
            </div>
            <a
              href={whatsappUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={styles.btnSecondary}
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

      {/* 7. למה שירה / נעים להכיר */}
      <section className={styles.sectionAlt}>
        <div className={`container ${styles.aboutGrid}`}>
          <div className={styles.aboutImageWrapper}>
            <img
              src="/images/shira-saharoni-about.webp"
              alt="שירה סהרוני - מנחת הורים ויועצת זוגית"
              className={styles.aboutImage}
              width="477"
              height="600"
              loading="lazy"
            />
          </div>
          <div className={styles.aboutContent}>
            <h2>הנחיית הורים באשדוד – ליווי מעשי לחיבור בין הבנת הילד לסמכות רגועה</h2>
            <span className={styles.aboutRole}>
              שירה סהרוני | מנחת הורים, יועצת זוגית ומגשרת מוסמכת
            </span>
            <p>
              הגישה שלי משלבת ראייה מערכתית של התא המשפחתי, הבנה עמוקה של צורכי הילד, והתמקדות בכלים יישומיים שמתאימים למציאות העמוסה של הורים כיום.
            </p>
            <p>
              לצד ליווי משפחות סביב שגרה וגבולות, צברתי ניסיון עשיר בהתמודדות עם אתגרי קשב וריכוז (ADHD), תפקודים ניהוליים, ילדים מחוננים ומעברים חינוכיים משמעותיים.
            </p>

            <ul className={styles.trustPointsList}>
              <li>
                <strong>חזית הורית משותפת:</strong>
                <span>עוזרים לשני ההורים לפעול בתיאום, גם כשיש ביניהם פערי גישות.</span>
              </li>
              <li>
                <strong>ראייה מעשית וקונקרטית:</strong>
                <span>פתרונות ברורים לבוקר, להשכבה, למסכים ולשעות שדורשות שיתוף פעולה.</span>
              </li>
              <li>
                <strong>מרחב בטוח ללא שיפוטיות:</strong>
                <span>מקום שבו מותר לפרוק את הקושי ולקבל תמיכה אמיתית ומקצועית.</span>
              </li>
            </ul>

            <a href="/about" className={styles.aboutLink}>
              עוד על שירה ועל אופן העבודה ←
            </a>
          </div>
        </div>
      </section>

      {/* 8. מידע מעשי ומחיר */}
      <section className={styles.section}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>כל מה שצריך לדעת לפני שקובעים</h2>
          </div>

          <div className={styles.detailsCard}>
            <div className={styles.priceTag}>500 ₪</div>
            <div className={styles.detailsList}>
              <div className={styles.detailsItem}>
                <strong>מחיר פגישה:</strong>
                <span>500 ₪ (כולל מע״מ)</span>
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
                <span>פגישה אונליין (Zoom)</span>
              </div>
              <div className={styles.detailsItem}>
                <strong>קביעת מועד:</strong>
                <span>בוחרים מועד פנוי ביומן באתר ומשלימים את ההזמנה</span>
              </div>
              <div className={styles.detailsItem}>
                <strong>שינוי או ביטול:</strong>
                <span>ניתן לשנות או לבטל מועד בקלות באמצעות הקישור באישור ההזמנה</span>
              </div>
            </div>

            <div className={styles.detailsClosing}>
              אין צורך להתחייב מראש למספר קבוע של פגישות. אחרי הפגישה הראשונה תוכלו להבין יחד מה נכון להמשך.
            </div>

            <div className={styles.detailsCtas}>
              <button
                type="button"
                className={styles.btnPrimary}
                onClick={() => scrollToBooking('details_card')}
              >
                קביעת פגישה
              </button>
              <a
                href={whatsappUrl}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.btnSecondary}
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

      {/* 9. שאלות נפוצות (FAQ) */}
      <section className={styles.sectionAlt}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>שאלות נפוצות על הדרכת הורים</h2>
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

      {/* 10. אזור הזמנת פגישה (Booking / Calendly) */}
      <section id="booking" className={`${styles.section} ${styles.bookingSection}`}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <FiCalendar aria-hidden="true" style={{ fontSize: '2rem', color: 'var(--color-accent)' }} />
            <h2>אפשר להתחיל מפגישה אחת מסודרת</h2>
            <p>
              אם אתם מרגישים ששגרת הבית שוחקת אתכם ורוצים להחזיר את הרוגע והסמכות, אפשר לבחור מועד נוח לפגישת הדרכת הורים. הפגישה מתקיימת בקליניקה באשדוד או אונליין.
            </p>
          </div>

          <div className={styles.calendlyWrapper}>
            <CalendlyBookingEmbed
              ariaLabel="לוח זמנים לקביעת פגישת הדרכת הורים באשדוד עם שירה סהרוני"
              serviceType="parenting_guidance"
              bookingPagePath="/parenting-guidance-ashdod"
              landingPageType="ashdod"
              variantId={variantId}
              value={500}
              currency="ILS"
            />
          </div>

          <div className={styles.bookingHelp}>
            <span>לא מצאתם מועד מתאים או שיש לכם שאלה לפני ההזמנה?</span>
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
              כתבו לשירה ב-WhatsApp
            </a>
          </div>
        </div>
      </section>

      {/* 11. CTA מסכם */}
      <section className={styles.closingCta}>
        <div className="container">
          <h2>אפשר להחזיר את הרוגע והביטחון לבית</h2>
          <p>מספיק להתחיל מצעד קטן וממוקד כדי לראות איך האווירה המשפחתית משתנה לטובה.</p>
          <div className={styles.closingCtas}>
            <button
              type="button"
              className={styles.btnPrimary}
              onClick={() => scrollToBooking('closing_cta')}
            >
              קביעת פגישה
            </button>
            <a
              href={whatsappUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={styles.btnSecondary}
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
            שירה סהרוני — קשר
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
            <a href="/">לדף הבית של האתר</a>
          </div>
          <div className={styles.copyright}>
            © {new Date().getFullYear()} שירה סהרוני. כל הזכויות שמורות.
          </div>
        </div>
      </footer>

      {/* 13. Mobile Sticky Bar */}
      {!isBookingInView && (
        <div className={styles.mobileStickyBar}>
          <a
            href={`tel:${SITE_CONFIG.contact.phone.replace(/-/g, '')}`}
            className={styles.mobileStickyPhoneBtn}
            onClick={trackPhoneClick}
            aria-label="חיוג טלפוני לשירה סהרוני"
          >
            <FaPhone aria-hidden="true" />
          </a>
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

export default ParentingGuidanceAshdodPage;
