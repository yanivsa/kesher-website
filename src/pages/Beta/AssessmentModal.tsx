import React, { useState } from 'react';
import { FiX, FiCheckCircle, FiArrowLeft, FiMessageCircle } from 'react-icons/fi';

interface AssessmentModalProps {
  isOpen: boolean;
  onClose: () => void;
}

const questions = [
  {
    id: 1,
    title: 'מה הסימן הבולט ביותר אצלכם כיום?',
    subtitle: 'בחרו את התשובה שמטרידה אתכם הכי הרבה',
    options: [
      'השתיקות בבית והתרחקות רגשית בסוף היום',
      'מריבות חוזרות בלתי פוסקות על אותם נושאים',
      'תחושה שאנחנו שותפים לניהול הבית ולא בני זוג',
      'קושי להקשיב בלי להתגונן ולהאשים',
    ],
  },
  {
    id: 2,
    title: 'כמה זמן אתם חשים שדרוש שינוי בתקשורת?',
    subtitle: 'הערכת זמן מעוררת מודעות',
    options: [
      'מספר חודשים האחרונים',
      'בין שנה לשנתיים',
      'למעלה משנתיים (שחיקה מתמשכת)',
    ],
  },
  {
    id: 3,
    title: 'מה התוצאה שהכי חשוב לכם להשיג בתהליך?',
    subtitle: 'מה יחזיר לכם את הביטחון',
    options: [
      'להחזיר את השיח החם, הקרבה והחבירות',
      'לדעת לנהל מחלוקת בלי להסלים למאבק',
      'לבנות גבולות ושגרה רגועה לבית ולילדים',
      'לקבל החלטות משותפות בבהירות ובשקט',
    ],
  },
];

