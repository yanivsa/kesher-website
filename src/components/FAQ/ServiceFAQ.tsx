import React, { useState } from 'react';
import { FiChevronDown } from 'react-icons/fi';
import faqs from '../../data/faqs';
import styles from './ServiceFAQ.module.css';

interface ServiceFAQProps {
  category: string;
}

const ServiceFAQ: React.FC<ServiceFAQProps> = ({ category }) => {
  const [openIndex, setOpenIndex] = useState<number | null>(0);
  const filteredFaqs = faqs.filter(f => f.category === category);

  if (filteredFaqs.length === 0) {
    return null;
  }

  const toggle = (index: number) => {
    setOpenIndex(openIndex === index ? null : index);
  };

  return (
    <section className={styles.faqSection}>
      <div className="container">
        <h2 className={styles.title}>שאלות נפוצות</h2>
        <div className={styles.list}>
          {filteredFaqs.map((faq, index) => (
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
                <FiChevronDown className={styles.chevron} />
              </button>
              <div className={styles.answerWrapper}>
                <p className={styles.answer}>{faq.answer}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default ServiceFAQ;
