import React from 'react';
import { FiHeart, FiShield, FiTrendingUp } from 'react-icons/fi';
import styles from './WhyMeSection.module.css';

const points = [
  {
    icon: <FiHeart />,
    title: 'מקום גם למה שלא מסתדר',
    description: 'לא צריך להגיע עם סיפור מסודר או עם הסכמה בין בני הזוג. מתחילים ממה שכל אחד מצליח לומר כרגע.'
  },
  {
    icon: <FiTrendingUp />,
    title: 'תרגול בין הפגישות',
    description: 'כשזה מתאים, יוצאים מהפגישה עם שיחה, הרגל או צעד קטן שאפשר לנסות בבית ולבחון יחד בפעם הבאה.'
  },
  {
    icon: <FiShield />,
    title: 'גבולות מקצועיים ברורים',
    description: 'הפגישות דיסקרטיות. אם יתברר שהצורך דורש מענה אחר או נוסף, אדבר על כך באופן ישיר ואעזור להבין למי נכון לפנות.'
  }
];

const WhyMeSection: React.FC = () => {
  return (
    <section className={styles.whyMe}>
      <div className="container">
        <div className={styles.header}>
          <h2>מה אני מביאה לפגישה?</h2>
          <p>שילוב בין הקשבה, סדר ותרגול מעשי — בלי להבטיח פתרונות מהירים ובלי להעמיד פנים שיש תשובה אחת שמתאימה לכולם.</p>
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
