import React from 'react';
import MetaTags from '../../../components/SEO/MetaTags';
import LeadMagnet from '../../../components/LeadMagnet/LeadMagnet';
import { FiCheckSquare, FiClock, FiDollarSign, FiUsers } from 'react-icons/fi';
import styles from './Mediation.module.css';

const Mediation: React.FC = () => {
  return (
    <div className={styles.page}>
      <MetaTags 
        title="גישור גירושין ומשפחה באשדוד | שירה סהרוני" 
        description="גישור גירושין ומשפחה באשדוד. פתרון סכסוכים בדרכי שלום, בניית הסכמים וגירושין בשיתוף פעולה." 
      />
      
      <header className={styles.header}>
        <div className={`container ${styles.heroContainer}`}>
          <div className={styles.heroContent}>
            <div className={styles.badge}>פתרון סכסוכים בדרכי שלום</div>
            <h1>לסיים בטוב <br /><span>ולהישאר הורים</span></h1>
            <p className={styles.subtitle}>גישור משפחתי מקצועי המעניק לכם שליטה על העתיד שלכם ושל ילדיכם.</p>
            <a href="https://wa.me/972525267848" className={styles.ctaBtn}>תיאום פגישת היכרות</a>
          </div>
          <div className={styles.heroImageWrapper}>
            <img src="https://images.unsplash.com/photo-1573497019940-1c28c88b4f3e?auto=format&fit=crop&w=1200&q=80" alt="גישור משפחתי באשדוד" />
          </div>
        </div>
      </header>

      <section className={styles.benefits}>
        <div className="container">
          <h2 className={styles.sectionTitle}>למה לבחור בגישור על פני בית משפט?</h2>
          <div className={styles.benefitGrid}>
            <div className={styles.benefit}>
              <FiClock className={styles.icon} />
              <h3>חיסכון בזמן</h3>
              <p>תהליך הגישור אורך חודשים בודדים, לעומת שנים של דיונים בבית המשפט.</p>
            </div>
            <div className={styles.benefit}>
              <FiDollarSign className={styles.icon} />
              <h3>חיסכון כלכלי</h3>
              <p>שבריר מהעלות של ניהול מאבק משפטי עם שני עורכי דין נפרדים.</p>
            </div>
            <div className={styles.benefit}>
              <FiCheckSquare className={styles.icon} />
              <h3>שליטה מלאה</h3>
              <p>אתם אלו שקובעים את ההסכם ואת העתיד שלכם, לא שופט חיצוני שלא מכיר אתכם.</p>
            </div>
            <div className={styles.benefit}>
              <FiUsers className={styles.icon} />
              <h3>טובת הילדים</h3>
              <p>מניעת קונפליקטים קשים ושמירה על יכולת התקשורת שלכם כהורים בעתיד.</p>
            </div>
          </div>
        </div>
      </section>

      <section className={styles.expertise}>
        <div className="container">
          <div className={styles.expertiseBox}>
            <h2>הערך המוסף שלי כמגשרת</h2>
            <p>
              אני מביאה איתי ידע מעמיק בתהליכי גישור וניהול משא ומתן, לצד כלים רגשיים מעולם הטיפול. 
              זה מאפשר לי לנהל את המורכבות של הגישור ברגישות רבה, תוך שמירה על ענייניות והגעה להסכמות יציבות שיחזיקו מעמד לאורך שנים.
            </p>
          </div>
        </div>
      </section>

      <section className={styles.ctaBottom}>
        <div className="container">
          <LeadMagnet />
          <div className={styles.finalBox}>
            <h2>בואו נבנה הסכם שמכבד את כולם.</h2>
            <p>אני כאן כדי לעזור לכם לעבור את זה בדרך השפויה והנכונה ביותר.</p>
            <a href="/contact" className={styles.mainBtn}>דברו איתי</a>
          </div>
        </div>
      </section>
    </div>
  );
};

export default Mediation;
