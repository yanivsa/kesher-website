import React from 'react';
import MetaTags from '../../components/SEO/MetaTags';
import AboutSection from '../Home/AboutSection';
import styles from './AboutPage.module.css';

const AboutPage: React.FC = () => {
  return (
    <div className={styles.page}>
      <MetaTags 
        title="אודות שירה סהרוני | יועצת זוגית ומגשרת באשדוד" 
        description="הכירו את שירה סהרוני - עורכת דין, מגשרת מוסמכת ויועצת זוגית. שילוב ייחודי של הבנה משפטית וראייה טיפולית רגישה." 
      />
      <header className={styles.header}>
        <div className="container">
          <h1>אודותי</h1>
          <p>השילוב בין עולם המשפט לעולם הרגש - למען מערכות היחסים שלכם.</p>
        </div>
      </header>
      <AboutSection />
      <section className={styles.extraContent}>
        <div className="container">
          <h2>האני המאמין שלי</h2>
          <p>
            אני מאמינה שכל אדם וכל זוג נושאים בתוכם את הכוח לשינוי. התפקיד שלי הוא להעניק את המרחב הבטוח, את הכלים המקצועיים ואת הליווי הרגיש שמאפשר לכוח הזה לצאת אל הפועל.
          </p>
          <p>
            בין אם זה בחדר הגישור או בספת הייעוץ, המטרה שלי היא תמיד אחת: לייצר חיבור. חיבור של אדם לעצמו, חיבור בין בני זוג, וחיבור בין הורים לילדיהם.
          </p>
        </div>
      </section>
    </div>
  );
};

export default AboutPage;
