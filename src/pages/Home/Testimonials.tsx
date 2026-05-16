import React from 'react';
import styles from './Testimonials.module.css';

const Testimonials: React.FC = () => {
  const testimonials = [
    {
      text: "הגענו לשירה בשיא המשבר. היא עזרה לנו להוריד את גובה הלהבות ולדבר בפעם הראשונה מזה שנים. השילוב של הידע המשפטי שלה נתן לנו המון שקט.",
      author: "א. ו-מ., אשדוד"
    },
    {
      text: "הדרכת ההורים של שירה שינתה לנו את הבית. הכלים שקיבלנו להתמודדות עם ה-ADHD של הבן שלנו היו פרקטיים ועבדו מהיום הראשון.",
      author: "משפחת ל., גן יבנה"
    },
    {
      text: "תהליך הגישור היה קצר, ענייני ומכבד מאוד. חסכנו המון כסף ועוגמת נפש בבתי משפט. ממליצה בחום לכל מי שרוצה לסיים בטוב.",
      author: "ד. ס., דרום"
    }
  ];

  return (
    <section className={styles.testimonials}>
      <div className="container">
        <div className={styles.header}>
          <h2>מה אומרים עלי?</h2>
          <p>המלצות אנונימיות מחדר הטיפולים והגישור.</p>
        </div>
        <div className={styles.grid}>
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
