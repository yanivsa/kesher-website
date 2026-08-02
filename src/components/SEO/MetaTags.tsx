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

const upsertMeta = (selector: string, attributes: Record<string, string>) => {
  const matches = [...document.head.querySelectorAll<HTMLMetaElement>(selector)];
  const element = matches.shift() || document.createElement('meta');
  for (const duplicate of matches) duplicate.remove();
  for (const [name, value] of Object.entries(attributes)) element.setAttribute(name, value);
  element.dataset.kesherSeo = 'true';
  if (!element.parentElement) document.head.appendChild(element);
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

const upsertHreflang = (hreflang: string, href: string) => {
  const matches = [...document.head.querySelectorAll<HTMLLinkElement>(`link[rel="alternate"][hreflang="${hreflang}"]`)];
  const element = matches.shift() || document.createElement('link');
  for (const duplicate of matches) duplicate.remove();
  element.rel = 'alternate';
  element.setAttribute('hreflang', hreflang);
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
    const fullTitle = title.includes(SITE_CONFIG.brand) ? title : `${title} | ${SITE_CONFIG.brand}`;

    document.title = fullTitle;
    upsertMeta('meta[name="description"]', { name: 'description', content: description });
    upsertCanonical(currentUrl);
    upsertHreflang('he-IL', currentUrl);
    upsertHreflang('x-default', currentUrl);

    const meta = [
      ['meta[name="author"]', { name: 'author', content: SITE_CONFIG.author }],
      ['meta[property="og:type"]', { property: 'og:type', content: ogType }],
      ['meta[property="og:locale"]', { property: 'og:locale', content: 'he_IL' }],
      ['meta[property="og:title"]', { property: 'og:title', content: fullTitle }],
      ['meta[property="og:description"]', { property: 'og:description', content: description }],
      ['meta[property="og:url"]', { property: 'og:url', content: currentUrl }],
      ['meta[property="og:site_name"]', { property: 'og:site_name', content: SITE_CONFIG.author }],
      ['meta[property="og:image"]', { property: 'og:image', content: imageUrl }],
      ['meta[name="twitter:card"]', { name: 'twitter:card', content: 'summary_large_image' }],
      ['meta[name="twitter:title"]', { name: 'twitter:title', content: fullTitle }],
      ['meta[name="twitter:description"]', { name: 'twitter:description', content: description }],
      ['meta[name="twitter:image"]', { name: 'twitter:image', content: imageUrl }],
    ] as const;

    for (const [selector, attributes] of meta) upsertMeta(selector, attributes);

    const robots = [...document.head.querySelectorAll<HTMLMetaElement>('meta[name="robots"]')];
    if (noIndex) {
      upsertMeta('meta[name="robots"]', { name: 'robots', content: 'noindex, nofollow' });
    } else {
      for (const element of robots) element.remove();
    }
  }, [currentUrl, description, imageUrl, noIndex, ogType, title]);

  return null;
};

export default MetaTags;
