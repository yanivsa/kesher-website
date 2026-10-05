import React from 'react';
import LandingPageTemplate from '../LandingPageTemplate';
import { LANDING_PAGES_CONFIG } from '../../../data/landingPagesConfig';

const CouplesCounselingGanYavnePage: React.FC = () => {
  const config = LANDING_PAGES_CONFIG['couples-counseling-gan-yavne'];
  return <LandingPageTemplate config={config} />;
};

export default CouplesCounselingGanYavnePage;
