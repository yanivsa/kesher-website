import React from 'react';
import { FaWhatsapp } from 'react-icons/fa';
import { FiArrowLeft } from 'react-icons/fi';
import { Link } from 'react-router-dom';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './Hero.module.css';

const Hero: React.FC = () => {
  return (
    <section className={styles.hero}>
      <div className={`container ${styles.container}`}>
        <div className={styles.content}>
          <div className={styles.badge}>מענה רגשי מקיף + גישור מקצועי</div>
          <h1 className={styles.title}>
            להחזיר את השקט והקירבה <br />
            <span>לזוגיות ולמשפחה שלכם.</span>
          </h1>
          <p className={styles.description}>
            שירה סהרוני - יועצת זוגית, מנחת הורים ומגשרת מוסמכת.
            ליווי רגיש, פרקטי ודיסקרטי שנועד להוציא אתכם ממעגל המריבות ולבנות מחדש תקשורת בריאה, אמון וקירבה.
          </p>
          <div className={styles.actions}>
            <a href={SITE_CONFIG.links.whatsapp} className={styles.primaryBtn}>
              <FaWhatsapp aria-hidden="true" />
              שיחת היכרות בוואטסאפ
            </a>
            <Link to="/about" className={styles.secondaryBtn}>
              במה אני יכולה לעזור לכם?
              <FiArrowLeft aria-hidden="true" />
            </Link>
          </div>
          <div className={styles.trustBar} aria-label="תחומי התמחות">
            <span>יועצת זוגית</span>
            <span>מנחת הורים</span>
            <span>מגשרת מוסמכת</span>
          </div>
        </div>
        <div className={styles.imageContainer}>
          <div className={styles.imageWrapper}>
            <img 
              src="/images/generated/site/home-hero.jpg" 
              alt="מרחב בטוח לייעוץ וגישור - שירה סהרוני" 
              className={styles.heroImage}
            />
            <div className={styles.overlay}></div>
            <div className={styles.photoNote}>
              <strong>מרחב דיסקרטי ומכבד</strong>
              <span>פגישות באשדוד ובאונליין</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Hero;
