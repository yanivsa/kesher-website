import React from 'react';
import ServiceCard from '../../components/Services/ServiceCard';
import styles from './ServicesSection.module.css';

const ServicesSection: React.FC = () => {
  const services = [
    {
      title: 'ייעוץ זוגי',
      description: 'בניית תקשורת מקרבת, פתרון קונפליקטים והחזרת האינטימיות והחברות לקשר הזוגי.',
      icon: '💑',
      link: '#couples'
    },
    {
      title: 'הדרכת הורים',
      description: 'כלים פרקטיים להתמודדות עם אתגרי ההורות, סמכות הורית וליווי הורים לילדים עם ADHD.',
      icon: '👨‍👩‍👧',
      link: '#parenting'
    },
    {
      title: 'גישור משפחתי',
      description: 'ליווי מקצועי ומשפטי לפתרון סכסוכים, גירושין בשיתוף פעולה ובניית הסכמים מחוץ לכותלי בית המשפט.',
      icon: '⚖️',
      link: '#mediation'
    }
  ];

  return (
    <section id="services" className={styles.services}>
      <div className="container">
        <div className={styles.header}>
          <h2 className={styles.title}>איך אוכל לעזור לכם?</h2>
          <p className={styles.subtitle}>
            אני מאמינה שכל משבר הוא הזדמנות לצמיחה. יחד נמצא את הכלים המתאימים לכם.
          </p>
        </div>
        <div className={styles.grid}>
          {services.map((service, index) => (
            <ServiceCard key={index} {...service} />
          ))}
        </div>
      </div>
    </section>
  );
};

export default ServicesSection;
