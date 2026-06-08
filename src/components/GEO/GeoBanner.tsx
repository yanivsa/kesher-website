import React from 'react';
import styles from './GeoBanner.module.css';

const GeoBanner: React.FC = () => {
  return (
    <div className={styles.banner}>
      <div className="container">
        <p>
          📍 מספקת שירותי ייעוץ והדרכת הורים באזור <strong>אשדוד והסביבה</strong> ובפריסה ארצית (אונליין).
        </p>
      </div>
    </div>
  );
};

export default GeoBanner;
