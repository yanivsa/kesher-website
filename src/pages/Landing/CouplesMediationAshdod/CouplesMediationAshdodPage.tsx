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
import styles from './CouplesMediationAshdodPage.module.css';

const recognitionItems = [
  {
    title: 'שיחות שחוזרות שוב למבוי סתום',
    desc: 'מחלוקת עקרונית סביב כספים, חלוקת תפקידים או עתיד הקשר שתוקעת את ההתקדמות.',
  },
  {
    title: 'פחד מהסלמה למאבק הרסני',
    desc: 'רצון עמוק לפתור את הדברים בהסכמה ובכבוד הדדי, בלי להיגרר לעימותים ומלחמות מתישות.',
  },
  {
    title: 'קושי לתקשר בלי להיפגע',
    desc: 'כל ניסיון לנהל שיחה עניינית מידרדר במהירות להטחת האשמות הדדית ולתחושת תסכול.',
  },
  {
    title: 'רצון לשמור על הילדים והמשפחה',
    desc: 'הבנה ברורה שמחלוקות בין המבוגרים אינן צריכות לפגוע בביטחון וביציבות של הילדים.',
  },
  {
    title: 'פערים בציפיות ובצרכים',
    desc: 'כל צד מרגיש שהצד השני אינו רואה את נקודת המבט שלו ולא מבין מה באמת חשוב לו.',
  },
  {
    title: 'צורך במסגרת מקצועית וניטרלית',
    desc: 'הבנה שבכוחות עצמכם קשה לפרוץ את המחסום, ושדרוש גורם מוסמך שינהל את השיח.',
  },
];

const timelineSteps = [
  {
    time: '00–15 דק׳',
    title: 'הגדרת גבולות השיח ומיפוי הנושאים',
    desc: 'יוצרים מרחב מוגן, בטוח ומכבד. כל אחד מבני הזוג מציג את הסוגיות המרכזיות והדחופות ביותר עבורו, וממפים את נקודות ההסכמה ואת מוקדי המחלוקת.',
  },
  {
    time: '15–35 דק׳',
    title: 'זיהוי האינטרסים שמתחת לעמדות',
    desc: 'עוברים מוויכוח על "מי צודק" לבירור הצרכים, החששות והאינטרסים האמיתיים של כל צד. בוחנים נקודות מפגש שמאפשרות לבנות פתרונות מותאמים.',
  },
  {
    time: '35–50 דק׳',
    title: 'גיבוש מתווה ראשוני להמשך והסכמות',
    desc: 'מגדירים את סדר העבודה על הסוגיות שעל הפרק ויוצאים עם הבנות מעשיות ראשונות שאפשר ליישם כבר עכשיו, לקראת השלמת הסכמות יציבות.',
  },
];

const faqItems = [
  {
    question: 'מה ההבדל בין גישור זוגי לייעוץ זוגי?',
    answer: 'ייעוץ זוגי מתמקד בהבנת דפוסי התקשורת וחיזוק החיבור הרגשי, בעוד גישור זוגי מתמקד בניהול משא ומתן מכבד, יישוב מחלוקות מוגדרות והגעה להסכמות יציבות וברורות בין בני הזוג.',
  },
  {
    question: 'מה קורה בפגישת הגישור הראשונה?',
    answer: 'בפגישה הראשונה מגדירים את כללי השיח המכבד, ממפים את כל הנושאים הדורשים פתרון (הורות, כספים, שגרה, עתיד הקשר), ומתווים את הדרך להגעה להסכמות משותפות.',
  },
  {
    question: 'האם המגשרת מכריעה או קובעת מי צודק?',
    answer: 'לא. המגשרת אינה שופטת ואינה מכריעה. תפקידה לסייע לשני הצדדים לנהל שיח הוגן ובטוח, לזהות פתרונות מוסכמים ולשמור על האינטרסים של שניהם.',
  },
  {
    question: 'מה אם בן או בת הזוג חוששים שיפעילו עליהם לחץ?',
    answer: 'גישור מתקיים אך ורק מרצון חופשי. שירה סהרוני, כמגשרת מוסמכת ויועצת זוגית, מקפידה על שוויון מלא ועל כך שאף צד לא יחתום או יסכים למה שאינו שלם איתו.',
  },
  {
    question: 'כמה פגישות נדרשות בדרך כלל לתהליך גישור?',
    answer: 'מספר הפגישות תלוי בהיקף הנושאים ובקצב שבו בני הזוג מעוניינים להתקדם. אין התחייבות למספר פגישות מראש, וכל פגישה מקדמת את בניית ההסכמות.',
  },
  {
    question: 'כמה זמן נמשכת פגישה ומה עלותה?',
    answer: 'פגישת גישור נמשכת 50 דקות מלאות. עלות הפגישה היא 500 ₪ כולל מע״מ.',
  },
  {
    question: 'איפה מתקיימות הפגישות?',
    answer: 'הפגישות הפרונטליות מתקיימות בקליניקה באשדוד. כמו כן, ניתן לקיים פגישות מקוונות (Zoom) מכל מקום.',
  },
  {
    question: 'האם השיחות בגישור חסויות?',
    answer: 'הליך הגישור מתנהל בדיסקרטיות. אם חשוב לכם להבין מראש את גבולות החיסיון ואת אופן השימוש במידע שנמסר בתהליך, אפשר לברר זאת עם שירה לפני הפגישה.',
  },
];

