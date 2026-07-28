import React from 'react';
import { FiCalendar, FiMessageCircle, FiCheckCircle } from 'react-icons/fi';
import styles from './ProcessSection.module.css';

const steps = [
  {
    icon: <FiCalendar />,
    title: 'בוחרים מועד',
    description: 'קובעים פגישת ייעוץ של 50 דקות ביומן. אם אתם מעדיפים לברר משהו קודם, אפשר לשלוח הודעה.'
  },
  {
    icon: <FiMessageCircle />,
    title: 'נפגשים ומבררים',
    description: 'בפגישה הראשונה נקשיב למה שכל אחד מביא איתו. נברר מה קורה עכשיו, מה כבר ניסיתם ומה הייתם רוצים שייראה אחרת.'
  },
  {
    icon: <FiCheckCircle />,
    title: 'מחליטים על ההמשך',
    description: 'בסוף הפגישה נסכם את המוקד ואת האפשרויות להמשך. אין מספר פגישות קבוע מראש, וההחלטה מתקבלת יחד.'
  }
];

const ProcessSection: React.FC = () => {
  return (
    <section className={styles.process}>
      <div className="container">
        <div className={styles.header}>
          <h2>מה קורה כשפונים?</h2>
          <p>שלושה צעדים פשוטים, בלי צורך לדעת מראש בדיוק איך לקרוא למה שקורה.</p>
        </div>
        <div className={styles.grid}>
          {steps.map((step, index) => (
            <div key={index} className={styles.step}>
              <div className={styles.iconWrapper}>{step.icon}</div>
              <h3 className={styles.stepTitle}>{step.title}</h3>
              <p className={styles.stepDescription}>{step.description}</p>
              {index < steps.length - 1 && <div className={styles.connector} />}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default ProcessSection;
