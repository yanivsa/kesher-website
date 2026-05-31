import React, { useState } from 'react';
import { FiChevronDown } from 'react-icons/fi';
import MetaTags from '../../components/SEO/MetaTags';
import SchemaOrg from '../../components/SEO/SchemaOrg';
import styles from './FAQ.module.css';

interface FAQItem {
  question: string;
  answer: string;
  category: string;
}

const FAQ: React.FC = () => {
  const [openIndex, setOpenIndex] = useState<number | null>(0);
  const [activeCategory, setActiveCategory] = useState('הכל');

  const faqs: FAQItem[] = [
    // ייעוץ זוגי
    {
      question: "כמה פגישות נדרשות בתהליך ייעוץ זוגי?",
      answer: "זה משתנה מזוג לזוג, אך בדרך כלל תהליך משמעותי לוקח בין 10 ל-15 פגישות. יש זוגות שזקוקים לליווי ממושך יותר ויש כאלו שמגיעים למטרות נקודתיות של מספר פגישות בודדות. בפגישת ההיכרות נגבש יחד תוכנית מותאמת.",
      category: "ייעוץ זוגי"
    },
    {
      question: "מתי כדאי לפנות לייעוץ זוגי?",
      answer: "כדאי לפנות כשיש קשיי תקשורת חוזרים, ריבים תכופים על אותם נושאים, ירידה באינטימיות, או כשאחד מבני הזוג שוקל פרידה. ככל שפונים מוקדם יותר, כך הסיכויים להצלחה גבוהים יותר. לא חייבים להגיע למשבר כדי לבקש עזרה.",
      category: "ייעוץ זוגי"
    },
    {
      question: "האם שני בני הזוג חייבים להגיע יחד?",
      answer: "מומלץ מאוד שכן, אך לא תמיד הכרחי. לפעמים אחד מבני הזוג מתחיל לבד ובהמשך השני מצטרף. שינוי בהתנהגות של אחד מבני הזוג יכול ליצור אפקט חיובי על כל מערכת היחסים.",
      category: "ייעוץ זוגי"
    },
    // גישור
    {
      question: "מה ההבדל בין גישור לפרידה בבית משפט?",
      answer: "גישור הוא הליך בהסכמה שבו אתם קובעים את העתיד שלכם, בעוד שבבית משפט שופט חיצוני מחליט עבורכם. גישור הוא מהיר יותר (2-4 חודשים לעומת שנים), זול משמעותית ושומר על האווירה המשפחתית עבור הילדים.",
      category: "גישור"
    },
    {
      question: "כמה עולה גישור משפחה?",
      answer: "עלות גישור משפחה נמוכה משמעותית מהליך משפטי. תהליך גישור טיפוסי כולל 4-8 פגישות ועולה פחות מחצי ממה שעולה ייצוג של שני עורכי דין. המחיר המדויק נקבע בהתאם למורכבות המקרה.",
      category: "גישור"
    },
    {
      question: "מה קורה בפגישת גישור ראשונה?",
      answer: "בפגישה הראשונה אני מכירה את שניכם, שומעת את הסיפור מכל צד ומסבירה את כללי התהליך. אנחנו בונים יחד את מפת הנושאים שצריך לפתור: רכוש, ילדים, מזונות ומגורים. זו פגישה ללא התחייבות.",
      category: "גישור"
    },
    {
      question: "האם הסכם גישור תקף משפטית?",
      answer: "כן. הסכם הגישור נחתם על ידי שני הצדדים ומוגש לאישור בית הדין הרבני או בית המשפט לענייני משפחה. לאחר אישורו, יש לו תוקף של פסק דין מחייב.",
      category: "גישור"
    },
    // הדרכת הורים
    {
      question: "איך הדרכת הורים יכולה לעזור לילד עם ADHD?",
      answer: "הדרכת הורים מעניקה לכם כלים להבין את המנגנון הנוירולוגי של הילד, לבנות שגרה תומכת ולהגיב בצורה שמפחיתה התפרצויות ומשפרת את שיתוף הפעולה בבית. מומחים רבים מדגישים שבגיל הרך, הדרכת ההורים לעיתים יעילה יותר מטיפול ישיר בילד.",
      category: "הדרכת הורים"
    },
    {
      question: "מה ההבדל בין הדרכת הורים לטיפול פסיכולוגי?",
      answer: "הדרכת הורים מתמקדת בכם — ההורים. אני מלמדת כלים פרקטיים לניהול מצבים יומיומיים: איך מגיבים לסירוב, איך מציבים גבולות בלי עונשים, איך בונים שגרה. טיפול פסיכולוגי מתמקד בעולם הפנימי של הילד. לפעמים צריך את שניהם.",
      category: "הדרכת הורים"
    },
    {
      question: "מגיל כמה ניתן להתחיל הדרכת הורים?",
      answer: "הדרכת הורים רלוונטית מגיל ינקות ועד גיל ההתבגרות. הכלים משתנים בהתאם לגיל הילד, אבל העיקרון זהה: להורים יש כוח עצום לשנות את הדינמיקה בבית כשהם מקבלים את הכלים הנכונים.",
      category: "הדרכת הורים"
    },
    // כללי
    {
      question: "האם את עובדת גם אונליין?",
      answer: "כן, בהחלט. אני מקיימת פגישות ייעוץ זוגי והדרכת הורים גם דרך ה-Zoom. זה מאפשר גמישות רבה לזוגות ולהורים מכל רחבי הארץ, ולעיתים אף נוח יותר — במיוחד להורים עם ילדים קטנים.",
      category: "כללי"
    },
    {
      question: "איך קובעים פגישה ראשונה?",
      answer: "הדרך הקלה ביותר היא דרך WhatsApp — שלחו הודעה קצרה ואחזור אליכם תוך 24 שעות. אפשר גם להשאיר פרטים בטופס באתר או להתקשר ישירות. שיחת ההיכרות הראשונה היא ללא עלות.",
      category: "כללי"
    }
  ];

  const categories = ['הכל', 'ייעוץ זוגי', 'גישור', 'הדרכת הורים', 'כללי'];

  const filteredFaqs = activeCategory === 'הכל' 
    ? faqs 
    : faqs.filter(f => f.category === activeCategory);

  const toggle = (index: number) => {
    setOpenIndex(openIndex === index ? null : index);
  };

  // FAQPage Schema for SEO/GEO
  const faqSchema = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    "mainEntity": faqs.map(faq => ({
      "@type": "Question",
      "name": faq.question,
      "acceptedAnswer": {
        "@type": "Answer",
        "text": faq.answer
      }
    }))
  };

  return (
    <div className={styles.faq}>
      <MetaTags 
        title="שאלות נפוצות | שירה סהרוני — ייעוץ זוגי, הדרכת הורים וגישור" 
        description="תשובות לשאלות נפוצות על ייעוץ זוגי, הדרכת הורים לילדים עם ADHD, גישור משפחה בהסכמה, טיפול מקוון ועוד."
      />
      <SchemaOrg data={faqSchema} />
      <header className={styles.header}>
        <div className="container">
          <h1>שאלות נפוצות</h1>
          <p>תשובות לשאלות שמעסיקות זוגות, הורים ומשפחות בתהליכי שינוי.</p>
        </div>
      </header>
      <div className={`container ${styles.container}`}>
        <div className={styles.categories}>
          {categories.map(cat => (
            <button 
              key={cat}
              className={`${styles.categoryBtn} ${activeCategory === cat ? styles.active : ''}`}
              onClick={() => { setActiveCategory(cat); setOpenIndex(null); }}
            >
              {cat}
            </button>
          ))}
        </div>
        <div className={styles.list}>
          {filteredFaqs.map((faq, index) => (
            <div 
              key={`${activeCategory}-${index}`} 
              className={`${styles.item} ${openIndex === index ? styles.open : ''}`}
            >
              <button 
                className={styles.question} 
                onClick={() => toggle(index)}
                aria-expanded={openIndex === index}
              >
                <span>{faq.question}</span>
                <FiChevronDown className={styles.chevron} />
              </button>
              <div className={styles.answerWrapper}>
                <p className={styles.answer}>{faq.answer}</p>
              </div>
            </div>
          ))}
        </div>

        <div className={styles.cta}>
          <h3>לא מצאתם תשובה?</h3>
          <p>אני כאן לכל שאלה. שלחו הודעה ואחזור אליכם תוך 24 שעות.</p>
          <a href="https://wa.me/972525267848" className={styles.ctaBtn}>
            שאלו אותי בוואטסאפ
          </a>
        </div>
      </div>
    </div>
  );
};

export default FAQ;
