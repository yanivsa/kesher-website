import React from 'react';
import styles from './ProcessSection.module.css';

const steps = [
  {
    title: 'שיחה ראשונה',
    text: 'בודקים בקצרה מה מביא אתכם עכשיו, מה דחוף, ואיזה סוג ליווי מתאים: זוגי, הורי או גישורי.'
  },
  {
    title: 'מיפוי משותף',
    text: 'מזהים את הדפוסים שחוזרים בבית, את המקומות שבהם השיחה נתקעת, ואת המטרות שחשוב לכם להשיג.'
  },
  {
    title: 'כלים והסכמות',
    text: 'מתרגמים את ההבנות לפעולות קטנות וברורות: דרך לדבר, דרך לקבל החלטות, ודרך להוריד הסלמה ברגעי עומס.'
  }
];

const ProcessSection: React.FC = () => {
  return (
    <section className={styles.process}>
      <div className={`container ${styles.container}`}>
        <div className={styles.header}>
          <p className={styles.eyebrow}>איך זה נראה בפועל</p>
          <h2>תהליך קצר, ברור וממוקד במה שקורה אצלכם בבית</h2>
        </div>
        <div className={styles.steps}>
          {steps.map((step, index) => (
            <article className={styles.step} key={step.title}>
              <span className={styles.number}>{index + 1}</span>
              <h3>{step.title}</h3>
              <p>{step.text}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
};

export default ProcessSection;
