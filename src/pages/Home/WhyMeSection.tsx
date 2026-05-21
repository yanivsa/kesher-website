import React from 'react';
import { FiAward, FiHeart, FiShield, FiTrendingUp } from 'react-icons/fi';
import styles from './WhyMeSection.module.css';

const points = [
  {
    icon: <FiAward />,
    title: 'הסמכה רב-תחומית',
    description: 'השילוב בין ייעוץ זוגי, הנחיית הורים וגישור משפחתי מאפשר לי לראות את כל התמונה ולתת מענה שלם.'
  },
  {
    icon: <FiHeart />,
    title: 'גישה אנושית ורגישה',
    description: 'אני מאמינה שבתוך כל קונפליקט מסתתר רצון לחיבור. הטיפול שלי מבוסס על חמלה, הקשבה וביטחון רגשי.'
  },
  {
    icon: <FiTrendingUp />,
    title: 'כלים פרקטיים ליומיום',
    description: 'לא רק מדברים, אלא עושים. תקבלו ממני "שיעורי בית" וכלים יישומיים שיעבדו עבורכם כבר מהיום הראשון.'
  },
  {
    icon: <FiShield />,
    title: 'דיסקרטיות ומקצועיות',
    description: 'מחויבות מלאה לפרטיות שלכם ולסטנדרטים המקצועיים הגבוהים ביותר בעולם הגישור והטיפול.'
  }
];

const WhyMeSection: React.FC = () => {
  return (
    <section className={styles.whyMe}>
      <div className="container">
        <div className={styles.header}>
          <h2>למה לבחור לעבוד דווקא איתי?</h2>
          <p>הניסיון שלי מלמד שהדרך לשינוי עוברת דרך הבנה עמוקה של הצרכים של כל בני המשפחה.</p>
        </div>
        <div className={styles.grid}>
          {points.map((point, index) => (
            <div key={index} className={styles.card}>
              <div className={styles.iconWrapper}>{point.icon}</div>
              <h3 className={styles.cardTitle}>{point.title}</h3>
              <p className={styles.cardDescription}>{point.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default WhyMeSection;
