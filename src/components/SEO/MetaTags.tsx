import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { SITE_CONFIG } from '../../constants/siteConfig';

interface MetaTagsProps {
  title: string;
  description: string;
  canonical?: string;
  ogType?: string;
  image?: string;
  noIndex?: boolean;
}

const MetaTags = ({
  title,
  description,
  canonical,
  ogType = 'website',
  image,
  noIndex = false,
}: MetaTagsProps) => {
  const location = useLocation();
  const cleanPath = location.pathname === '/' ? '' : (location.pathname.length > 1 && location.pathname.endsWith('/')
    ? location.pathname.slice(0, -1)
    : location.pathname);
  const currentUrl = canonical || `${SITE_CONFIG.url}${cleanPath}`;
  const imageUrl = image?.startsWith('/')
    ? `${SITE_CONFIG.url}${image}`
    : image || `${SITE_CONFIG.url}/apple-touch-icon.png`;

  useEffect(() => {
    const fullTitle = title.includes(SITE_CONFIG.brand) ? title : `${title} | ${SITE_CONFIG.brand}`;
    document.title = fullTitle;

    const headChildren = document.head.children;
    const existingMeta = new Map<string, HTMLMetaElement>();
    let existingCanonical: HTMLLinkElement | null = null;

    for (let i = headChildren.length - 1; i >= 0; i--) {
      const el = headChildren[i];
      if (el.tagName === 'META') {
        const metaEl = el as HTMLMetaElement;
        const name = metaEl.getAttribute('name');
        const property = metaEl.getAttribute('property');
        if (name === 'robots' && !noIndex) {
          metaEl.remove();
          continue;
        }
        const key = name ? `name:${name}` : property ? `property:${property}` : null;
        if (key) {
          if (existingMeta.has(key)) {
            metaEl.remove();
          } else {
            existingMeta.set(key, metaEl);
          }
        }
      } else if (el.tagName === 'LINK' && el.getAttribute('rel') === 'canonical') {
        const linkEl = el as HTMLLinkElement;
        if (existingCanonical) {
          linkEl.remove();
        } else {
          existingCanonical = linkEl;
        }
      }
    }

    const upsert = (key: string, attrs: Record<string, string>) => {
      let element = existingMeta.get(key);
      if (!element) {
        element = document.createElement('meta');
        document.head.appendChild(element);
      }
      for (const [k, v] of Object.entries(attrs)) {
        if (element.getAttribute(k) !== v) element.setAttribute(k, v);
      }
      element.dataset.kesherSeo = 'true';
    };

    upsert('name:description', { name: 'description', content: description });
    upsert('name:author', { name: 'author', content: SITE_CONFIG.author });
    upsert('property:og:type', { property: 'og:type', content: ogType });
    upsert('property:og:locale', { property: 'og:locale', content: 'he_IL' });
    upsert('property:og:title', { property: 'og:title', content: fullTitle });
    upsert('property:og:description', { property: 'og:description', content: description });
    upsert('property:og:url', { property: 'og:url', content: currentUrl });
    upsert('property:og:site_name', { property: 'og:site_name', content: SITE_CONFIG.author });
    upsert('property:og:image', { property: 'og:image', content: imageUrl });
    upsert('name:twitter:card', { name: 'twitter:card', content: 'summary_large_image' });
    upsert('name:twitter:title', { name: 'twitter:title', content: fullTitle });
    upsert('name:twitter:description', { name: 'twitter:description', content: description });
    upsert('name:twitter:image', { name: 'twitter:image', content: imageUrl });
    if (noIndex) {
      upsert('name:robots', { name: 'robots', content: 'noindex, nofollow' });
    }

    if (!existingCanonical) {
      existingCanonical = document.createElement('link');
      existingCanonical.rel = 'canonical';
      document.head.appendChild(existingCanonical);
    }
    if (existingCanonical.href !== currentUrl) existingCanonical.href = currentUrl;
    existingCanonical.dataset.kesherSeo = 'true';
  }, [currentUrl, description, imageUrl, noIndex, ogType, title]);

  return null;
};

export default MetaTags;
