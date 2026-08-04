import React, { useState } from 'react';
import { FiChevronDown } from 'react-icons/fi';
import styles from './FAQSection.module.css';

const faqs = [
  {
    question: 'האם אפשר להגיע לייעוץ זוגי לבד?',
    answer: 'בהחלט. הרבה פעמים רק אחד מבני הזוג מרגיש צורך או מוכנות להתחיל בתהליך. אפשר להתחיל את הייעוץ לבד, לעבד את הקשיים ולהבין מה הייתם רוצים לשנות. פעמים רבות, עצם השינוי של אחד מבני הזוג משפיע לטובה על הדינמיקה הזוגית כולה ויכול בהמשך לעודד גם את הצד השני להצטרף.'
  },
  {
    question: 'איך נראית הפגישה הראשונה?',
    answer: 'הפגישה הראשונה היא פגישת היכרות שנועדה קודם כל לעשות סדר ולהבין מה מביא אתכם לכאן. כל אחד מקבל מקום לשתף את החוויה שלו, את הקשיים ואת הציפיות. בסיום הפגישה, ננסה להגדיר יחד את מוקד העבודה ונחליט יחד על אופן ההמשך.'
  },
  {
    question: 'כמה פגישות נצטרך?',
    answer: 'אין תשובה אחת שמתאימה לכולם. מספר הפגישות תלוי בסיבה שבגללה הגעתם, במטרות שלכם ובקצב שמתאים לכם. יש זוגות שזקוקים למספר פגישות ממוקדות סביב נושא ספציפי, ויש שבוחרים בתהליך ארוך יותר ומעמיק. בכל שלב אנחנו בודקים יחד איפה אנחנו עומדים.'
  },
  {
    question: 'האם זה מתאים גם לזוגות שלא נשואים?',
    answer: 'כן, כמובן. הייעוץ מתאים לכל שלב בזוגיות - לפני נישואים, בשנה הראשונה, לזוגות בפרק ב\', או לאנשים שנמצאים בתהליך של מציאת זוגיות ורוצים לבחון דפוסים אישיים. המיקוד הוא תמיד בדינמיקה, בתקשורת ובקשר עצמו, ולא בסטטוס הרשמי.'
  }
];

const FAQSection: React.FC = () => {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  const toggleFAQ = (index: number) => {
    setOpenIndex(openIndex === index ? null : index);
  };

  return (
    <section className={styles.faqSection}>
      <div className="container">
        <div className={styles.header}>
          <h2 className={styles.title}>שאלות נפוצות</h2>
          <p className={styles.subtitle}>
            תשובות לשאלות שעולות הרבה לפני שמתחילים תהליך ייעוץ.
          </p>
        </div>
        <div className={styles.faqGrid}>
          {faqs.map((faq, index) => {
            const isOpen = openIndex === index;
            return (
              <div key={index} className={styles.faqItem}>
                <button
                  className={styles.faqQuestion}
                  onClick={() => toggleFAQ(index)}
                  aria-expanded={isOpen}
                >
                  <span>{faq.question}</span>
                  <FiChevronDown className={styles.icon} aria-hidden="true" />
                </button>
                <div className={styles.faqAnswer} aria-hidden={!isOpen}>
                  <p>{faq.answer}</p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};

export default FAQSection;
