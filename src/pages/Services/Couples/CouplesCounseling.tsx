import React from 'react';
import ServicePageTemplate from '../../../components/ServicePageTemplate/ServicePageTemplate';

const CouplesCounseling: React.FC = () => {
  const content = (
    <div>
      <p>ייעוץ זוגי הוא מרחב בטוח לחקור את הדינמיקה ביניכם, להבין את מקור הקונפליקטים ולמצוא דרכים חדשות ומקרבות לתקשורת.</p>
      <h3>איך זה עובד?</h3>
      <ul>
        <li>זיהוי דפוסי תקשורת מעכבים.</li>
        <li>לימוד כלים לפתרון קונפליקטים בצורה מכבדת.</li>
        <li>בניית אמון ואינטימיות מחודשת.</li>
        <li>עבודה עם שיטת גוטמן ו-EFT.</li>
      </ul>
      <p>בין אם אתם חווים משבר עמוק או פשוט מרגישים שהתרחקתם, הייעוץ יעזור לכם לחזור ולהיות צוות אחד.</p>
    </div>
  );

  return (
    <ServicePageTemplate
      title="ייעוץ זוגי באשדוד | שירה סהרוני"
      description="ייעוץ זוגי מקצועי ורגיש באשדוד. בואו לשפר את התקשורת, לפתור קונפליקטים ולהחזיר את האינטימיות לקשר."
      heroTitle="ייעוץ זוגי"
      heroSubtitle="בניית גשרים של תקשורת ואינטימיות בלב הקשר שלכם."
      icon="💑"
      content={content}
    />
  );
};

export default CouplesCounseling;