const AssessmentModal: React.FC<AssessmentModalProps> = ({ isOpen, onClose }) => {
  const [currentStep, setCurrentStep] = useState(0);
  const [, setAnswers] = useState<Record<number, string>>({});
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [submitted, setSubmitted] = useState(false);

  if (!isOpen) return null;

  const handleSelectOption = (option: string) => {
    setAnswers((prev) => ({ ...prev, [currentStep]: option }));
    if (currentStep < questions.length - 1) {
      setCurrentStep((prev) => prev + 1);
    } else {
      setCurrentStep(questions.length); // Move to lead form step
    }
  };

  const handleSubmitLead = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !phone) return;
    setSubmitted(true);
  };

  const handleReset = () => {
    setCurrentStep(0);
    setAnswers({});
    setName('');
    setPhone('');
    setSubmitted(false);
    onClose();
  };

  return (
    <div
      className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/80 backdrop-blur-md transition-opacity duration-300"
      role="dialog"
      aria-modal="true"
      dir="rtl"
    >
      <div className="relative w-full max-w-xl bg-[#121217] border border-[#2a2a35] rounded-2xl shadow-2xl p-6 md:p-8 text-white overflow-hidden">
        {/* Close Button */}
        <button
          onClick={handleReset}
          className="absolute top-4 left-4 p-2 text-gray-400 hover:text-white rounded-full bg-white/5 hover:bg-white/10 transition-colors"
          aria-label="סגירה"
        >
          <FiX className="w-5 h-5" />
        </button>

        {!submitted ? (
          <div>
            {/* Header / Progress bar */}
            <div className="mb-6">
              <span className="text-xs uppercase tracking-widest text-[#E5C158] font-bold">
                שאלון אבחון זוגי קצר (60 שניות)
              </span>
              <div className="w-full h-1.5 bg-white/10 rounded-full mt-2 overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-[#E5C158] to-[#E0A96D] transition-all duration-300"
                  style={{
                    width: `${((currentStep + 1) / (questions.length + 1)) * 100}%`,
                  }}
                />
              </div>
            </div>

            {currentStep < questions.length ? (
              <div>
                <h3 className="text-xl md:text-2xl font-bold font-heebo text-white mb-1">
                  {questions[currentStep].title}
                </h3>
                <p className="text-sm text-gray-400 mb-6">
                  {questions[currentStep].subtitle}
                </p>

                <div className="space-y-3">
                  {questions[currentStep].options.map((opt, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSelectOption(opt)}
                      className="w-full text-right p-4 rounded-xl bg-[#1a1a24] border border-[#2d2d3d] hover:border-[#E5C158] hover:bg-[#222230] transition-all duration-200 flex items-center justify-between group"
                    >
                      <span className="text-sm md:text-base font-medium text-gray-200 group-hover:text-white">
                        {opt}
                      </span>
                      <FiArrowLeft className="w-4 h-4 text-gray-500 group-hover:text-[#E5C158] group-hover:-translate-x-1 transition-all" />
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              /* Lead Capture Form */
              <form onSubmit={handleSubmitLead} className="space-y-4">
                <h3 className="text-xl md:text-2xl font-bold font-heebo text-white mb-1">
                  הערכת האבחון הראשונית מוכנה!
                </h3>
                <p className="text-sm text-gray-300 mb-4">
                  השאירו פרטים דיסקרטיים לקבלת הסיכום ותיאום שיחת אבחון והתאמה אישית עם שירה סהרוני (ללא התחייבות).
                </p>

                <div>
                  <label className="block text-xs font-semibold text-gray-300 mb-1">
                    שם פרטי ומשפחה
                  </label>
                  <input
                    type="text"
                    required
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="השם שלכם"
                    className="w-full p-3 rounded-lg bg-[#1a1a24] border border-[#2d2d3d] text-white focus:outline-none focus:border-[#E5C158]"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-gray-300 mb-1">
                    מספר טלפון / וואטסאפ
                  </label>
                  <input
                    type="tel"
                    required
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="050-0000000"
                    className="w-full p-3 rounded-lg bg-[#1a1a24] border border-[#2d2d3d] text-white focus:outline-none focus:border-[#E5C158]"
                  />
                </div>

                <button
                  type="submit"
                  className="w-full py-3.5 px-6 rounded-xl bg-gradient-to-r from-[#E5C158] to-[#D4AF37] text-black font-bold font-heebo hover:brightness-110 transition-all duration-200 shadow-lg shadow-[#E5C158]/20 mt-2"
                >
                  לשליחה וקבלת שיחת אבחון ללא התחייבות
                </button>

                <p className="text-[11px] text-gray-400 text-center mt-2 leading-tight">
                  מסירת הפרטים נעשית מרצונכם החופשי לצורך חזרה אליכם לשיחת אבחון והתאמה דיסקרטית באשדוד/אונליין, בהתאם ל<a href="/privacy" target="_blank" className="underline hover:text-[#E5C158]">מדיניות הפרטיות</a>.
                </p>
              </form>
            )}
          </div>
        ) : (
          /* Confirmation Success State */
          <div className="text-center py-8 space-y-4">
            <FiCheckCircle className="w-14 h-14 text-[#E5C158] mx-auto animate-bounce" />
            <h3 className="text-2xl font-bold font-heebo text-white">
              תודה {name}, הפנייה התקבלה בדיסקרטיות!
            </h3>
            <p className="text-sm text-gray-300 max-w-md mx-auto">
              שירה סהרוני או צוות המרכז יחזרו אליכם בהקדם לתיאום שיחת אבחון והתאמה אישית.
            </p>

            <div className="pt-4 flex flex-col sm:flex-row gap-3 justify-center">
              <a
                href={`https://wa.me/972500000000?text=${encodeURIComponent(
                  `שלום שירה, מילאתי את השאלון באתר: ${name}, טלפון: ${phone}`
                )}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center gap-2 px-5 py-3 rounded-xl bg-[#25D366] text-black font-bold hover:brightness-110 transition-all"
              >
                <FiMessageCircle className="w-5 h-5" />
                פנייה מיידית בוואטסאפ
              </a>

              <button
                onClick={handleReset}
                className="px-5 py-3 rounded-xl bg-white/10 hover:bg-white/20 text-white font-medium transition-colors"
              >
                סגירה
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default AssessmentModal;
