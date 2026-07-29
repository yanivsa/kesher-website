import React from 'react';
import { Link } from 'react-router-dom';
import MetaTags from '../../components/SEO/MetaTags';
import styles from './NotFound.module.css';

const NotFound: React.FC = () => (
  <section className={styles.page}>
    <MetaTags
      title="העמוד לא נמצא"
      description="העמוד שביקשתם אינו קיים."
      noIndex
    />
    <div className="container">
      <p className={styles.code}>404</p>
      <h1>העמוד לא נמצא</h1>
      <p>ייתכן שהקישור השתנה או שהעמוד הוסר.</p>
      <Link to="/" className={styles.link}>חזרה לעמוד הבית</Link>
    </div>
  </section>
);

export default NotFound;
