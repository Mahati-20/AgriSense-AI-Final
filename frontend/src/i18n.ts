import en from './translations/en.json';
import hi from './translations/hi.json';
import te from './translations/te.json';
import kn from './translations/kn.json';
import ta from './translations/ta.json';

export type LanguageCode = 'en' | 'hi' | 'te' | 'kn' | 'ta';

const translations: Record<LanguageCode, Record<string, string>> = {
  en,
  hi,
  te,
  kn,
  ta,
};

export const getTranslation = (language: LanguageCode, key: string) => translations[language][key] ?? key;
