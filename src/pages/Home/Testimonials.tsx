import React from 'react';
import { useScrollReveal } from '../../hooks/useScrollReveal';
import styles from './Testimonials.module.css';

const testimonials = [
  {
    text: "הגענו לשירה בשיא המשבר. היא עזרה לנו להוריד את גובה הלהבות ולדבר בפעם הראשונה מזה שנים. השילוב של המקצועיות והרגישות שלה נתן לנו המון שקט.",
    author: "א. ו-מ., אשדוד"
  },
  {
    text: "הדרכת ההורים של שירה שינתה לנו את הבית. הכלים שקיבלנו להתמודדות עם ה-ADHD של הבן שלנו היו פרקטיים ועבדו מהיום הראשון.",
    author: "משפחת ל., גן יבנה"
  },
  {
    text: "שירה עזרה לנו למצוא את הדרך חזרה אחד לשנייה אחרי שנים של ריחוק ושחיקה. המקצועיות, הרגישות והכלים המעשיים שקיבלנו פשוט הצילו את הנישואין שלנו.",
    author: "ד. ס., דרום"
  }
];

const Testimonials: React.FC = () => {
  const [headerRef, headerVisible] = useScrollReveal();
  const [gridRef, gridVisible] = useScrollReveal({ threshold: 0.1 });

  return (
    <section className={styles.testimonials}>
      <div className="container">
        <div ref={headerRef} className={`${styles.header} reveal ${headerVisible ? 'visible' : ''}`}>
          <h2>מה אומרים עלי?</h2>
          <p>המלצות אנונימיות מהקליניקה.</p>
        </div>
        <div ref={gridRef} className={`${styles.grid} reveal-stagger ${gridVisible ? 'visible' : ''}`}>
          {testimonials.map((t, index) => (
            <div key={index} className={styles.card}>
              <div className={styles.quote}>"</div>
              <p className={styles.text}>{t.text}</p>
              <span className={styles.author}>{t.author}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default Testimonials;
