import React, { useEffect, useRef, useState } from 'react';
import styles from './SignatureMark.module.css';

type SignatureTone = 'about' | 'article' | 'footer';

interface SignatureMarkProps {
  tone: SignatureTone;
  animated?: boolean;
  label?: string;
  className?: string;
}

const SignatureMark: React.FC<SignatureMarkProps> = ({
  tone,
  animated = false,
  label,
  className = '',
}) => {
  const rootRef = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(!animated);

  useEffect(() => {
    if (!animated) {
      setVisible(true);
      return;
    }

    const node = rootRef.current;
    if (!node) return;

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (reducedMotion.matches) {
      setVisible(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.35 }
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [animated]);

  const rootClassName = [
    styles.signature,
    styles[tone],
    animated ? styles.animated : '',
    visible ? styles.visible : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div ref={rootRef} className={rootClassName}>
      {label && <span className={styles.label}>{label}</span>}
      <span
        className={styles.mark}
        role="img"
        aria-label="חתימתה של שירה סהרוני"
      />
    </div>
  );
};

export default SignatureMark;
