import React from 'react';
import { Link } from 'react-router-dom';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './TherapistBio.module.css';

const TherapistBio: React.FC = () => {
  return (
    <section className={styles.bioSection}>
      <div className="container">
        <div className={styles.bioWrapper}>
          <div className={styles.imageContainer}>
            <img
              src="/images/shira-saharoni.webp"
              alt="שירה סהרוני"
              width="300"
              height="300"
              loading="lazy"
            />
          </div>
          <div className={styles.textContent}>
            <h2>נעים להכיר, שירה סהרוני</h2>
            <p>
              יועצת זוגית, מנחת הורים ומגשרת מוסמכת. עורכת דין בהכשרתי, שבחרה להפנות את היכולת לנתח מצבים מורכבים, להקשיב לכל הצדדים ולבנות הסכמות — לעבודה עם זוגות, הורים ומשפחות.
            </p>
            <div className={styles.actions}>
              <Link to={SITE_CONFIG.links.appointment} className={styles.primaryCta}>
                קביעת פגישת ייעוץ
              </Link>
              <Link to="/about" className={styles.readMoreBtn}>
                לקריאה נוספת עליי
              </Link>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default TherapistBio;
