import { createI18n } from 'vue-i18n'
import { watch } from 'vue'
import zhCN from './zh-CN.json'
import en from './en.json'

export const supportedLocales = [
  { value: 'zh-CN', label: '简体中文' },
  { value: 'en', label: 'English' },
]
const storageKey = 'xmmcg.locale'
export function resolveLocale(saved, languages = []) {
  if (supportedLocales.some(({ value }) => value === saved)) return saved
  for (const language of languages) {
    if (/^zh(?:-|$)/i.test(language)) return 'zh-CN'
    if (/^en(?:-|$)/i.test(language)) return 'en'
  }
  return 'zh-CN'
}
let savedLocale
try {
  if (typeof window !== 'undefined') savedLocale = window.localStorage.getItem(storageKey)
} catch {
  // Browsers may disable storage; language switching still works for this session.
}
export const i18n = createI18n({
  legacy: false,
  locale: resolveLocale(savedLocale, globalThis.navigator?.languages),
  fallbackLocale: 'zh-CN',
  messages: { 'zh-CN': zhCN, en },
})
export const t = (...args) => i18n.global.t(...args)
watch(
  i18n.global.locale,
  (locale) => {
    if (typeof document !== 'undefined') document.documentElement.lang = locale
    try {
      if (typeof window !== 'undefined') window.localStorage.setItem(storageKey, locale)
    } catch {
      // Keep the selected language in memory when storage is unavailable.
    }
  },
  { immediate: true, flush: 'sync' },
)
