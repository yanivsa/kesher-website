import React from 'react';
import { Link } from 'react-router-dom';
import { FiBookOpen, FiCompass, FiHeart, FiMessageCircle, FiStar, FiUsers } from 'react-icons/fi';
import ServiceCard from '../../components/Services/ServiceCard';
import { useScrollReveal } from '../../hooks/useScrollReveal';
import styles from './ServicesSection.module.css';

const services = [
  {
    title: 'ייעוץ זוגי',
    description: 'לזוגות שכל שיחה אצלם חוזרת לאותו ויכוח, או שהמרחק והשחיקה כבר מורגשים בחיי היום־יום.',
    icon: <FiMessageCircle aria-hidden="true" />,
    highlights: ['מיפוי דפוסי התקשורת', 'כלים לשיחות קשות בלי הסלמה', 'חיזוק אמון, קרבה ושיתוף פעולה'],
    link: '/services/couples'
  },
  {
    title: 'הדרכת הורים',
    description: 'להורים שמחפשים דרך ברורה יותר להגיב בבית, להציב גבולות וללוות ילד שזקוק להתאמות או להכנה למעבר.',
    icon: <FiUsers aria-hidden="true" />,
    highlights: ['הורים לילדים מחוננים', 'ADHD ותפקודים ניהוליים', 'הכנה למסגרות חינוכיות'],
    link: '/services/parenting'
  },
  {
    title: 'גישור',
    description: 'לבני זוג, בני משפחה, הורים, שכנים או שותפים שרוצים לנהל מחלוקת בצורה מסודרת ולנסח הסכמות שאפשר לקיים.',
    icon: <FiCompass aria-hidden="true" />,
    highlights: ['בירור צרכים ונושאים', 'הפחתת מתח והאשמות', 'הסכמות ישימות וברורות'],
    link: '/services/mediation'
  }
];

const specializations = [
  {
    title: 'הנחיית הורים לילדים מחוננים',
    description: 'ליווי סביב רגישות, פרפקציוניזם, שייכות, מוטיבציה ומחוננות לצד ADHD.',
    icon: <FiStar aria-hidden="true" />,
    link: '/services/gifted-parenting'
  },
  {
    title: "הכנה לכיתה א' ותפקודים ניהוליים",
    description: 'לילדים עם ADHD ולכל ילד שזקוק לחיזוק בהתארגנות, ויסות, עצמאות ושגרת למידה — יחד עם הוריו.',
    icon: <FiBookOpen aria-hidden="true" />,
    link: '/services/parenting'
  },
  {
    title: 'הכנה לכניסה למסגרת מחוננים',
    description: 'הכנה ניהולית, רגשית וחברתית לילד ולהוריו לקראת המעבר למסגרת החדשה.',
    icon: <FiCompass aria-hidden="true" />,
    link: '/services/gifted-parenting#gifted-framework'
  },
  {
    title: 'ייעוץ במצבי רווקות מאוחרת',
    description: 'ליווי אישי סביב שחיקה, לחץ מהסביבה, בדידות ודפוסים שחוזרים בקשרים ובהיכרויות.',
    icon: <FiHeart aria-hidden="true" />,
    link: '/services/late-singleness'
  },
  {
    title: 'ליווי למציאת זוגיות',
    description: 'ליווי מעשי סביב היכרויות, בחירת קשר, תקשורת, גבולות והמעבר מדייטים לזוגיות.',
    icon: <FiCompass aria-hidden="true" />,
    link: '/services/finding-relationship'
  },
  {
    title: 'משפחות עולים ותושבים חוזרים',
    description: 'ייעוץ זוגי והנחיית הורים סביב הסתגלות, מסגרות חדשות, שינוי תפקידים ותחושת שייכות בישראל.',
    icon: <FiHeart aria-hidden="true" />,
    link: '/services/aliyah-families'
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
            בחרו את הנושא שהכי קרוב למה שמעסיק אתכם. אם עדיין לא ברור מה מתאים, אפשר לברר זאת בפגישה הראשונה.
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
            <p>מענים להורים ולמשפחות סביב מחוננות, קשב ומעברים משמעותיים.</p>
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
