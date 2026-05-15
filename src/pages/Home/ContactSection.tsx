import React, { useState } from 'react';
import { SITE_CONFIG } from '../../constants/siteConfig';
import styles from './ContactSection.module.css';

const ContactSection: React.FC = () => {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    service: 'couples',
    message: ''
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    console.log('Form submitted:', formData);
    alert('תודה! פנייתך התקבלה ונחזור אליך בהקדם.');
    setFormData({ name: '', email: '', phone: '', service: 'couples', message: '' });
  };

  return (
    <section id="contact" className={styles.contact}>
      <div className={`container ${styles.container}`}>
        <div className={styles.info}>
          <h2 className={styles.title}>בואו נתחיל לדבר</h2>
          <p className={styles.subtitle}>
            אני כאן לכל שאלה, התייעצות או קביעת פגישה. אתם מוזמנים להשאיר פרטים או ליצור קשר ישיר.
          </p>
          <div className={styles.contactDetails}>
            <div className={styles.detail}>
              <span className={styles.icon}>📞</span>
              <div>
                <h4>טלפון</h4>
                <p>{SITE_CONFIG.contact.phone}</p>
              </div>
            </div>
            <div className={styles.detail}>
              <span className={styles.icon}>✉️</span>
              <div>
                <h4>אימייל</h4>
                <p>{SITE_CONFIG.contact.email}</p>
              </div>
            </div>
            <div className={styles.detail}>
              <span className={styles.icon}>📍</span>
              <div>
                <h4>מיקום</h4>
                <p>{SITE_CONFIG.contact.location}</p>
              </div>
            </div>
          </div>
        </div>
        <div className={styles.formContainer}>
          <form className={styles.form} onSubmit={handleSubmit}>
            <div className={styles.formGroup}>
              <label htmlFor="name">שם מלא</label>
              <input 
                type="text" 
                id="name" 
                name="name" 
                value={formData.name}
                onChange={handleChange}
                required 
                placeholder="איך קוראים לכם?"
              />
            </div>
            <div className={styles.formRow}>
              <div className={styles.formGroup}>
                <label htmlFor="email">אימייל</label>
                <input 
                  type="email" 
                  id="email" 
                  name="email" 
                  value={formData.email}
                  onChange={handleChange}
                  required 
                  placeholder="כתובת המייל שלכם"
                />
              </div>
              <div className={styles.formGroup}>
                <label htmlFor="phone">טלפון</label>
                <input 
                  type="tel" 
                  id="phone" 
                  name="phone" 
                  value={formData.phone}
                  onChange={handleChange}
                  required 
                  placeholder="מספר לווצאפ/שיחה"
                />
              </div>
            </div>
            <div className={styles.formGroup}>
              <label htmlFor="service">במה תרצו עזרה?</label>
              <select 
                id="service" 
                name="service" 
                value={formData.service}
                onChange={handleChange}
              >
                <option value="couples">ייעוץ זוגי</option>
                <option value="parenting">הדרכת הורים</option>
                <option value="mediation">גישור / גירושין</option>
                <option value="other">אחר</option>
              </select>
            </div>
            <div className={styles.formGroup}>
              <label htmlFor="message">הודעה (אופציונלי)</label>
              <textarea 
                id="message" 
                name="message" 
                rows={4} 
                value={formData.message}
                onChange={handleChange}
                placeholder="ספרו לי קצת על הפנייה שלכם..."
              ></textarea>
            </div>
            <button type="submit" className={styles.submitBtn}>שלח הודעה</button>
          </form>
        </div>
      </div>
    </section>
  );
};

export default ContactSection;
