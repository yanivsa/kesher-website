import React from 'react';
import { FaWhatsapp } from 'react-icons/fa';
import { FiArrowLeft } from 'react-icons/fi';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './Hero.module.css';

const Hero: React.FC = () => {
  return (
    <section className={styles.hero}>
      <div className={`container ${styles.container}`}>
        <div className={styles.content}>
          <p className={styles.eyebrow}>שירה סהרוני | ייעוץ זוגי, הדרכת הורים וגישור באשדוד ובאונליין</p>
          <h1 className={styles.title}>
            כשמערכת היחסים בבית יוצאת מאיזון, לא חייבים להישאר לבד עם זה.
          </h1>
          <p className={styles.description}>
            ליווי מקצועי ורגיש לזוגות, הורים ומשפחות שרוצים להפחית קונפליקטים, לדבר אחרת, ולקבל החלטות משפחתיות מתוך שקט ובהירות.
          </p>
          <div className={styles.actions}>
            <a href={SITE_CONFIG.links.whatsapp} className={styles.primaryBtn}>
              <FaWhatsapp aria-hidden="true" />
              קביעת שיחת היכרות
            </a>
            <a href="#services" className={styles.secondaryBtn}>
              במה אפשר לעזור?
              <FiArrowLeft aria-hidden="true" />
            </a>
          </div>
          <div className={styles.trustBar} aria-label="תחומי התמחות">
            <span>ייעוץ זוגי</span>
            <span>הדרכת הורים</span>
            <span>גישור משפחתי</span>
          </div>
        </div>
        <div className={styles.imageContainer}>
          <div className={styles.imageWrapper}>
            <img 
              src="https://images.unsplash.com/photo-1493663284031-b7e3aefcae8e?auto=format&fit=crop&w=1200&q=80" 
              alt="מרחב בטוח לייעוץ וגישור" 
              className={styles.heroImage}
            />
            <div className={styles.overlay}></div>
            <div className={styles.photoNote}>
              <strong>מרחב דיסקרטי ומכבד</strong>
              <span>לפגישות זוגיות, הוריות ומשפחתיות</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Hero;
