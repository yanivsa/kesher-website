import React from 'react';
import LandingPageTemplate from '../LandingPageTemplate';
import { LANDING_PAGES_CONFIG } from '../../../data/landingPagesConfig';

const CouplesCrisisAshdodPage: React.FC = () => {
  const config = LANDING_PAGES_CONFIG['couples-crisis-ashdod'];
  return <LandingPageTemplate config={config} />;
};

export default CouplesCrisisAshdodPage;
