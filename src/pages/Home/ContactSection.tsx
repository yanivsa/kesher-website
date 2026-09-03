import React, { useRef, useState } from 'react';
import { FaWhatsapp } from 'react-icons/fa';
import { FiCalendar, FiShield } from 'react-icons/fi';
import { Link, useSearchParams } from 'react-router-dom';
import { SITE_CONFIG } from '../../constants/siteConfig';
import { submitContact } from '../../lib/contactApi';
import { pushAnalyticsEvent } from '../../lib/analytics';
import { CONTACT_SERVICE_OPTIONS, resolveContactService } from '../../lib/contactServices';
import styles from './ContactSection.module.css';

const ContactSection: React.FC = () => {
  const [searchParams] = useSearchParams();
  const initialService = resolveContactService(searchParams.get('service'));
  const isLectureInquiry = initialService === 'lectures';
  const whatsappHref = isLectureInquiry
    ? `https://wa.me/${SITE_CONFIG.contact.whatsapp}?text=${encodeURIComponent('היי שירה, אני מעוניין/ת לקבל פרטים על הזמנת הרצאה או סדנה בנושא זוגיות, הורות או נושא אחר מהאתר.')}`
    : SITE_CONFIG.links.whatsapp;
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    service: initialService as string,
    message: ''
  });
  const [company, setCompany] = useState('');
  const [submitStatus, setSubmitStatus] = useState<'idle' | 'submitting' | 'success' | 'error'>('idle');
  const startedAt = useRef(0);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitStatus('idle');
    
    try {
      setSubmitStatus('submitting');
      await submitContact({
        kind: 'contact',
        ...formData,
        company,
        startedAt: startedAt.current,
      });
      const leadContext = {
        service_type: formData.service,
        lead_type: 'contact_form',
        cta_location: 'contact_form',
      };
      pushAnalyticsEvent('generate_lead', leadContext);
      pushAnalyticsEvent('lead_submit', leadContext);
      setSubmitStatus('success');
      setFormData({ name: '', email: '', phone: '', service: initialService, message: '' });
      setCompany('');
      startedAt.current = 0;
    } catch {
      setSubmitStatus('error');
    }
  };

  return (
    <section id="contact" className={styles.contact}>
      <div className={`container ${styles.container}`}>
        <div className={styles.info}>
          <h2 className={styles.title}>
            {isLectureInquiry ? 'להזמנת הרצאה או סדנה' : 'אפשר לפנות בדרך שנוחה לכם'}
          </h2>
          <p className={styles.subtitle}>
            {isLectureInquiry
              ? 'ספרו בקצרה מי הקהל, מה הנושא שמעניין אתכם וכל פרט רלוונטי על האירוע. אפשר להשאיר פרטים בטופס או לפנות ישירות בוואטסאפ.'
              : 'פנייה לליווי זוגי או הורי מלווה לעיתים בהתלבטות, וזה טבעי לגמרי. אפשר לבחור מועד לפגישת ייעוץ ישירות ביומן, או לפנות אליי בדרך שנוחה לכם.'}
          </p>
          <div className={styles.contactActions}>
            {!isLectureInquiry && (
              <Link to={SITE_CONFIG.links.appointment} className={styles.appointmentBtn}>
                <FiCalendar aria-hidden="true" />
                בחירת מועד לפגישה
              </Link>
            )}
            <a
              href={whatsappHref}
              className={styles.whatsappBtn}
              onClick={() => pushAnalyticsEvent('whatsapp_click', {
                service_type: isLectureInquiry ? 'lectures' : formData.service,
                cta_location: isLectureInquiry ? 'lecture_contact' : 'contact_section',
              })}
            >
              <FaWhatsapp aria-hidden="true" />
              {isLectureInquiry ? 'פנייה בוואטסאפ על הרצאה' : 'שליחת הודעה בוואטסאפ'}
            </a>
          </div>
          <div className={styles.contactDetails}>
            <div className={styles.detail}>
              <span className={styles.icon}>📞</span>
              <div>
                <h3>טלפון</h3>
                <p>{SITE_CONFIG.contact.phone}</p>
              </div>
            </div>
            <div className={styles.detail}>
              <span className={styles.icon}>✉️</span>
              <div>
                <h3>אימייל</h3>
                <p>{SITE_CONFIG.contact.email}</p>
              </div>
            </div>
            <div className={styles.detail}>
              <span className={styles.icon}>📍</span>
              <div>
                <h3>מיקום</h3>
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
              <p>פרטי הקשר שלכם התקבלו. אחזור אליכם לתיאום המשך.</p>
              <button 
                type="button" 
                className={styles.resetBtn} 
                onClick={() => setSubmitStatus('idle')}
              >
                שליחת פנייה נוספת
              </button>
            </div>
          ) : (
            <form
              className={styles.form}
              onSubmit={handleSubmit}
              onFocus={() => {
                if (!startedAt.current) startedAt.current = Date.now();
              }}
            >
              {submitStatus === 'error' && (
                <div className={styles.errorMessage} role="alert">
                  הייתה שגיאה בשליחת הטופס. אפשר לנסות שוב או לפנות אליי ישירות בטלפון או בוואטסאפ.
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
                  {CONTACT_SERVICE_OPTIONS.map(({ value, label }) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
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
                  placeholder={isLectureInquiry ? 'למשל: סוג הקהל, נושא מועדף, מועד משוער ומיקום...' : 'ספרו לי קצת על הפנייה שלכם...'}
                ></textarea>
              </div>
              <button type="submit" className={styles.submitBtn} disabled={submitStatus === 'submitting'}>
                {submitStatus === 'submitting' ? 'שולחת...' : 'שליחת פנייה'}
              </button>
              <div className={styles.privacyNote}>
                <FiShield aria-hidden="true" />
                <span>הפרטים שלכם נשמרים בדיסקרטיות מלאה ומשמשים לחזרה אליכם בלבד.</span>
              </div>
            </form>
          )}
        </div>
      </div>
    </section>
  );
};

export default ContactSection;
