import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'

import commonEs from '../locales/es/common.json'
import authEs from '../locales/es/auth.json'
import topicsEs from '../locales/es/topics.json'
import documentsEs from '../locales/es/documents.json'
import chatEs from '../locales/es/chat.json'
import commonEn from '../locales/en/common.json'
import authEn from '../locales/en/auth.json'
import topicsEn from '../locales/en/topics.json'
import documentsEn from '../locales/en/documents.json'
import chatEn from '../locales/en/chat.json'

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    fallbackLng: 'es',
    defaultNS: 'common',
    resources: {
      es: { common: commonEs, auth: authEs, topics: topicsEs, documents: documentsEs, chat: chatEs },
      en: { common: commonEn, auth: authEn, topics: topicsEn, documents: documentsEn, chat: chatEn },
    },
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
      lookupLocalStorage: 'docsrag-language',
    },
    interpolation: { escapeValue: false },
  })

export default i18n
