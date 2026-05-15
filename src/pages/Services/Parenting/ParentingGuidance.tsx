import React from 'react';
import ServicePageTemplate from '../../../components/ServicePageTemplate/ServicePageTemplate';

const ParentingGuidance: React.FC = () => {
  const content = (
    <div>
      <p>הדרכת הורים מעניקה לכם את הכלים להבין את עולמם של הילדים שלכם, לבסס סמכות הורית מטיבה וליצור אווירה משפחתית רגועה ומחברת.</p>
      <h3>התמחות ב-ADHD</h3>
      <p>הורות לילדים עם הפרעת קשב וריכוז דורשת כלים ספציפיים וסבלנות רבה. אני מלווה אתכם בהבנת המנגנון של ה-ADHD וביצירת שגרה שתומכת בילד ובמשפחה כולה.</p>
      <h3>מה תקבלו בתהליך?</h3>
      <ul>
        <li>הבנת צרכי הילד והתנהגותו.</li>
        <li>כלים להצבת גבולות ללא מאבקי כוח.</li>
        <li>שיפור האווירה בבית והפחתת מתחים.</li>
        <li>ליווי אישי ומותאם לדינמיקה המשפחתית שלכם.</li>
      </ul>
    </div>
  );

  return (
    <ServicePageTemplate
      title="הדרכת הורים אשדוד | ADHD | שירה סהרוני"
      description="הדרכת הורים מקצועית באשדוד. התמחות בילדים עם ADHD, הצבת גבולות ושיפור האווירה המשפחתית."
      heroTitle="הדרכת הורים"
      heroSubtitle="מנהיגות הורית מתוך חיבור, הבנה וכלים פרקטיים ליום-יום."
      icon="👨‍👩‍👧"
      content={content}
    />
  );
};

export default ParentingGuidance;
