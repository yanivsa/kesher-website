import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { FiChevronDown, FiArrowLeft } from 'react-icons/fi';
import faqs from '../../data/faqs';
import styles from './FAQSection.module.css';

const selectedIndices = [1, 2, 8, 10];
const selectedFaqs = selectedIndices.map(index => faqs[index]);

const FAQSection: React.FC = () => {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  const toggle = (index: number) => {
    setOpenIndex(openIndex === index ? null : index);
  };

  return (
    <section className={styles.faqSection}>
      <div className="container">
        <div className={styles.header}>
          <h2>שאלות נפוצות בקליניקה</h2>
          <p>תשובות לשאלות שעולות לפני הפגישה הראשונה.</p>
        </div>

        <div className={styles.list}>
          {selectedFaqs.map((faq, index) => (
            <div
              key={index}
              className={`${styles.item} ${openIndex === index ? styles.open : ''}`}
            >
              <button
                type="button"
                className={styles.question}
                onClick={() => toggle(index)}
                aria-expanded={openIndex === index}
              >
                <span>{faq.question}</span>
                <FiChevronDown className={styles.chevron} aria-hidden="true" />
              </button>
              <div className={styles.answerWrapper}>
                <p className={styles.answer}>{faq.answer}</p>
              </div>
            </div>
          ))}
        </div>

        <div className={styles.cta}>
          <Link to="/faq" className={styles.ctaLink}>
            לכל השאלות הנפוצות
            <FiArrowLeft aria-hidden="true" />
          </Link>
        </div>
      </div>
    </section>
  );
};

export default FAQSection;
