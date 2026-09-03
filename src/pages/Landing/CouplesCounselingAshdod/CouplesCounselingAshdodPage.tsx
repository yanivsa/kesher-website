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
import styles from './CouplesCounselingAshdodPage.module.css';

const recognitionItems = [
  {
    title: 'שוב אותו ויכוח',
    desc: 'הנושא משתנה, אבל השיחה כמעט תמיד מגיעה לאותו מקום.',
  },
  {
    title: 'אחד מדבר, השני נסגר',
    desc: 'ככל שאחד מנסה להסביר יותר, השני מתרחק או מתגונן.',
  },
  {
    title: 'דברים קטנים מתפוצצים מהר',
    desc: 'שיחה שהתחילה בעניין יומיומי הופכת במהירות למאבק.',
  },
  {
    title: 'נוצר ריחוק',
    desc: 'מדברים על הבית, הילדים והמשימות — אבל פחות על מה שקורה ביניכם.',
  },
  {
    title: 'נמנעים משיחות',
    desc: 'יש דברים שכבר לא מעלים, כי לא רוצים עוד ערב של מתח.',
  },
  {
    title: 'רוצים שינוי, אבל תקועים',
    desc: 'שניכם אולי רוצים שיהיה אחרת, אבל לא יודעים איך לצאת מהדפוס שנוצר.',
  },
];

