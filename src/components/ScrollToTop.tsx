import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

const ScrollToTop = () => {
  const { pathname, hash } = useLocation();

  useEffect(() => {
    if (hash) {
      let frame = 0;
      let attempts = 0;
      const scrollToHash = () => {
        const element = document.getElementById(hash.substring(1));
        if (element) {
          element.scrollIntoView({ behavior: 'smooth' });
          return;
        }
        attempts += 1;
        if (attempts < 30) frame = window.requestAnimationFrame(scrollToHash);
      };
      frame = window.requestAnimationFrame(scrollToHash);
      return () => window.cancelAnimationFrame(frame);
    } else {
      window.scrollTo(0, 0);
    }
  }, [pathname, hash]);

  return null;
};

export default ScrollToTop;
