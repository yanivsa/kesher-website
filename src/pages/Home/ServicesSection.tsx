import React from 'react';
import { Link } from 'react-router-dom';
import { FiBookOpen, FiFileText, FiHeart, FiMessageCircle, FiUsers } from 'react-icons/fi';
import ServiceCard from '../../components/Services/ServiceCard';
import { useScrollReveal } from '../../hooks/useScrollReveal';
import styles from './ServicesSection.module.css';

const services = [
  {
    title: 'ייעוץ זוגי',
    description: 'לזוגות שנמצאים בלופים של ריבים, ריחוק או שחיקה ורוצים להבין מה קורה ביניהם לפני שמוותרים.',
    icon: <FiMessageCircle aria-hidden="true" />,
    highlights: ['מיפוי דפוסי התקשורת', 'כלים לשיחות קשות בלי הסלמה', 'חיזוק אמון, קרבה ושיתוף פעולה'],
    link: '/services/couples'
  },
  {
    title: 'הדרכת הורים',
    description: 'להורים שרוצים פחות מאבקי כוח בבית ויותר בהירות, גבולות ושיתוף פעולה עם הילדים.',
    icon: <FiUsers aria-hidden="true" />,
    highlights: ['סמכות הורית רגועה ועקבית', 'התמודדות עם ילדים ומתבגרים', 'ליווי סביב ADHD ואתגרי קשב'],
    link: '/services/parenting'
  },
  {
    title: 'גישור משפחתי',
    description: 'מרחב מובנה ומכבד לקבלת החלטות כשיש מחלוקת, פרידה או צורך בהסכמות משפחתיות.',
    icon: <FiFileText aria-hidden="true" />,
    highlights: ['חלופה רגועה יותר למאבק משפטי', 'שיחה שמחזירה שליטה לצדדים', 'התמקדות בטובת הילדים והמשפחה'],
    link: '/services/mediation'
  }
];

const specializations = [
  {
    title: "הכנה לכיתה א' לילדים עם ADHD",
    description: 'ליווי ממוקד להורים לקראת המעבר למסגרת בית הספר: שגרה, התארגנות, ויסות רגשי וקשר עם הצוות החינוכי.',
    icon: <FiBookOpen aria-hidden="true" />,
    link: '/services/parenting'
  },
  {
    title: 'הכנה לחתונה לזוגות שרוצים להתחיל נכון',
    description: 'בניית שפה זוגית והסכמות לפני החתונה, כולל ליווי למתחתנים שהוריהם גרושים ולזוגות שבהם אחד או שני בני הזוג מתמודדים עם ADHD.',
    icon: <FiHeart aria-hidden="true" />,
    link: '/services/couples'
  }
];

const ServicesSection: React.FC = () => {
  const [headerRef, headerVisible] = useScrollReveal();
  const [gridRef, gridVisible] = useScrollReveal({ threshold: 0.1 });

  return (
    <section id="services" className={styles.services}>
      <div className="container">
        <div 
          ref={headerRef} 
          className={`${styles.header} reveal ${headerVisible ? 'visible' : ''}`}
        >
          <h2 className={styles.title}>איך אוכל לעזור לכם?</h2>
          <p className={styles.subtitle}>
            שלושה שערי כניסה לאותו צורך: להוריד את עוצמת הקונפליקט, להבין את הדפוס שחוזר על עצמו, ולבנות דרך פעולה שאפשר ליישם בבית.
          </p>
        </div>
        <div 
          ref={gridRef} 
          className={`${styles.grid} reveal-stagger ${gridVisible ? 'visible' : ''}`}
        >
          {services.map((service, index) => (
            <ServiceCard key={index} {...service} />
          ))}
        </div>
        <div className={styles.specializations}>
          <div className={styles.specializationsHeader}>
            <h3>תחומי התמחות ממוקדים</h3>
            <p>הכנה מעשית לצמתים שבהם נכון לבנות כלים מראש, לפני שהעומס והחששות מנהלים את הבית או את הזוגיות.</p>
          </div>
          <div className={styles.specializationGrid}>
            {specializations.map((specialization) => (
              <Link key={specialization.title} to={specialization.link} className={styles.specializationItem}>
                <span className={styles.specializationIcon}>{specialization.icon}</span>
                <span>
                  <strong>{specialization.title}</strong>
                  <small>{specialization.description}</small>
                </span>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
};

export default ServicesSection;
