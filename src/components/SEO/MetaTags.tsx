import React from 'react';
import { useLocation } from 'react-router-dom';
import { SITE_CONFIG } from '../../constants/siteConfig';

interface MetaTagsProps {
  title: string;
  description: string;
  canonical?: string;
  ogType?: string;
  image?: string;
}

const MetaTags: React.FC<MetaTagsProps> = ({ 
  title, 
  description, 
  canonical,
  ogType = "website",
  image
}) => {
  const location = useLocation();
  const currentUrl = canonical || `${SITE_CONFIG.url}${location.pathname === '/' ? '' : location.pathname}`;

  // Format image URL properly
  let imageUrl = image || `${SITE_CONFIG.url}/apple-touch-icon.png`;
  if (imageUrl.startsWith('/')) {
    imageUrl = `${SITE_CONFIG.url}${imageUrl}`;
  }

  return (
    <>
      <title>{title}</title>
      <meta name="description" content={description} />
      <link rel="canonical" href={currentUrl} />
      
      {/* Open Graph / Facebook */}
      <meta property="og:type" content={ogType} />
      <meta property="og:title" content={title} />
      <meta property="og:description" content={description} />
      <meta property="og:url" content={currentUrl} />
      <meta property="og:site_name" content={SITE_CONFIG.author} />
      <meta property="og:image" content={imageUrl} />
      
      {/* Twitter */}
      <meta name="twitter:card" content="summary_large_image" />
      <meta name="twitter:title" content={title} />
      <meta name="twitter:description" content={description} />
      <meta name="twitter:image" content={imageUrl} />
    </>
  );
};

export default MetaTags;
