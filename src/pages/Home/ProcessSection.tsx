import React from 'react';
import { FiPhoneCall, FiMap, FiHeart, FiCheckCircle } from 'react-icons/fi';
import styles from './ProcessSection.module.css';

const steps = [
  {
    icon: <FiPhoneCall />,
    title: 'שיחת היכרות קצרה',
    description: 'שיחת היכרות קצרה בטלפון או בזום ללא התחייבות, כדי להבין את הצרכים שלכם ולראות איך אני יכולה לעזור.'
  },
  {
    icon: <FiMap />,
    title: 'פגישת מיפוי ואבחון',
    description: 'צלילה לעומק הדינמיקה, הבנת החסמים המרכזיים ובניית מפת דרכים אישית.'
  },
  {
    icon: <FiHeart />,
    title: 'תהליך הליווי הזוגי או ההורי',
    description: 'סדרת מפגשים ממוקדים בקליניקה או באונליין, שבהם תקבלו כלים פרקטיים לשינוי התנהגותי ותקשורתי.'
  },
  {
    icon: <FiCheckCircle />,
    title: 'תוצאה: שקט ובהירות',
    description: 'יציאה לדרך חדשה עם כלים ברורים, תקשורת מקרבת ותחושת ביטחון בבית.'
  }
];

const ProcessSection: React.FC = () => {
  return (
    <section className={styles.process}>
      <div className="container">
        <div className={styles.header}>
          <h2>איך זה עובד? המסע שלכם איתי</h2>
          <p>תהליך מובנה, רגיש ומקצועי שמוריד את מפלס החרדה ומייצר תוצאות בשטח.</p>
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
