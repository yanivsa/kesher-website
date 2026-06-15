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

const upsertMetaTagsBatch = (tags: Record<string, string>[]) => {
  const existingMetas = document.head.querySelectorAll('meta');
  const metaMap: Record<string, HTMLMetaElement[]> = {};

  for (const meta of existingMetas) {
    const name = meta.getAttribute('name');
    const property = meta.getAttribute('property');
    const key = name ? `name=${name}` : property ? `property=${property}` : null;
    if (key) {
      if (!metaMap[key]) metaMap[key] = [];
      metaMap[key].push(meta);
    }
  }

  for (const attributes of tags) {
    const isName = 'name' in attributes;
    const key = isName ? `name=${attributes.name}` : `property=${attributes.property}`;
    if (!key) continue;

    const matches = metaMap[key] || [];
    const element = matches.shift() || document.createElement('meta');

    for (const duplicate of matches) duplicate.remove();
    for (const [name, value] of Object.entries(attributes)) {
      if (element.getAttribute(name) !== value) {
        element.setAttribute(name, value);
      }
    }
    element.dataset.kesherSeo = 'true';
    if (!element.parentElement) document.head.appendChild(element);
  }
};

const upsertCanonical = (href: string) => {
  const matches = [...document.head.querySelectorAll<HTMLLinkElement>('link[rel="canonical"]')];
  const element = matches.shift() || document.createElement('link');
  for (const duplicate of matches) duplicate.remove();
  element.rel = 'canonical';
  element.href = href;
  element.dataset.kesherSeo = 'true';
  if (!element.parentElement) document.head.appendChild(element);
};

const MetaTags = ({
  title,
  description,
  canonical,
  ogType = 'website',
  image,
  noIndex = false,
}: MetaTagsProps) => {
  const location = useLocation();
  const cleanPath = location.pathname.length > 1 && location.pathname.endsWith('/')
    ? location.pathname.slice(0, -1)
    : location.pathname;
  const currentUrl = canonical || `${SITE_CONFIG.url}${cleanPath}`;
  const imageUrl = image?.startsWith('/')
    ? `${SITE_CONFIG.url}${image}`
    : image || `${SITE_CONFIG.url}/apple-touch-icon.png`;

  useEffect(() => {
    document.title = title;

    upsertCanonical(currentUrl);

    const metaTags: Record<string, string>[] = [
      { name: 'description', content: description },
      { property: 'og:type', content: ogType },
      { property: 'og:title', content: title },
      { property: 'og:description', content: description },
      { property: 'og:url', content: currentUrl },
      { property: 'og:site_name', content: SITE_CONFIG.author },
      { property: 'og:image', content: imageUrl },
      { name: 'twitter:card', content: 'summary_large_image' },
      { name: 'twitter:title', content: title },
      { name: 'twitter:description', content: description },
      { name: 'twitter:image', content: imageUrl },
    ];

    upsertMetaTagsBatch(metaTags);

    const robots = [...document.head.querySelectorAll<HTMLMetaElement>('meta[name="robots"]')];
    if (noIndex) {
      upsertMetaTagsBatch([{ name: 'robots', content: 'noindex, nofollow' }]);
    } else {
      for (const element of robots) element.remove();
    }
  }, [currentUrl, description, imageUrl, noIndex, ogType, title]);

  return null;
};

export default MetaTags;
