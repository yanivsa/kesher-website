import React from 'react';
import Hero from './Hero';
import ServicesSection from './ServicesSection';
import AboutSection from './AboutSection';
import BlogPreview from './BlogPreview';
import ContactSection from './ContactSection';
import styles from './Home.module.css';

const Home: React.FC = () => {
  return (
    <div className={styles.home}>
      <Hero />
      <ServicesSection />
      <AboutSection />
      <BlogPreview />
      <ContactSection />
    </div>
  );
};

export default Home;
