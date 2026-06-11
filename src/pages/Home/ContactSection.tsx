import React, { useState } from 'react';
import { FaWhatsapp } from 'react-icons/fa';
import { FiShield } from 'react-icons/fi';
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
  const [submitStatus, setSubmitStatus] = useState<'idle' | 'success' | 'error'>('idle');

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitStatus('idle');
    
    const formSpreeUrl = SITE_CONFIG.formspreeUrl;

    try {
      const response = await fetch(formSpreeUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...formData,
          _subject: `פנייה חדשה מהאתר: ${formData.name}`,
        }),
      });
      
      if (response.ok) {
        setSubmitStatus('success');
        setFormData({ name: '', email: '', phone: '', service: 'couples', message: '' });
      } else {
        setSubmitStatus('error');
      }
    } catch (error) {
      console.error('Error submitting form:', error);
      setSubmitStatus('error');
    }
  };

  return (
    <section id="contact" className={styles.contact}>
      <div className={`container ${styles.container}`}>
        <div className={styles.info}>
          <h2 className={styles.title}>בואו נתחיל לדבר</h2>
          <p className={styles.subtitle}>
            השאירו פרטים ואחזור אליכם, או שלחו הודעת WhatsApp קצרה אם נוח לכם להתחיל משם.
          </p>
          <a href={SITE_CONFIG.links.whatsapp} className={styles.whatsappBtn}>
            <FaWhatsapp aria-hidden="true" />
            שליחת WhatsApp
          </a>
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
          {submitStatus === 'success' ? (
            <div className={styles.successMessage}>
              <div className={styles.successIcon}>✓</div>
              <h3>תודה רבה! פנייתכם התקבלה בהצלחה</h3>
              <p>פרטי הקשר שלכם התקבלו. אחזור אליכם בהקדם (בדרך כלל תוך 24 שעות) לתיאום שיחת ההיכרות הראשונית.</p>
              <button 
                type="button" 
                className={styles.resetBtn} 
                onClick={() => setSubmitStatus('idle')}
              >
                שליחת פנייה נוספת
              </button>
            </div>
          ) : (
            <form className={styles.form} onSubmit={handleSubmit}>
              {submitStatus === 'error' && (
                <div className={styles.errorMessage}>
                  הייתה שגיאה בשליחת הטופס. אנא נסו שוב או פנו אלי ישירות בטלפון / WhatsApp.
                </div>
              )}
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
              <button type="submit" className={styles.submitBtn}>שליחת פנייה</button>
              <div className={styles.privacyNote}>
                <FiShield aria-hidden="true" />
                <span>כל פנייה נשמרת בדיסקרטיות וסודיות מלאה.</span>
              </div>
            </form>
          )}
        </div>
      </div>
    </section>
  );
};

export default ContactSection;
