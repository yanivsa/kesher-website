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
            לצאת מהפלונטר הזוגי <br />
            <span>עם ביטחון וכלים פרקטיים.</span>
          </h1>
          <p className={styles.description}>
            שירה סהרוני — מגשרת מוסמכת ויועצת זוגית. עוזרת לכם לצלוח משברים, 
            לבנות הורות משותפת חזקה או לסיים קשר בדרך מכבדת — תוך שמירה על הלב ועל השקט הנפשי שלכם.
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
              src="https://images.unsplash.com/photo-1493663284031-b7e3aefcae8e?auto=format&fit=crop&w=1200&q=80" 
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
