export const CONTACT_SERVICE_OPTIONS = [
  { value: 'couples', label: 'ייעוץ זוגי' },
  { value: 'premarital-first-year', label: 'הכנה לנישואים וליווי בשנה הראשונה' },
  { value: 'couples-aliyah-relocation', label: 'ייעוץ זוגי בעלייה או ברילוקיישן' },
  { value: 'late-singleness', label: 'ייעוץ במצבי רווקות מאוחרת' },
  { value: 'finding-relationship', label: 'ליווי למציאת זוגיות' },
  { value: 'parenting', label: 'הדרכת הורים' },
  { value: 'mediation', label: 'גישור' },
  { value: 'gifted-parenting', label: 'הנחיית הורים לילדים מחוננים' },
  { value: 'first-grade', label: 'הכנה לכיתה א׳ ותפקודים ניהוליים' },
  { value: 'gifted-framework', label: 'הכנה למסגרת מחוננים' },
  { value: 'aliyah-families', label: 'עולים ותושבים חוזרים' },
  { value: 'lectures', label: 'הזמנת הרצאה או סדנה' },
  { value: 'other', label: 'אחר' },
] as const;

export type ContactService = (typeof CONTACT_SERVICE_OPTIONS)[number]['value'];

const CONTACT_SERVICE_VALUES = new Set<string>(
  CONTACT_SERVICE_OPTIONS.map(({ value }) => value),
);

export const resolveContactService = (
  value: string | null | undefined,
): ContactService =>
  value && CONTACT_SERVICE_VALUES.has(value)
    ? (value as ContactService)
    : 'couples';
