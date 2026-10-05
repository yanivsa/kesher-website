import React from 'react';
import LandingPageTemplate from '../LandingPageTemplate';
import { LANDING_PAGES_CONFIG } from '../../../data/landingPagesConfig';

const CouplesMediationAshdodPage: React.FC = () => {
  const config = LANDING_PAGES_CONFIG['couples-mediation-ashdod'];
  return <LandingPageTemplate config={config} />;
};

export default CouplesMediationAshdodPage;
