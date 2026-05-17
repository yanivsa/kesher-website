import React, { useState } from 'react';
import { FiDownload } from 'react-icons/fi';
import styles from './LeadMagnet.module.css';

const LeadMagnet: React.FC = () => {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;

    // Simulate sending email to Formspree or email marketing service
    const formSpreeUrl = 'https://formspree.io/f/xvgzgeyw';
    try {
      await fetch(formSpreeUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, _subject: "בקשה להורדת מדריך: 5 מילים שיעצרו ריב" }),
      });
      setSubmitted(true);
      setEmail('');
    } catch (error) {
      console.error(error);
    }
  };

  return (
    <div className={styles.wrapper}>
      <div className={styles.container}>
        <div className={styles.content}>
          <h3>מרגישים שהריבים יוצאים משליטה?</h3>
          <p>
            הורידו בחינם את המדריך הקצר שלי: <strong>"5 משפטים שיעצרו כל ריב תוך 3 דקות"</strong>.
            כלים מעשיים מהקליניקה שאפשר ליישם כבר הערב.
          </p>
          {submitted ? (
            <div className={styles.successMessage}>
              <p>תודה! המדריך בדרך לתיבת המייל שלך.</p>
            </div>
          ) : (
            <form className={styles.form} onSubmit={handleSubmit}>
              <input
                type="email"
                placeholder="הכנס/י כתובת אימייל"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className={styles.input}
              />
              <button type="submit" className={styles.button}>
                <FiDownload /> שליחה למייל
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};

export default LeadMagnet;
