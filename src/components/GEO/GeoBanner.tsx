import React from 'react';
import styles from './GeoBanner.module.css';

const GeoBanner: React.FC = () => {
  return (
    <div className={styles.banner}>
      <div className="container">
        <p>
          📍 ייעוץ זוגי, הנחיית הורים וגישור באזור <strong>אשדוד והסביבה</strong> ובפריסה ארצית (אונליין).
        </p>
      </div>
    </div>
  );
};

export default GeoBanner;