const schemaData = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': ['LocalBusiness', 'ProfessionalService'],
      '@id': `${SITE_CONFIG.url}/couples-mediation-ashdod#service`,
      name: 'גישור זוגי באשדוד | שירה סהרוני',
      alternateName: 'קשר - גישור זוגי באשדוד',
      url: `${SITE_CONFIG.url}/couples-mediation-ashdod`,
      image: `${SITE_CONFIG.url}/images/generated/services/mediation-room.jpg`,
      telephone: '+972-50-2763802',
      email: SITE_CONFIG.contact.email,
      priceRange: '₪500',
      description: 'גישור זוגי מקצועי ומכבד באשדוד או אונליין. מרחב ניטרלי ליישוב מחלוקות, בניית הסכמות הדדיות וניהול שיח בטוח. שירה סהרוני, מגשרת מוסמכת. פגישה של 50 דקות, 500 ₪.',
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
      '@id': `${SITE_CONFIG.url}/couples-mediation-ashdod#breadcrumb`,
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
          name: 'גישור זוגי באשדוד',
          item: `${SITE_CONFIG.url}/couples-mediation-ashdod`,
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

const CouplesMediationAshdodPage: React.FC = () => {
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
    'היי שירה, הגעתי לעמוד הגישור הזוגי באשדוד ויש לי שאלה לפני שקובעים פגישה.',
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
        title="גישור זוגי באשדוד | שירה סהרוני - מגשרת מוסמכת"
        description="גישור זוגי מקצועי ומכבד באשדוד או אונליין. מרחב ניטרלי ליישוב מחלוקות, בניית הסכמות הדדיות וניהול שיח בטוח. שירה סהרוני, מגשרת מוסמכת. פגישה של 50 דקות, 500 ₪."
        canonical={`${SITE_CONFIG.url}/couples-mediation-ashdod`}
        image="/images/generated/services/mediation-room.jpg"
      />
      <SchemaOrg data={schemaData} />

      {/* 1. Header מצומצם */}
      <header className={styles.header}>
        <div className={`container ${styles.headerInner}`}>
          <a href="/" className={styles.brand} aria-label="לדף הבית של שירה סהרוני">
            <div className={styles.brandText}>
              <span className={styles.brandTitle}>שירה סהרוני</span>
              <span className={styles.brandSubtitle}>קשר | גישור זוגי באשדוד</span>
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
      <section className={styles.heroSection} aria-labelledby="mediation-ashdod-title">
        <div className={`container ${styles.heroGrid}`}>
          <div className={styles.heroContent}>
            <div className={styles.heroTag}>
              <FiHeart aria-hidden="true" />
              <span>קליניקה באשדוד ובאונליין | שירה סהרוני</span>
            </div>
            <h1 id="mediation-ashdod-title" className={styles.heroTitle}>
              גישור זוגי באשדוד – בניית הסכמות ושיח מכבד
            </h1>
            <p className={styles.heroSubtitle}>
              גישור זוגי באשדוד עם שירה סהרוני מתאים לבני זוג שיש ביניהם מחלוקת מוגדרת ורוצים לנהל אותה במסגרת מקצועית וניטרלית. בפגישה ממפים את הנושאים, מבררים את הצרכים של שני הצדדים ובוחנים הסכמות מעשיות שניתן ליישם; אפשר להתחיל בקביעת פגישה או בשאלה קצרה ב-WhatsApp.
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
                <span>מרחב ניטרלי והוגן</span>
              </div>
              <div className={styles.trustPoint}>
                <FiClock className={styles.trustIcon} aria-hidden="true" />
                <span>הסכמות יציבות ומעשיות</span>
              </div>
              <div className={styles.trustPoint}>
                <FiLock className={styles.trustIcon} aria-hidden="true" />
                <span>חיסיון מלא ודיסקרטיות</span>
              </div>
            </div>
          </div>
          <div className={styles.heroImageWrapper}>
            <img
              src="/images/generated/services/mediation-room.jpg"
              alt="שירה סהרוני - גישור זוגי באשדוד"
              className={styles.heroImage}
              width="1600"
              height="900"
              fetchPriority="high"
            />
            <div className={styles.heroImageBadge}>
              שירה סהרוני | מגשרת מוסמכת ויועצת זוגית
            </div>
          </div>
        </div>
      </section>

      {/* 3. אזור הזדהות עם הצורך (Recognition) */}
      <section className={styles.sectionAlt}>
        <div className="container">
          <div className={styles.sectionHeader}>
            <h2>הסכם פרידה מכבד מחוץ לכותלי בית המשפט או חזרה לשיח בונה</h2>
            <p>
              כשלא מצליחים להסכים על נושאים מהותיים – כספים, התנהלות הבית, שגרת הילדים או עתיד הקשר – התסכול גובר במהירות. כל ניסיון לדבר מדרדר לוויכוחים מתישים, לתחושת חוסר אונים ולפחד מהסלמה. במקום להישאר תקועים או להיגרר לעימותים הרסניים, אפשר לבחור בדרך של שיח מובנה ומכבד.
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
            <h2>בניית הסכמות משותפות ושלום בית – מחלוקת אינה חייבת להפוך למאבק</h2>
            <div className={styles.hopeContent}>
              <p>
                גישור זוגי מאפשר לעצור את ההסלמה, לפרק את המוקשים ולמצוא פתרונות מציאותיים ששני הצדדים יכולים לחיות איתם בשלום.
              </p>
              <p>
                כשיש מסגרת מקצועית שמבטיחה ששני הקולות יישמעו בהגינות וללא איומים, אפשר להפוך מתח מתמשך להסכמות יציבות וברורות שמחזירות את השקט לחיים.
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
              50 דקות ממוקדות שמעניקות ודאות וסדר. מגדירים את הכללים לשיח מכבד, ממפים יחד את הסוגיות שדורשות מענה ובוחנים כיוונים להסכמות ראשוניות.
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
            אין מספר קבוע של פגישות שמתאים לכל מקרה. התהליך מותאם לקצב שלכם ולנושאים שעל הפרק.
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

      {/* 6. התמודדות עם חששות הצדדים */}
      <section className={styles.resistanceSection}>
        <div className="container">
          <div className={styles.resistanceBox}>
            <h2>ומה אם אחד מאיתנו חושש שיפעילו עליו לחץ לוותר?</h2>
            <div className={styles.resistanceBody}>
              <p>
                זהו חשש מובן לחלוטין. ברגעי מחלוקת קיים פחד שצד אחד יהיה משכנע יותר, או שהמגשרת תיקח צד ותלחץ על אחד מכם להסכים לדברים שאינם מתאימים לו.
              </p>
              <p>
                זה לא קורה בגישור. שירה סהרוני, כמגשרת מוסמכת ויועצת זוגית, מחויבת לניטרליות מוחלטת ולהגנה על זכותו של כל צד להשמיע את דעתו ולהסכים רק לפתרונות הוגנים ושלמים עבורו.
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
              src="/images/shira-saharoni-consult.webp"
              alt="שירה סהרוני - מגשרת מוסמכת ויועצת זוגית"
              className={styles.aboutImage}
              width="477"
              height="600"
              loading="lazy"
            />
          </div>
          <div className={styles.aboutContent}>
            <h2>גישור זוגי מוסמך באשדוד – מרחב בטוח וניטרלי להסכמות</h2>
            <span className={styles.aboutRole}>
              שירה סהרוני | מגשרת מוסמכת ויועצת זוגית
            </span>
            <p>
              כמגשרת מוסמכת ויועצת זוגית, אני מביאה לחדר הגישור שילוב של הקשבה עמוקה, יסודיות בהגדרת הסכמות, ורגישות אנושית רבה למורכבות הרגשית של בני הזוג.
            </p>
            <p>
              המטרה אינה להילחם על "מי מנצח", אלא ליצור הסכמות ששני הצדדים שלמים איתן, ושמבטיחות יציבות וכבוד הדדי גם בעתיד.
            </p>

            <ul className={styles.trustPointsList}>
              <li>
                <strong>ניטרליות ללא פשרות:</strong>
                <span>שמירה מלאה על כבודם והאינטרסים של שני בני הזוג.</span>
              </li>
              <li>
                <strong>הסכמות ברורות וסדורות:</strong>
                <span>ניסוח פתרונות מעשיים וישימים שמונעים חיכוכים עתידיים.</span>
              </li>
              <li>
                <strong>מרחב בטוח וחסוי:</strong>
                <span>דיאלוג ישיר ומכבד בסביבה דיסקרטית ומקצועית.</span>
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
            <h2>שאלות נפוצות על גישור זוגי</h2>
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
              אם אתם עומדים מול מחלוקת משמעותית ורוצים להגיע להסכמות בדרך מכבדת ויציבה, אפשר לבחור מועד לפגישת גישור. הפגישה מתקיימת בקליניקה באשדוד או אונליין.
            </p>
          </div>

          <div className={styles.calendlyWrapper}>
            <CalendlyBookingEmbed
              ariaLabel="לוח זמנים לקביעת פגישת גישור זוגי באשדוד עם שירה סהרוני"
              serviceType="couples_mediation"
              bookingPagePath="/couples-mediation-ashdod"
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
          <h2>מחלוקת אפשר לפתור בהסכמה ובכבוד</h2>
          <p>מספיק להתחיל משיחה אחת מובנית כדי למצוא את הדרך המשותפת קדימה.</p>
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

export default CouplesMediationAshdodPage;
