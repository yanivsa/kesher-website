import React from 'react';
import ServicePageTemplate from '../../../components/ServicePageTemplate/ServicePageTemplate';

const Mediation: React.FC = () => {
  const content = (
    <div>
      <p>גישור הוא הדרך המכבדת, המהירה והיעילה ביותר לפתרון סכסוכים, במיוחד בתהליכי פרידה וגירושין. כעורכת דין ומגשרת, אני מלווה אתכם בבניית הסכמים שמשרתים את כל הצדדים, ובעיקר את טובת הילדים.</p>
      <h3>למה לבחור בגישור?</h3>
      <ul>
        <li><strong>חיסכון בזמן ובכסף:</strong> הליך קצר וזול משמעותית מהתדיינות בבתי משפט.</li>
        <li><strong>שליטה בתוצאה:</strong> אתם אלו שקובעים את ההסכם, לא שופט חיצוני.</li>
        <li><strong>שמירה על מערכות יחסים:</strong> הליך המפחית עוינות ומאפשר תקשורת עתידית.</li>
        <li><strong>תוקף משפטי:</strong> ההסכם שמגובש בגישור מקבל תוקף של פסק דין.</li>
      </ul>
      <p>אני מביאה איתי את הניסיון המשפטי לצד הרגישות הטיפולית, כדי להבטיח שהתהליך יהיה בטוח ומקצועי עבורכם.</p>
    </div>
  );

  return (
    <ServicePageTemplate
      title="גישור גירושין אשדוד | שירה סהרוני עו״ד ומגשרת"
      description="גישור גירושין ומשפחה באשדוד. פתרון סכסוכים בדרכי שלום, בניית הסכמים וגירושין בשיתוף פעולה."
      heroTitle="גישור משפחתי"
      heroSubtitle="פתרון סכסוכים בדרכי שלום ובניית הסכמים שמכבדים את כל הצדדים."
      icon="⚖️"
      image="https://images.unsplash.com/photo-1573497019940-1c28c88b4f3e?auto=format&fit=crop&w=1200&q=80"
      content={content}
    />
  );
};

export default Mediation;
