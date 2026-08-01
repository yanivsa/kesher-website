import React from 'react';
import { FiCalendar, FiMessageCircle, FiCheckCircle } from 'react-icons/fi';
import styles from './ProcessSection.module.css';

const steps = [
  {
    icon: <FiCalendar />,
    title: 'תיאום מועד',
    description: 'מתאמים פגישת היכרות של 50 דקות, בקליניקה באשדוד או באונליין. אפשר לקבוע ישירות ביומן או לשלוח הודעה לבירור מוקדם.'
  },
  {
    icon: <FiMessageCircle />,
    title: 'פגישת היכרות ומיפוי',
    description: 'במפגש הראשון אנחנו קודם כל עושים סדר. נקשיב לכל הצדדים, נמפה את הקשיים ונבין מה ניסיתם ומה תרצו לשנות.'
  },
  {
    icon: <FiCheckCircle />,
    title: 'החלטה על אופן העבודה',
    description: 'בסיום הפגישה נגדיר יחד את מוקד העבודה ונסכם איך נכון להתקדם. ההחלטה על ההמשך מתקבלת תמיד במשותף.'
  }
];

const ProcessSection: React.FC = () => {
  return (
    <section className={styles.process}>
      <div className="container">
        <div className={styles.header}>
          <h2>איך נראה תהליך הליווי?</h2>
          <p>שלושה שלבים ברורים, בלי צורך לדעת מראש איך בדיוק להגדיר את הקושי.</p>
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
