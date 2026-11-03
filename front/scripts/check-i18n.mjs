import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { createI18n } from 'vue-i18n'
import { createServer } from 'vite'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const zh = JSON.parse(read('../src/i18n/zh-CN.json'))
const en = JSON.parse(read('../src/i18n/en.json'))
const placeholders = (text) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort()
assert.deepEqual(Object.keys(zh).sort(), Object.keys(en).sort())
const translator = createI18n({ legacy: false, locale: 'en', messages: { en } }).global
for (const key of Object.keys(zh)) {
  assert.ok(en[key].trim(), `Empty translation: ${key}`)
  assert.deepEqual(placeholders(zh[key]), placeholders(en[key]), `Parameters differ: ${key}`)
  const args = Object.fromEntries(placeholders(en[key]).map((name) => [name, 3]))
  assert.equal(translator.t(key, args), en[key].replace(/\{\w+\}/g, '3'), key)
}
// Catch references to missing messages in templates, scripts and route titles.
const files = readdirSync(new URL('../src', import.meta.url), { recursive: true })
for (const file of files.filter((file) => /\.(vue|js)$/.test(file))) {
  const source = read(`../src/${file}`)
  for (const match of source.matchAll(/\bt\(['"]([^'"]+)['"]/g)) {
    assert.ok(Object.hasOwn(zh, match[1]), `${file}: unknown key ${match[1]}`)
  }
  if (file === 'router/index.js') {
    for (const match of source.matchAll(/title: '([^']+)'/g)) {
      assert.ok(Object.hasOwn(zh, match[1]), `Unknown route title: ${match[1]}`)
    }
  }
}
// Load through Vite so JSON imports use the same path as the application.
const server = await createServer({
  server: { middlewareMode: true, hmr: false, ws: false },
  appType: 'custom',
})
try {
  const { i18n, resolveLocale, t } = await server.ssrLoadModule('/src/i18n/index.js')
  assert.equal(resolveLocale('en', ['zh-CN']), 'en')
  assert.equal(resolveLocale('zh-CN', ['en-US']), 'zh-CN')
  assert.equal(resolveLocale('invalid', ['en-GB']), 'en')
  assert.equal(resolveLocale(null, ['ja', 'zh-TW']), 'zh-CN')
  assert.equal(resolveLocale(null, ['ja']), 'zh-CN')
  i18n.global.locale.value = 'zh-CN'
  assert.equal(t('logIn'), '登录')
  i18n.global.locale.value = 'en'
  assert.equal(t('logIn'), 'Log in')
  assert.equal(t('remainingTime', { days: 2, hours: 3 }), '2 days 3 hours')
} finally {
  await server.close()
}
console.log(`i18n checks passed: ${Object.keys(zh).length} messages in each locale`)
