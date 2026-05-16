import React from 'react';
import styles from './Hero.module.css';

const Hero: React.FC = () => {
  return (
    <section className={styles.hero}>
      <div className={`container ${styles.container}`}>
        <div className={styles.content}>
          <h1 className={styles.title}>
            מערכות יחסים <br />
            <span>ראויות לטיפול נכון.</span>
          </h1>
          <p className={styles.description}>
            ליווי מקצועי ורגיש לזוגות, הורים ומשפחות בתהליכי שינוי, צמיחה וגישור. 
            בואו נמצא יחד את הדרך לחיבור עמוק יותר ופחות קונפליקטים.
          </p>
          <div className={styles.actions}>
            <a href="#contact" className={styles.primaryBtn}>קביעת פגישת היכרות</a>
            <a href="#about" className={styles.secondaryBtn}>קרא עוד אודותי</a>
          </div>
        </div>
        <div className={styles.imageContainer}>
          <div className={styles.imageWrapper}>
            <img 
              src="https://images.unsplash.com/photo-1493663284031-b7e3aefcae8e?auto=format&fit=crop&w=1200&q=80" 
              alt="מרחב בטוח לייעוץ וגישור" 
              className={styles.heroImage}
            />
            <div className={styles.overlay}></div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Hero;
