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
  FiUserCheck,
} from 'react-icons/fi';
import MetaTags from '../../../components/SEO/MetaTags';
import SchemaOrg from '../../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../../constants/siteConfig';
import { useLandingPageAnalytics } from '../../../hooks/useLandingPageAnalytics';
import styles from './CouplesCounselingAshdodPage.module.css';



const timelineSteps = [
  {
    time: '00–15 דק׳',
    title: 'מיפוי הנושאים והורדת הלהבות',
    desc: 'היכרות רגועה במרחב בטוח, הגדרת האתגר המרכזי מנקודת המבט של שני בני הזוג ויצירת מסגרת שיחה מכבדת.',
  },
  {
    time: '15–35 דק׳',
    title: 'זיהוי הטריגר הזוגי האוטומטי',
    desc: 'פירוק הדפוס שחוזר על עצמו בשיחות: מזהים מה גורם לאחד להתגונן ולשני להתרחק, ואיך עוצרים את ההסלמה.',
  },
  {
    time: '35–50 דק׳',
    title: 'בניית כלי מעשי ראשון לבית',
    desc: 'יציאה עם תרגיל תקשורת ממוקד ומותאם אישית שתוכלו לנסות כבר בשיחה הבאה שלכם בבית.',
  },
];

const faqItems = [
  {
    question: 'מה קורה בפגישה הראשונה?',
    answer: 'הפגישה הראשונה מיועדת להיכרות, להבנת הנושאים שמעסיקים את בני הזוג ולמיפוי דפוסי התקשורת והמטרות להמשך.',
  },
  {
    question: 'האם צריך להגיע יחד?',
    answer: 'מומלץ להגיע יחד לפגישה הזוגית, שכן התהליך מתמקד בתקשורת ובדפוסים שבין בני הזוג. במידת הצורך ניתן להתייעץ מראש לפני הפגישה.',
  },
  {
    question: 'כמה פגישות נדרשות?',
    answer: 'אין מספר קבוע שמתאים לכל זוג. לאחר הפגישה הראשונה ניתן להעריך יחד את הצרכים ואת דרך ההמשך.',
  },
  {
    question: 'האם אפשר להיפגש אונליין?',
    answer: 'כן. לצד הפגישות בקליניקה באשדוד, קיימת אפשרות לקיים פגישה אונליין.',
  },
  {
    question: 'מה מחיר הפגישה?',
    answer: 'מחיר פגישת ייעוץ הוא 500 ₪.',
  },
  {
    question: 'כיצד משנים או מבטלים פגישה?',
    answer: 'ניתן לשנות או לבטל את הפגישה בקלות באמצעות הקישור המופיע באישור ההזמנה מ־Calendly או בפנייה ישרה.',
  },
  {
    question: 'האם הפגישות דיסקרטיות?',
    answer: 'הפגישות מתקיימות במרחב פרטי ומכבד, בהתאם לכללי האתיקה המקצועית. ניתן לעיין במדיניות הפרטיות של האתר.',
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
      description: 'ייעוץ זוגי ממוקד ומעשי באשדוד או אונליין. כלים לתקשורת, ניהול מחלוקות ויצירת הסכמות. קביעת פגישה בעלות 500 ₪.',
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

// Controlled Copy Variants Architecture (Variant A = Default Production, B = Trust & Process, C = Pattern)
type VariantId = 'A' | 'B' | 'C';

const copyVariants: Record<VariantId, { h1: string; subtitle: string }> = {
  A: {
    h1: 'ייעוץ זוגי באשדוד – דרך מעשית לדבר אחרת',
    subtitle: 'תהליך ממוקד ומכבד לזיהוי דפוסי תקשורת, ניהול מחלוקות ובניית שיחה זוגית טובה יותר. פגישות בקליניקה באשדוד או אונליין.',
  },
  B: {
    h1: 'ייעוץ זוגי באשדוד בתהליך ממוקד ומכבד',
    subtitle: 'מרחב מסודר ומקצועי לזיהוי נקודות המחלוקת, רכישת כלים מעשיים ובניית שיחה רגועה וברורה יותר. פגישות באשדוד או אונליין.',
  },
  C: {
    h1: 'כשהשיחות חוזרות לאותו דפוס – ייעוץ זוגי באשדוד',
    subtitle: 'תהליך ממוקד להבנת דפוסי התקשורת ולתרגול כלים לשיחה מכבדת ומועילה יותר.',
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
    'היי שירה, הגעתי מעמוד הייעוץ הזוגי באשדוד ויש לי שאלה לפני שקובעים פגישה.',
  );
  const whatsappUrl = `https://wa.me/${SITE_CONFIG.contact.whatsapp}?text=${whatsappMessage}`;

  const scrollToBooking = (location: string) => {
    trackCtaClick('קביעת פגישת ייעוץ – 500 ₪', location);
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
        description="ייעוץ זוגי ממוקד ומעשי באשדוד או אונליין. כלים לתקשורת, ניהול מחלוקות ויצירת הסכמות. קביעת פגישה בעלות 500 ₪."
        canonical={`${SITE_CONFIG.url}/couples-counseling-ashdod`}
        image="/images/shira-saharoni.webp"
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
      <section className={styles.heroSection}>
        <div className={`container ${styles.heroGrid}`}>
          <div className={styles.heroContent}>
            <div className={styles.heroTag}>
              <FiHeart aria-hidden="true" />
              <span>ייעוץ זוגי באשדוד והסביבה</span>
            </div>
            <h1 className={styles.heroTitle}>
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
                קביעת פגישת ייעוץ – 500 ₪
              </button>
              <a
                href={whatsappUrl}
                target="_blank"
                rel="noopener noreferrer"
                className={styles.btnSecondary}
                onClick={() => {
                  trackSecondaryCtaClick('יש לכם שאלה לפני שקובעים?', 'hero_secondary');
                  trackWhatsappClick();
                }}
              >
                <FaWhatsapp aria-hidden="true" />
                יש לכם שאלה לפני שקובעים?
              </a>
            </div>
            <div className={styles.trustPoints} aria-label="נקודות אמון">
              <div className={styles.trustPoint}>
                <FiMapPin className={styles.trustIcon} aria-hidden="true" />
                <span>קליניקה באשדוד</span>
              </div>
              <div className={styles.trustPoint}>
                <FiClock className={styles.trustIcon} aria-hidden="true" />
                <span>אפשרות לפגישה אונליין</span>
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
              alt="שירה סהרוני - יועצת זוגית ומגשרת באשדוד"
              className={styles.heroImage}
              width="1271"
              height="1280"
              fetchPriority="high"
            />
            <div className={styles.heroImageBadge}>
              שירה סהרוני | יועצת זוגית ומגשרת מוסמכת
            </div>
          </div>
        </div>
      </section>



      {/* 3. אזור הזדהות עם הצורך */}
      <section className={styles.sectionAlt}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>כשהשיחות חוזרות שוב לאותו המקום</h2>
            <p>
              לעיתים גם זוגות שרוצים להמשיך יחד מתקשים לדבר על נושאים חשובים בלי להיגרר להתגוננות, כעס או שתיקה. ייעוץ זוגי מאפשר לעצור, לזהות את הדפוסים שחוזרים על עצמם וללמוד דרכים מעשיות יותר להקשבה, להצגת צרכים ולניהול מחלוקות.
            </p>
          </div>
          <div className={styles.identificationGrid}>
            <div className={styles.identCard}>
              <div className={styles.identIcon} aria-hidden="true">🔄</div>
              <p>מחלוקות שחוזרות ללא פתרון ברור</p>
            </div>
            <div className={styles.identCard}>
              <div className={styles.identIcon} aria-hidden="true">🗣️</div>
              <p>קושי להביע צרכים ולהקשיב לצד השני</p>
            </div>
            <div className={styles.identCard}>
              <div className={styles.identIcon} aria-hidden="true">🛡️</div>
              <p>תחושה שהשיחה הופכת במהירות להתגוננות או להתרחקות</p>
            </div>
          </div>
        </div>
      </section>

      {/* 3.5 מפת 50 הדקות של הפגישה הראשונה (Interactive Session Timeline) */}
      <section className={styles.timelineSection}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>מה בדיוק קורה ב-50 הדקות של הפגישה הראשונה?</h2>
            <p>שקיפות לגבי התהליך: ללא הפתעות, במרחב מכבד וענייני</p>
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
        </div>
      </section>

      {/* 4. אזור הצעת הערך */}
      <section className={styles.section}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>ייעוץ זוגי ממוקד וכלים שאפשר ליישם בבית</h2>
            <p>
              הייעוץ מתמקד בהבנת דפוסי השיחה בין בני הזוג, בזיהוי נקודות החיכוך ובתרגול כלים לניהול שיחה, הקשבה ויצירת הסכמות. המטרה היא לבנות דרך תקשורת שמאפשרת להתמודד עם מחלוקות באופן מכבד ומועיל יותר.
            </p>
          </div>

          <div className={styles.stepsGrid}>
            <article className={styles.stepCard}>
              <span className={styles.stepNumber}>שלב 1</span>
              <h3>ממפים את הקושי</h3>
              <p>מזהים את הנושאים ואת דפוסי התקשורת שחוזרים בשיחות.</p>
            </article>
            <article className={styles.stepCard}>
              <span className={styles.stepNumber}>שלב 2</span>
              <h3>לומדים כלים מעשיים</h3>
              <p>מתרגלים הקשבה, הצגת צרכים, ניהול מחלוקת ויצירת הסכמות.</p>
            </article>
            <article className={styles.stepCard}>
              <span className={styles.stepNumber}>שלב 3</span>
              <h3>מיישמים בחיי היום־יום</h3>
              <p>מתאימים את הכלים למצבים אמיתיים ובוחנים את ההתקדמות מפגישה לפגישה.</p>
            </article>
          </div>

          <div className={styles.sessionsNote}>
            אין מספר קבוע של פגישות שמתאים לכל זוג. דרך ההמשך נקבעת בהתאם למטרות ולצרכים שעולים בפגישה.
          </div>
        </div>
      </section>

      {/* 5. אזור נעים להכיר */}
      <section className={styles.sectionAlt}>
        <div className={`container ${styles.aboutGrid}`}>
          <div className={styles.aboutImageWrapper}>
            <img
              src="/images/shira-saharoni.webp"
              alt="שירה סהרוני - יועצת זוגית ומגשרת"
              className={styles.aboutImage}
              width="1271"
              height="1280"
              loading="lazy"
            />
          </div>
          <div className={styles.aboutContent}>
            <h2>נעים להכיר, שירה סהרוני</h2>
            <span className={styles.aboutRole}>
              יועצת זוגית ומנחת הורים
            </span>
            <p>
              הגישה שלי משלבת הסתכלות מסודרת על נקודות המחלוקת עם כלים מעשיים לניהול שיחה, הקשבה ויצירת הסכמות. המטרה אינה לקבוע מי צודק, אלא לעזור לבני הזוג להבין את הדפוסים שנוצרו ביניהם ולבחור דרך תקשורת מועילה ומכבדת יותר.
            </p>
            <p>
              אני מביאה לחדר הייעוץ הקשבה עמוקה, בהירות ומבנה מסודר המסייעים לפרק מורכבות ולהפוך שיחות עמוסות לדיאלוג ענייני ומקדם.
            </p>
          </div>
        </div>
      </section>

      {/* 6. אזור התאמת השירות */}
      <section className={styles.section}>
        <div className={`container ${styles.fitGrid}`}>
          <div className={styles.fitCard}>
            <h3>
              <FiUserCheck aria-hidden="true" />
              למי מתאים ייעוץ זוגי?
            </h3>
            <ul className={styles.fitList}>
              <li>זוגות המעוניינים לשפר את דרך התקשורת ביניהם</li>
              <li>זוגות המתמודדים עם מחלוקות שחוזרות שוב ושוב</li>
              <li>זוגות המחפשים תהליך ממוקד וכלים מעשיים</li>
              <li>זוגות המעוניינים להיפגש באשדוד או אונליין</li>
              <li>זוגות שמוכנים לבחון יחד דפוסים ודרכי פעולה חדשות</li>
            </ul>
          </div>

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
      </section>

      {/* 7. יתרון מקומי */}
      <section className={styles.sectionAlt}>
        <div className="container">
          <div className={styles.localBox}>
            <h2>ייעוץ זוגי בקליניקה באשדוד</h2>
            <p>
              הפגישות מתקיימות בקליניקה באשדוד. קיימת גם אפשרות לקיים פגישות אונליין, בהתאם לצורך ולזמינות.
            </p>
            <div className={styles.localFeatures}>
              <div className={styles.localBadge}>
                <FiMapPin aria-hidden="true" />
                <span>קליניקה באשדוד</span>
              </div>
              <div className={styles.localBadge}>
                <FiClock aria-hidden="true" />
                <span>פגישות אונליין (Zoom)</span>
              </div>
              <div className={styles.localBadge}>
                <FiLock aria-hidden="true" />
                <span>סביבה שקטה ודיסקרטית</span>
              </div>
            </div>
          </div>
        </div>
      </section>



      {/* 9. מידע על הפגישה + הסרת חסמים */}
      <section className={styles.section}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>מידע מעשי לפני שקובעים</h2>
          </div>

          {/* כרטיס פרטי פגישה */}
          <div className={styles.detailsCard}>
            <div className={styles.priceTag}>500 ₪</div>
            <div className={styles.detailsList}>
              <div className={styles.detailsItem}>
                <strong>מחיר פגישה:</strong>
                <span>500 ₪</span>
              </div>
              <div className={styles.detailsItem}>
                <strong>מיקום:</strong>
                <span>אשדוד</span>
              </div>
              <div className={styles.detailsItem}>
                <strong>אפשרות נוספת:</strong>
                <span>פגישה אונליין (Zoom)</span>
              </div>
              <div className={styles.detailsItem}>
                <strong>משך הפגישה:</strong>
                <span>50 דקות</span>
              </div>
              <div className={styles.detailsItem}>
                <strong>אופן התשלום:</strong>
                <span>התשלום מתבצע ישירות בעת קביעת הפגישה ב-Calendly</span>
              </div>
              <div className={styles.detailsItem}>
                <strong>מדיניות שינוי וביטול:</strong>
                <span>שינוי או ביטול מועד מתבצעים בקלות באמצעות הקישור באישור ההזמנה</span>
              </div>
            </div>
          </div>

          {/* הסרת חסמים — Fear Removal */}
          <div className={styles.frictionBox}>
            <h3 className={styles.frictionTitle}>שאלות שעולות לפני שמחליטים לקבוע</h3>
            <div className={styles.frictionGrid}>
              <div className={styles.frictionCard}>
                <div className={styles.frictionEmoji} aria-hidden="true">🔒</div>
                <h4>האם מה שנאמר בפגישה נשמר בסוד?</h4>
                <p>הפגישות מתקיימות במרחב פרטי ומכבד, בהתאם לכללי האתיקה המקצועית. ניתן לעיין במדיניות הפרטיות של האתר.</p>
              </div>
              <div className={styles.frictionCard}>
                <div className={styles.frictionEmoji} aria-hidden="true">📅</div>
                <h4>מה קורה אם אנחנו לא מוכנים להמשיך אחרי הפגישה הראשונה?</h4>
                <p>אין שום מחויבות להמשיך. הפגישה הראשונה היא נקודת היכרות והערכה הדדית. דרך ההמשך נקבעת רק אם שני הצדדים מרגישים שזה מתאים.</p>
              </div>
              <div className={styles.frictionCard}>
                <div className={styles.frictionEmoji} aria-hidden="true">🤔</div>
                <h4>מה אם בן/בת הזוג שלי לא מוכן/ה לבוא?</h4>
                <p>כדאי לשאול — לפעמים הצד שמסרב לבוא רק צריך להבין מה מחכה לו שם. אפשר לפנות לשירה ב-WhatsApp לפני שקובעים, ולקבל תשובה לשאלה הזו ספציפית.</p>
              </div>
              <div className={styles.frictionCard}>
                <div className={styles.frictionEmoji} aria-hidden="true">❌</div>
                <h4>מה קורה אם צריך לבטל את הפגישה?</h4>
                <p>ביטול ושינוי מועד מתבצעים בקלות מהקישור באישור ההזמנה מ-Calendly — בלי שיחות טלפון ובלי לחץ.</p>
              </div>
              <div className={styles.frictionCard}>
                <div className={styles.frictionEmoji} aria-hidden="true">🎯</div>
                <h4>האם שירה תגיד לנו מי צודק?</h4>
                <p>לא. המטרה אינה לשפוט מי צודק, אלא להבין ביחד מה קורה בינינו ולמצוא דרך שתעבוד לשניהם.</p>
              </div>
              <div className={styles.frictionCard}>
                <div className={styles.frictionEmoji} aria-hidden="true">💬</div>
                <h4>יש לנו שאלה לפני שקובעים — איך פונים?</h4>
                <p>אפשר לכתוב לשירה ישירות ב-WhatsApp. היא תחזור בהקדם עם תשובה ממוקדת, בלי מחויבות לקביעת פגישה.</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 10. שאלות נפוצות */}
      <section className={styles.sectionAlt}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>שאלות נפוצות</h2>
          </div>
          <div className={styles.faqAccordion}>
            {faqItems.map((item) => (
              <div key={item.question} className={styles.faqItem}>
                <details>
                  <summary>{item.question}</summary>
                  <p className={styles.faqAnswer}>{item.answer}</p>
                </details>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* 11. אזור הזמנת פגישה */}
      <section id="booking" className={`${styles.section} ${styles.bookingSection}`}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <FiCalendar aria-hidden="true" style={{ fontSize: '2rem', color: 'var(--color-accent)' }} />
            <h2>בחרו מועד לפגישת ייעוץ</h2>
            <p>בחרו את המועד המתאים והשלימו את ההזמנה ביומן. מחיר הפגישה הוא 500 ₪.</p>
          </div>

          <div className={styles.calendlyWrapper}>
            <iframe
              src={SITE_CONFIG.links.calendly}
              title="יומן קביעת פגישת ייעוץ זוגי באשדוד Calendly - שירה סהרוני"
              className={styles.calendlyFrame}
              loading="eager"
            />
          </div>

          <div className={styles.bookingHelp}>
            <span>לא מצאתם מועד מתאים?</span>
            <a
              href={whatsappUrl}
              target="_blank"
              rel="noopener noreferrer"
              onClick={trackWhatsappClick}
            >
              <FaWhatsapp aria-hidden="true" />
              כתבו לשירה ב-WhatsApp
            </a>
          </div>
        </div>
      </section>

      {/* 12. CTA מסכם */}
      <section className={styles.closingCta}>
        <div className="container">
          <h2>הצעד הראשון הוא שיחה מסודרת</h2>
          <p>אפשר לבחור מועד לפגישת ייעוץ בקליניקה באשדוד או אונליין.</p>
          <button
            type="button"
            className={styles.btnPrimary}
            onClick={() => scrollToBooking('closing_cta')}
          >
            קביעת פגישת ייעוץ – 500 ₪
          </button>
        </div>
      </section>

      {/* 13. Footer מצומצם */}
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

      {/* Mobile Sticky Bottom Bar */}
      {!isBookingInView && (
        <div className={styles.mobileStickyBar}>
          <button
            type="button"
            className={styles.mobileStickyBtn}
            onClick={() => scrollToBooking('mobile_sticky')}
          >
            <FiCheckCircle aria-hidden="true" />
            קביעת פגישה – 500 ₪
          </button>
        </div>
      )}
    </main>
  );
};

export default CouplesCounselingAshdodPage;
