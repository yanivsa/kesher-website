import editorialSlots from './financialGuidanceArchiveSlots.json';

// Editorial sort positions only. Never feed them to Article dates or sitemaps.
const slots = editorialSlots as Record<string, string>;

export const getFinancialArchiveSlot = (id: string): string | undefined => slots[id];

export const getEditorialArchiveSortDate = (id: string, publishedDate: string): string =>
  getFinancialArchiveSlot(id) || publishedDate;
