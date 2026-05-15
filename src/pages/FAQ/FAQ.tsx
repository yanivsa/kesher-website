import React from 'react';
import MetaTags from '../../components/SEO/MetaTags';
import styles from './FAQ.module.css';

const FAQ: React.FC = () => {
  const faqs = [
    {
      question: "כמה פגישות נדרשות בתהליך ייעוץ זוגי?",
      answer: "זה משתנה מזוג לזוג, אך בדרך כלל תהליך משמעותי לוקח בין 10 ל-15 פגישות. יש זוגות שזקוקים לליווי ממושך יותר ויש כאלו שמגיעים למטרות נקודתיות של מספר פגישות בודדות."
    },
    {
      question: "מה ההבדל בין גישור לגירושין בבית משפט?",
      answer: "גישור הוא הליך בהסכמה שבו אתם קובעים את העתיד שלכם, בעוד שבבית משפט שופט חיצוני מחליט עבורכם. גישור הוא מהיר יותר, זול משמעותית ושומר על האווירה המשפחתית עבור הילדים."
    },
    {
      question: "האם את עובדת גם אונליין?",
      answer: "כן, בהחלט. אני מקיימת פגישות ייעוץ והדרכת הורים גם דרך ה-Zoom, מה שמאפשר גמישות רבה לזוגות ולהורים מכל רחבי הארץ."
    },
    {
      question: "איך הדרכת הורים יכולה לעזור לילד עם ADHD?",
      answer: "הדרכת הורים מעניקה לכם כלים להבין את המנגנון הנוירולוגי של הילד, לבנות שגרה תומכת ולהגיב בצורה שמפחיתה התפרצויות ומשפרת את שיתוף הפעולה בבית."
    }
  ];

  return (
    <div className={styles.faq}>
      <MetaTags 
        title="שאלות נפוצות | שירה סהרוני" 
        description="כל מה שרציתם לדעת על ייעוץ זוגי, הדרכת הורים וגישור. תשובות מקצועיות לשאלות שלכם." 
      />
      <header className={styles.header}>
        <div className="container">
          <h1>שאלות נפוצות</h1>
          <p>כאן תוכלו למצוא תשובות לשאלות שמעסיקות הורים וזוגות רבים.</p>
        </div>
      </header>
      <div className={`container ${styles.container}`}>
        <div className={styles.list}>
          {faqs.map((faq, index) => (
            <div key={index} className={styles.item}>
              <h3 className={styles.question}>{faq.question}</h3>
              <p className={styles.answer}>{faq.answer}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default FAQ;
