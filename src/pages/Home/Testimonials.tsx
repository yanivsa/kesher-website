import React from 'react';
import { useScrollReveal } from '../../hooks/useScrollReveal';
import styles from './Testimonials.module.css';

const testimonials = [
  {
    text: "הגענו לשירה בשיא המשבר. היא עזרה לנו להוריד את גובה הלהבות ולדבר בפעם הראשונה מזה שנים. השילוב של המקצועיות והרגישות שלה נתן לנו המון שקט.",
    author: "א. ו-מ., אשדוד"
  },
  {
    text: "הדרכת ההורים של שירה עזרה לנו להבין טוב יותר את הקושי של הבן שלנו ולבנות שגרה רגועה וברורה יותר.",
    author: "משפחת ל., גן יבנה"
  },
  {
    text: "שירה עזרה לנו לדבר אחרת אחרי תקופה ארוכה של ריחוק ושחיקה. הרגישות והכלים המעשיים נתנו לנו דרך להתחיל להתקרב מחדש.",
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
          <h2>מילים ממשפחות שליוויתי</h2>
          <p>השמות והפרטים המזהים הושמטו כדי לשמור על פרטיות הפונים.</p>
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
