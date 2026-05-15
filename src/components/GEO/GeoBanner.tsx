import React from 'react';
import styles from './GeoBanner.module.css';

const GeoBanner: React.FC = () => {
  return (
    <div className={styles.banner}>
      <div className="container">
        <p>
          📍 מספקת שירותי ייעוץ, הדרכת הורים וגישור באזור <strong>אשדוד והסביבה</strong> ובפריסה ארצית (אונליין).
        </p>
      </div>
    </div>
  );
};

export default GeoBanner;
