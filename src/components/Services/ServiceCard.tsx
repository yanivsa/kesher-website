import React from 'react';
import { Link } from 'react-router-dom';
import styles from './ServiceCard.module.css';

interface ServiceCardProps {
  title: string;
  description: string;
  icon: React.ReactNode;
  link: string;
  highlights?: string[];
}

const ServiceCard: React.FC<ServiceCardProps> = ({ title, description, icon, link, highlights = [] }) => {
  return (
    <div className={styles.card}>
      <div className={styles.icon}>{icon}</div>
      <h3 className={styles.title}>{title}</h3>
      <p className={styles.description}>{description}</p>
      {highlights.length > 0 && (
        <ul className={styles.highlights}>
          {highlights.map((highlight) => (
            <li key={highlight}>{highlight}</li>
          ))}
        </ul>
      )}
      <Link to={link} className={styles.link}>למידע נוסף ←</Link>
    </div>
  );
};

export default ServiceCard;
