import React from 'react';
import { FaWhatsapp } from 'react-icons/fa';
import { FiShield } from 'react-icons/fi';
import { SITE_CONFIG } from '../../constants/siteConfig';
import { useContactForm } from '../../hooks/useContactForm';
import styles from './ContactSection.module.css';

const ContactSection: React.FC = () => {
  const {
    formData,
    company,
    setCompany,
    submitStatus,
    handleChange,
    handleSubmit,
    handleFocus,
    resetStatus
  } = useContactForm();

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
                onClick={resetStatus}
              >
                שליחת פנייה נוספת
              </button>
            </div>
          ) : (
            <form
              className={styles.form}
              onSubmit={handleSubmit}
              onFocus={handleFocus}
            >
              {submitStatus === 'error' && (
                <div className={styles.errorMessage} role="alert">
                  הייתה שגיאה בשליחת הטופס. אנא נסו שוב או פנו אלי ישירות בטלפון / WhatsApp.
                </div>
              )}
              <div className={styles.honeypot} aria-hidden="true">
                <label htmlFor="company">חברה</label>
                <input
                  id="company"
                  name="company"
                  type="text"
                  value={company}
                  onChange={(event) => setCompany(event.target.value)}
                  tabIndex={-1}
                  autoComplete="off"
                />
              </div>
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
              <button type="submit" className={styles.submitBtn} disabled={submitStatus === 'submitting'}>
                {submitStatus === 'submitting' ? 'שולחת...' : 'שליחת פנייה'}
              </button>
              <div className={styles.privacyNote}>
                <FiShield aria-hidden="true" />
                <span>הפרטים משמשים לחזרה אליכם בלבד, בהתאם למדיניות הפרטיות.</span>
              </div>
            </form>
          )}
        </div>
      </div>
    </section>
  );
};

export default ContactSection;
