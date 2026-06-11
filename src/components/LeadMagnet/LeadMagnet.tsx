import React, { useRef, useState } from 'react';
import { FiDownload } from 'react-icons/fi';
import { submitContact } from '../../lib/contactApi';
import styles from './LeadMagnet.module.css';

const LeadMagnet: React.FC = () => {
  const [email, setEmail] = useState('');
  const [company, setCompany] = useState('');
  const [status, setStatus] = useState<'idle' | 'submitting' | 'success' | 'error'>('idle');
  const [downloadUrl, setDownloadUrl] = useState('');
  const startedAt = useRef(0);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;

    try {
      setStatus('submitting');
      const result = await submitContact({
        kind: 'lead_magnet',
        email,
        company,
        startedAt: startedAt.current,
      });
      setDownloadUrl(result.downloadUrl || '/guides/5-sentences-stop-an-argument.html');
      setStatus('success');
      setEmail('');
      setCompany('');
      startedAt.current = 0;
    } catch {
      setStatus('error');
    }
  };

  return (
    <div className={styles.wrapper}>
      <div className={styles.container}>
        <div className={styles.content}>
          <h3>מרגישים שהריבים יוצאים משליטה?</h3>
          <p>
            הורידו בחינם את המדריך הקצר שלי: <strong>"5 משפטים שעוזרים לעצור הסלמה בזמן ריב"</strong>.
            כלים מעשיים מהקליניקה שאפשר ליישם כבר הערב.
          </p>
          {status === 'success' ? (
            <div className={styles.successMessage} role="status">
              <p>תודה! אפשר להוריד את המדריך עכשיו.</p>
              <a href={downloadUrl} download>להורדת המדריך</a>
            </div>
          ) : (
            <form
              className={styles.form}
              onSubmit={handleSubmit}
              onFocus={() => {
                if (!startedAt.current) startedAt.current = Date.now();
              }}
            >
              <input
                type="text"
                name="company"
                value={company}
                onChange={(event) => setCompany(event.target.value)}
                tabIndex={-1}
                autoComplete="off"
                aria-hidden="true"
                className={styles.honeypot}
              />
              <input
                type="email"
                placeholder="הכנס/י כתובת אימייל"
                aria-label="כתובת אימייל"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className={styles.input}
              />
              <button type="submit" className={styles.button} disabled={status === 'submitting'}>
                <FiDownload /> {status === 'submitting' ? 'שולחת...' : 'קבלת קישור להורדה'}
              </button>
              {status === 'error' && (
                <p className={styles.errorMessage} role="alert">לא הצלחנו לשלוח את הבקשה. נסו שוב בעוד רגע.</p>
              )}
            </form>
          )}
        </div>
      </div>
    </div>
  );
};

export default LeadMagnet;
