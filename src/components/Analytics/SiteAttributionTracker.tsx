import React, { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { captureSiteAttribution } from '../../lib/attribution';

const SiteAttributionTracker: React.FC = () => {
  const { pathname, search } = useLocation();

  useEffect(() => {
    captureSiteAttribution(pathname, search);
  }, [pathname, search]);

  return null;
};

export default SiteAttributionTracker;
