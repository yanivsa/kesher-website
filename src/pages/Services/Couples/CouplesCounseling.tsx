import React from 'react';
import ServicePageTemplate from '../../../components/ServicePageTemplate/ServicePageTemplate';
import styles from './CouplesCounseling.module.css';

const CouplesCounseling: React.FC = () => {
  const content = (
    <div className={styles.serviceContent}>
      <section className={styles.segment}>
        <h2>למי זה מתאים?</h2>
        <p>ייעוץ זוגי הוא לא רק 'מוצא אחרון' לפני פרידה. הוא מתאים לכם אם:</p>
        <ul>
          <li>אתם מרגישים שאתם בלופ של מריבות שחוזרות על עצמן.</li>
          <li>השתיקה והריחוק השתלטו על הבית.</li>
          <li>עברתם משבר אמון או בגידה ואתם רוצים לבנות מחדש.</li>
          <li>אתם מרגישים כמו 'שותפים לדירה' ופחות כמו בני זוג.</li>
        </ul>
      </section>

      <section className={styles.segment}>
        <h2>מה קורה בתהליך הייעוץ?</h2>
        <p>התהליך איתי הוא שילוב של הבנה רגשית עמוקה לבין כלים פרקטיים לשימוש מיידי בבית.</p>
        <div className={styles.steps}>
          <div className={styles.step}>
            <h3>1. אבחון ומיפוי</h3>
            <p>נבין את דפוסי התקשורת שלכם - מה 'מדליק' אתכם ואיפה אתם הולכים לאיבוד.</p>
          </div>
          <div className={styles.step}>
            <h3>2. רכישת כלים</h3>
            <p>תלמדו איך לדבר על הצרכים שלכם בלי להאשים, ואיך להקשיב בלי להתגונן.</p>
          </div>
          <div className={styles.step}>
            <h3>3. בניית אינטימיות</h3>
            <p>נעבוד על החזרת החברות, התשוקה והביטחון לקשר שלכם.</p>
          </div>
        </div>
      </section>

      <section className={styles.segment}>
        <h2>למה דווקא אצלי?</h2>
        <p>
          השילוב שלי כעורכת דין ומגשרת נותן לי את היכולת לראות את 'השורה התחתונה' ואת ההשלכות המשפטיות, 
          בעוד שהכובע כיועצת זוגית מאפשר לי לטפל בלב הפועם של הקשר - הרגש. אתם מקבלים מעטפת מלאה.
        </p>
      </section>
    </div>
  );

  return (
    <ServicePageTemplate
      title="ייעוץ זוגי באשדוד | שירה סהרוני"
      description="ייעוץ זוגי מקצועי ורגיש באשדוד. בואו לשפר את התקשורת, לפתור קונפליקטים ולהחזיר את האינטימיות לקשר."
      heroTitle="ייעוץ זוגי"
      heroSubtitle="הזדמנות לבנות מחדש את החיבור, הביטחון והחברות ביניכם."
      icon="💑"
      image="/images/generated/services/couples-room.jpg"
      content={content}
    />
  );
};

export default CouplesCounseling;
