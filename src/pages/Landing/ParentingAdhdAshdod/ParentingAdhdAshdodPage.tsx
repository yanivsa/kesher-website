import React from 'react';
import LandingPageTemplate from '../LandingPageTemplate';
import { LANDING_PAGES_CONFIG } from '../../../data/landingPagesConfig';

const ParentingAdhdAshdodPage: React.FC = () => {
  const config = LANDING_PAGES_CONFIG['parenting-adhd-ashdod'];
  return <LandingPageTemplate config={config} />;
};

export default ParentingAdhdAshdodPage;
