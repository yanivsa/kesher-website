import React from 'react';
import ServicePageTemplate from '../../../components/ServicePageTemplate/ServicePageTemplate';
import styles from './Mediation.module.css';

const Mediation: React.FC = () => {
  const content = (
    <div className={styles.serviceContent}>
      <section className={styles.segment}>
        <h2>למה לבחור בגישור גירושין?</h2>
        <p>גישור הוא לא רק חלופה לבית משפט, הוא דרך חיים. הוא מאפשר לכם לסיים את הפרק הזוגי בכבוד ולבנות את הפרק הבא כהורים משותפים. היתרונות המרכזיים:</p>
        <ul>
          <li><strong>שליטה מלאה:</strong> אתם מחליטים על העתיד שלכם, לא שופט.</li>
          <li><strong>חיסכון משמעותי:</strong> שבריר מהעלות של ניהול מאבק משפטי עם שני עורכי דין.</li>
          <li><strong>מהירות ויעילות:</strong> תהליך שאורך חודשים בודדים במקום שנים בבתי משפט.</li>
          <li><strong>טובת הילדים:</strong> מניעת קונפליקטים קשים שפוגעים בנפש הילד.</li>
        </ul>
      </section>

      <section className={styles.segment}>
        <h2>איך נראה תהליך הגישור אצלי?</h2>
        <div className={styles.steps}>
          <div className={styles.step}>
            <h3>1. פתיחת הליך</h3>
            <p>הבנת הצרכים והנושאים שעל הפרק: רכוש, מזונות, והסדרי שהות.</p>
          </div>
          <div className={styles.step}>
            <h3>2. בניית הסכמות</h3>
            <p>ניהול משא ומתן מכבד וחיפוש פתרונות יצירתיים שטובים לכולם.</p>
          </div>
          <div className={styles.step}>
            <h3>3. חתימה ואישור</h3>
            <p>גיבוש הסכם משפטי מפורט והגשתו לאישור בית המשפט (תוקף של פסק דין).</p>
          </div>
        </div>
      </section>

      <section className={styles.segment}>
        <h2>הערך המוסף שלי כמגשרת</h2>
        <p>
          אני מביאה איתי ידע מעמיק בתהליכי גישור וניהול משא ומתן, לצד כלים רגשיים מעולם הטיפול. 
          זה מאפשר לי לנהל את המורכבות של הגישור ברגישות רבה, תוך שמירה על ענייניות והגעה להסכמות יציבות.
        </p>
      </section>
    </div>
  );

  return (
    <ServicePageTemplate
      title="גישור גירושין אשדוד | שירה סהרוני מגשרת מוסמכת"
      description="גישור גירושין ומשפחה באשדוד. פתרון סכסוכים בדרכי שלום, בניית הסכמים וגירושין בשיתוף פעולה."
      heroTitle="גישור משפחתי"
      heroSubtitle="לסיים בדרכי שלום, להתחיל בביטחון."
      icon="⚖️"
      image="https://images.unsplash.com/photo-1573497019940-1c28c88b4f3e?auto=format&fit=crop&w=1200&q=80"
      content={content}
    />
  );
};

export default Mediation;
