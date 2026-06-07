import React from 'react';
import { Link } from 'react-router-dom';
import { FiBookOpen, FiFileText, FiHeart, FiMessageCircle, FiUsers, FiZap } from 'react-icons/fi';
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
    title: 'הכנת זוגות לקראת חתונה',
    description: 'בניית שפה זוגית והסכמות לפני החתונה, עם רגישות מיוחדת למתחתנים שגדלו עם הורים גרושים.',
    icon: <FiHeart aria-hidden="true" />,
    link: '/services/couples'
  },
  {
    title: 'זוגיות כשאחד מבני הזוג עם ADHD',
    description: 'הבנת השפעת הקשב על עומס, משימות, תקשורת ואינטימיות, ובניית כלים שמתאימים לשני בני הזוג.',
    icon: <FiZap aria-hidden="true" />,
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
            <p>ליווי שמותאם לצמתים משפחתיים וזוגיים שדורשים הבנה מדויקת וכלים מעשיים.</p>
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
