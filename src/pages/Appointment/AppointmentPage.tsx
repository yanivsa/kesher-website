import React from 'react';
import { FaWhatsapp } from 'react-icons/fa';
import { FiCalendar, FiClock, FiMapPin, FiShield } from 'react-icons/fi';
import CalendlyBookingEmbed from '../../components/Booking/CalendlyBookingEmbed';
import MetaTags from '../../components/SEO/MetaTags';
import SchemaOrg from '../../components/SEO/SchemaOrg';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './AppointmentPage.module.css';

const schemaData = {
  '@context': 'https://schema.org',
  '@graph': [
    {
      '@type': 'Service',
      name: 'פגישת ייעוץ עם שירה סהרוני',
      serviceType: ['ייעוץ זוגי', 'הנחיית הורים', 'גישור'],
      url: `${SITE_CONFIG.url}/appointment`,
      provider: {
        '@type': 'Person',
        name: SITE_CONFIG.author,
      },
      areaServed: 'אשדוד וישראל באונליין',
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
          name: 'קביעת פגישה',
          item: `${SITE_CONFIG.url}/appointment`,
        },
      ],
    },
  ],
};

const AppointmentPage: React.FC = () => {
  return (
    <div className={styles.page}>
      <MetaTags
        title="קביעת פגישת ייעוץ עם שירה סהרוני"
        description="בחרו מועד לפגישת ייעוץ אישית עם שירה סהרוני — ייעוץ זוגי, הנחיית הורים או גישור, באשדוד או אונליין."
      />
      <SchemaOrg data={schemaData} />

      <header className={styles.header}>
        <div className={`container ${styles.headerContent}`}>
          <span className={styles.eyebrow}>מתחילים בשיחה</span>
          <h1>קביעת פגישת ייעוץ עם שירה</h1>
          <p>
            בחרו את המועד שנוח לכם. בפגישה נכיר, נבין מה מעסיק אתכם ונבחן יחד
            איזו דרך מקצועית יכולה להתאים.
          </p>
          <div className={styles.facts} aria-label="פרטי הפגישה">
            <span><FiClock aria-hidden="true" /> 50 דקות</span>
            <span><FiMapPin aria-hidden="true" /> אשדוד או אונליין</span>
            <span><FiShield aria-hidden="true" /> מרחב מכבד ודיסקרטי</span>
          </div>
        </div>
      </header>

      <section className={styles.bookingSection} aria-labelledby="booking-title">
        <div className={`container ${styles.bookingGrid}`}>
          <aside className={styles.intro}>
            <FiCalendar className={styles.calendarIcon} aria-hidden="true" />
            <h2 id="booking-title">בחרו מועד שמתאים לכם</h2>
            <p>
              לוח הזמנים מתעדכן אוטומטית. לאחר הבחירה תקבלו אישור וכל פרטי
              הפגישה ישירות למייל.
            </p>
            <ul>
              <li>ייעוץ זוגי ותקשורת בתוך הקשר</li>
              <li>הנחיית הורים והתמודדות משפחתית</li>
              <li>גישור ובניית הסכמות מעשיות</li>
            </ul>
            <div className={styles.help}>
              <strong>מעדיפים להתייעץ לפני שקובעים?</strong>
              <a
                href={SITE_CONFIG.links.whatsapp}
                target="_blank"
                rel="noopener noreferrer"
              >
                <FaWhatsapp aria-hidden="true" />
                שלחו הודעה לשירה
              </a>
            </div>
          </aside>

          <div className={styles.calendlyCard}>
            <CalendlyBookingEmbed
              ariaLabel="לוח זמנים לקביעת פגישת ייעוץ עם שירה סהרוני"
              serviceType="general_consultation"
              bookingPagePath="/appointment"
            />
          </div>
        </div>
      </section>
    </div>
  );
};

export default AppointmentPage;
