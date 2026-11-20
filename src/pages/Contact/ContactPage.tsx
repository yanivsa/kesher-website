import React from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';
import MetaTags from '../../components/SEO/MetaTags';
import SchemaOrg from '../../components/SEO/SchemaOrg';
import ContactSection from '../Home/ContactSection';
import { SITE_CONFIG } from '../../constants/siteConfig';
import { resolveContactService } from '../../lib/contactServices';
import { PARENTING_COORDINATION_CONTACT_URL } from '../../lib/parentingCoordination';
import styles from './ContactPage.module.css';

const schemaData = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "ContactPage",
      "name": "צור קשר | שירה סהרוני",
      "description": "צרו קשר עם שירה סהרוני לתיאום ייעוץ זוגי, הנחיית הורים, גישור או הזמנת הרצאה וסדנה. זמינה באשדוד ובאונליין.",
      "url": `${SITE_CONFIG.url}/contact`,
      "mainEntity": {
        "@type": "LocalBusiness",
        "@id": `${SITE_CONFIG.url}/#business`,
        "name": SITE_CONFIG.brand,
        "telephone": SITE_CONFIG.contact.phone,
        "email": SITE_CONFIG.contact.email,
        "address": {
          "@type": "PostalAddress",
          "addressLocality": "אשדוד",
          "addressCountry": "IL"
        }
      }
    },
    {
      "@type": "BreadcrumbList",
      "@id": `${SITE_CONFIG.url}/contact#breadcrumb`,
      "itemListElement": [
        {
          "@type": "ListItem",
          "position": 1,
          "name": "עמוד הבית",
          "item": SITE_CONFIG.url
        },
        {
          "@type": "ListItem",
          "position": 2,
          "name": "צור קשר",
          "item": `${SITE_CONFIG.url}/contact`
        }
      ]
    }
  ]
};

const ContactPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const { pathname } = useLocation();
  const isSpecialtyInquiry = pathname.replace(/\/$/, '') === PARENTING_COORDINATION_CONTACT_URL;
  const serviceKey = isSpecialtyInquiry ? 'parenting_coordination' : resolveContactService(searchParams.get('service'));

  return (
    <div className={styles.page}>
      {!isSpecialtyInquiry && <SchemaOrg data={schemaData} />}
      <MetaTags
        canonical={`${SITE_CONFIG.url}${isSpecialtyInquiry ? PARENTING_COORDINATION_CONTACT_URL : '/contact'}`}
        title={isSpecialtyInquiry ? 'בירור התאמה לתיאום הורי' : 'צור קשר'}
        description={isSpecialtyInquiry
          ? 'פנייה ראשונית לבירור התאמה לתיאום הורי עם שירה סהרוני. השאירו פרטי קשר בלבד, ללא מידע רגיש על ילדים או על הסכסוך.'
          : 'צרו קשר עם שירה סהרוני לתיאום ייעוץ זוגי, הנחיית הורים, גישור או הזמנת הרצאה וסדנה. זמינה באשדוד ובאונליין.'}
        noIndex={isSpecialtyInquiry}
      />
      <header className={styles.header}>
        <div className="container">
          <h1>{isSpecialtyInquiry ? 'בירור התאמה לתיאום הורי' : 'צרו קשר'}</h1>
          <p>{isSpecialtyInquiry
            ? 'לפני תחילת תיאום הורי חשוב לבדוק התאמה ובטיחות. השאירו פרטי קשר בלבד; אל תשלחו פרטים מזהים על ילדים, מסמכים משפטיים או תיאורי פגיעה בטופס פתוח.'
            : <>אפשר לקבוע פגישה בייעוץ זוגי, בהדרכת הורים או בגישור, להשאיר פרטים כדי שאחזור אליכם, או לשאול על <a href="/lectures">הרצאות וסדנאות</a>.</>}</p>
        </div>
      </header>
      <ContactSection key={serviceKey} initialServiceOverride={isSpecialtyInquiry ? 'parenting_coordination' : undefined} />
    </div>
  );
};

export default ContactPage;