const timelineSteps = [
  {
    time: '00–15 דק׳',
    title: 'מתחילים ממה שקורה עכשיו',
    desc: 'נבין מה מביא אתכם לפגישה. כל אחד מקבל מקום לתאר איך הוא חווה את המצב ומה היה רוצה שייראה אחרת. המטרה בשלב הזה היא ליצור תמונה משותפת — לא להכריע בין שתי גרסאות.',
  },
  {
    time: '15–35 דק׳',
    title: 'מזהים מה קורה כשהשיחה מסתבכת',
    desc: 'נבדוק איך מתחילות השיחות שמסתיימות שוב באותו מקום. מה מפעיל כל אחד. איפה מתחילה ההתגוננות, ההתרחקות או ההסלמה. ואיזה דפוס חוזר ביניכם גם כששניכם התכוונתם בכלל למשהו אחר.',
  },
  {
    time: '35–50 דק׳',
    title: 'יוצאים עם כיוון מעשי ראשון',
    desc: 'נבחר דרך אחת שאפשר להתחיל לתרגל. זו יכולה להיות דרך לפתוח שיחה אחרת, לעצור הסלמה או להקשיב לפני שמגיבים. המטרה היא לצאת מהפגישה עם כיוון ברור שאפשר לנסות גם בבית.',
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
    answer: 'לא חייבים להגיע מתוך הסכמה על מי צודק או אפילו מתוך אותה נקודת מבט על הבעיה. המטרה בפגישה היא לא לבחור צד, אלא להבין מה קורה ביניכם כשהשיחה מסתבכת ולבדוק דרך אחרת לנהל אותה. אם יש חשש מסוים לפני שקובעים, אפשר לכתוב לשירה ב-WhatsApp ולשאול.',
  },
  {
    question: 'כמה זמן נמשכת פגישה?',
    answer: 'פגישת ייעוץ נמשכת 50 דקות מלאות.',
  },
  {
    question: 'האם אפשר לקיים את הפגישה אונליין?',
    answer: 'כן. לצד הפגישות בקליניקה באשדוד, קיימת אפשרות לקיים פגישה אונליין (Zoom).',
  },
  {
    question: 'איפה מתקיימות הפגישות?',
    answer: 'הפגישות הפרונטליות מתקיימות בקליניקה באשדוד.',
  },
  {
    question: 'מה מחיר הפגישה?',
    answer: 'מחיר פגישת ייעוץ הוא 500 ₪ כולל מע״מ.',
  },
  {
    question: 'איך קובעים פגישה?',
    answer: 'לוחצים על "קביעת פגישה", בוחרים מועד פנוי ביומן ומשלימים את ההזמנה. אם לא מצאתם מועד מתאים או שיש לכם שאלה לפני ההזמנה, אפשר לפנות לשירה ב-WhatsApp.',
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
      image: `${SITE_CONFIG.url}/images/shira-saharoni-sea.webp`,
      telephone: SITE_CONFIG.contact.phone,
      email: SITE_CONFIG.contact.email,
      priceRange: '₪500',
      description: 'ייעוץ זוגי מעשי וממוקד באשדוד או אונליין. כשאותם ריבים ודפוסי שיחה חוזרים שוב ושוב, אפשר להבין מה קורה ולתרגל דרך אחרת לדבר. פגישה של 50 דקות, 500 ₪.',
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

const copyVariants: Record<VariantId, { eyebrow: string; h1: string; subtitle: string }> = {
  A: {
    eyebrow: 'ייעוץ זוגי מעשי וממוקד באשדוד ובאונליין',
    h1: 'כשהשיחות חוזרות שוב ושוב לאותו ריב — אפשר ללמוד לדבר אחרת',
    subtitle: 'אם כל ניסיון לדבר נגמר שוב בוויכוח, בהתגוננות או בשתיקה, אפשר לעצור ולבדוק מה קורה ביניכם. בייעוץ זוגי ממוקד נבין את הדפוס שחוזר בשיחות, ונתרגל דרך אחרת לדבר, להקשיב ולהתמודד עם מחלוקות — בלי לחפש מי אשם ומי צודק.',
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
        title="ייעוץ זוגי באשדוד | שירה סהרוני"
        description="ייעוץ זוגי מעשי וממוקד באשדוד או אונליין. כשאותם ריבים ודפוסי שיחה חוזרים שוב ושוב, אפשר להבין מה קורה ולתרגל דרך אחרת לדבר. פגישה של 50 דקות, 500 ₪."
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
                <span>מקום לשני בני הזוג</span>
              </div>
              <div className={styles.trustPoint}>
                <FiClock className={styles.trustIcon} aria-hidden="true" />
                <span>גישה ממוקדת ומעשית</span>
              </div>
              <div className={styles.trustPoint}>
                <FiLock className={styles.trustIcon} aria-hidden="true" />
                <span>מרחב פרטי ומכבד</span>
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
              שירה סהרוני | יועצת זוגית ומגשרת מוסמכת
            </div>
          </div>
        </div>
      </section>

      {/* 3. אזור הזדהות עם הצורך (Recognition) */}
      <section className={styles.sectionAlt}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>כשהבעיה כבר לא היא על מה רבים — אלא איך השיחה מתנהלת</h2>
            <p>
              לפעמים זה מתחיל ממשהו קטן. מנסים להסביר משהו חשוב — ותוך כמה דקות שוב נמצאים בדיוק באותו ויכוח. אחד מנסה לדבר והשני נסגר. אחד מרגיש שלא מקשיבים לו, והשני מרגיש שכל שיחה הופכת לביקורת. דברים קטנים מקבלים מהר מאוד עוצמה שלא התכוונתם אליה. ולפעמים כבר מעדיפים לא לפתוח נושאים מסוימים, רק כדי לא להיכנס שוב לאותו מעגל.
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
            <h2>לא צריך לפתור את כל הזוגיות בשיחה אחת</h2>
            <div className={styles.hopeContent}>
              <p>
                אפשר להתחיל ממשהו פשוט יותר: לעצור רגע את הדפוס שחוזר ביניכם. להבין מה קורה בשיחה לפני שהיא הופכת לעימות. לראות מה כל אחד מנסה לומר — ומה הצד השני שומע באותו רגע.
              </p>
              <p>
                ומתוך ההבנה הזאת, לתרגל דרך אחרת להגיב, להקשיב ולדבר. המטרה אינה לייצר זוגיות בלי מחלוקות — המטרה היא ללמוד לנהל את המחלוקות בצורה שמאפשרת לשניכם להישאר בשיחה.
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
              50 דקות ממוקדות שנותנות מקום לשני בני הזוג ומאפשרות להתחיל לעשות סדר במה שקורה ביניכם. המטרה אינה להגיע כדי להוכיח מי צודק. מתחילים מהמצב כפי שכל אחד מכם חווה אותו, מזהים את הדפוס שחוזר בשיחות ובוחרים נקודה מעשית שאפשר להתחיל לעבוד עליה.
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
            אין מספר קבוע של פגישות שמתאים לכל זוג. אחרי הפגישה הראשונה אפשר להבין יחד מה נכון עבורכם בהמשך.
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

      {/* 6. התמודדות עם התנגדות בן/בת הזוג (Partner Resistance) */}
      <section className={styles.resistanceSection}>
        <div className="container">
          <div className={styles.resistanceBox}>
            <h2>ומה אם אחד מאיתנו פחות רוצה להגיע?</h2>
            <div className={styles.resistanceBody}>
              <p>
                זה לא חריג שאחד מבני הזוג יוזם את הפנייה והשני פחות משוכנע. לפעמים עצם הרעיון של ייעוץ זוגי מעלה חשש: שיבואו להחליט מי צודק, שיצביעו על אחד מכם כ״הבעיה״, או שתיכנסו לתהליך ארוך בלי לדעת לאן הוא הולך.
              </p>
              <p>
                זו לא מטרת הפגישה. אין צורך להגיע כדי להוכיח מי צודק ומי טועה. המטרה היא להבין מה קורה ביניכם כשהשיחה מסתבכת, לתת מקום לשתי נקודות המבט ולבדוק אם אפשר לנהל את אותם רגעים בצורה אחרת.
              </p>
              <p>
                אם יש חשש או שאלה לפני שקובעים, אפשר לשאול את שירה ישירות ב-WhatsApp.
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

      {/* 7. למה שירה / נעים להכיר (Why Shira) */}
      <section className={styles.sectionAlt}>
        <div className={`container ${styles.aboutGrid}`}>
          <div className={styles.aboutImageWrapper}>
            <img
              src="/images/generated/services/couples-room.jpg"
              alt="מרחב שיחה וייעוץ זוגי - שירה סהרוני"
              className={styles.aboutImage}
              width="1600"
              height="900"
              loading="lazy"
            />
          </div>
          <div className={styles.aboutContent}>
            <h2>כדי לדבר על הדברים הכי רגישים, צריך להרגיש שיש מקום לשני הצדדים</h2>
            <span className={styles.aboutRole}>
              שירה סהרוני | יועצת זוגית, מנחת הורים ומגשרת מוסמכת, עורכת דין בהכשרתה
            </span>
            <p>
              הגישה שלי משלבת הקשבה לשתי נקודות המבט, הסתכלות מסודרת על מה שקורה בין בני הזוג וכלים מעשיים שאפשר לקחת גם לחיים בבית.
            </p>
            <p>
              המטרה אינה לקבוע מי צודק. המטרה היא לעזור לכם להבין את הדפוס שנוצר ביניכם, לפרק שיחות עמוסות למשהו שאפשר להבין ולעבוד איתו, ולבחון דרך תקשורת מכבדת ומועילה יותר.
            </p>

            <ul className={styles.trustPointsList}>
              <li>
                <strong>מקום לשני הצדדים:</strong>
                <span>כל אחד מבני הזוג מקבל מקום להסביר איך הוא חווה את המצב.</span>
              </li>
              <li>
                <strong>בהירות וסדר:</strong>
                <span>מנסים להבין מה קורה בשיחות שלכם, בלי להפוך את הדברים למסובכים יותר.</span>
              </li>
              <li>
                <strong>כלים מעשיים:</strong>
                <span>הדגש הוא על דברים שאפשר לתרגל ולבדוק גם מחוץ לפגישה.</span>
              </li>
            </ul>

            <a href="/about" className={styles.aboutLink}>
              עוד על שירה ועל אופן העבודה ←
            </a>
          </div>
        </div>
      </section>

      {/* 8. מידע מעשי ומחיר (Practical Details / Price) */}
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
              אין צורך להתחייב מראש למספר קבוע של פגישות. אחרי הפגישה הראשונה תוכלו להבין יחד עם שירה מה נכון להמשך.
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
            <h2>שאלות שכדאי לדעת עליהן לפני הפגישה</h2>
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
              אם אתם מרגישים שהשיחות חוזרות שוב לאותו מקום ורוצים לבדוק דרך אחרת להתמודד עם זה, אפשר לבחור מועד לפגישת ייעוץ. הפגישה מתקיימת בקליניקה באשדוד או אונליין.
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
          <h2>לא חייבים לדעת כבר עכשיו איך לפתור הכול</h2>
          <p>מספיק להתחיל מלהבין מה קורה בשיחות שלכם — ולבדוק אם אפשר לעשות משהו אחרת.</p>
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
          <button
            type="button"
            className={styles.mobileStickyBtn}
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
