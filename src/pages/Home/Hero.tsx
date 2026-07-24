import React from 'react';
import { FiArrowLeft, FiCalendar } from 'react-icons/fi';
import { Link } from 'react-router-dom';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './Hero.module.css';

const Hero: React.FC = () => {
  return (
    <section className={styles.hero}>
      <div className={`container ${styles.container}`}>
        <div className={styles.content}>
          <div className={styles.badge}>שירה סהרוני — ליווי זוגות ומשפחות</div>
          <h1 className={styles.title}>
            כשקשה לדבר בבית, <br />
            <span>אפשר להתחיל לעשות סדר.</span>
          </h1>
          <p className={styles.description}>
            ייעוץ זוגי, הנחיית הורים וגישור עם שירה סהרוני.
            פגישות באשדוד ובאונליין, בקצב שמתאים למה שקורה אצלכם עכשיו.
          </p>
          <div className={styles.actions}>
            <Link to={SITE_CONFIG.links.appointment} className={styles.primaryBtn}>
              <FiCalendar aria-hidden="true" />
              קביעת פגישת ייעוץ
            </Link>
            <Link to="/#services" className={styles.secondaryBtn}>
              מציאת הליווי המתאים
              <FiArrowLeft aria-hidden="true" />
            </Link>
          </div>
          <div className={styles.trustBar} aria-label="תחומי התמחות">
            <span>עורכת דין בהכשרתה</span>
            <span>מגשרת מוסמכת</span>
            <span>יועצת זוגית</span>
            <span>מנחת הורים</span>
          </div>
        </div>
        <div className={styles.imageContainer}>
          <div className={styles.imageWrapper}>
            <img 
              src="/images/generated/site/home-hero.jpg" 
              alt="חדר הייעוץ של שירה סהרוני באשדוד"
              className={styles.heroImage}
              width="1600"
              height="900"
              fetchPriority="high"
            />
            <div className={styles.overlay}></div>
          </div>
          <div className={styles.photoNote}>
            <strong>פגישה אישית ודיסקרטית</strong>
            <span>פגישות באשדוד ובאונליין</span>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Hero;
