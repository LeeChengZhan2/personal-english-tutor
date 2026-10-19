// Screenshots of the running app for visual checks, using the installed Microsoft Edge (no browser download).
// Usage: node scripts/screenshot.mjs <out-dir> [base-url] [names...]
import { mkdirSync } from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright-core'

const out = process.argv[2] ?? 'screenshots'
const base = process.argv[3] ?? 'http://127.0.0.1:8765'
const only = process.argv.slice(4)
const SHOTS = [
  { name: 'home', path: '/', width: 1440, height: 1250 },
  { name: 'home-dark', path: '/', width: 1440, height: 1250, theme: 'dark' },
  { name: 'mistakes', path: '/mistakes', width: 1440, height: 1100 },
  { name: 'mistake', path: '/mistakes/do-support', width: 1440, height: 1250 },
  { name: 'grammar', path: '/grammar', width: 1440, height: 1100 },
  { name: 'grammar-lesson', path: '/grammar/do-support', width: 1440, height: 2400 },
  { name: 'words', path: '/words', width: 1440, height: 1250 },
  { name: 'words-fix', path: '/words?group=fix', width: 1440, height: 1250 },
  { name: 'messages', path: '/messages', width: 1440, height: 1250 },
  { name: 'progress', path: '/progress', width: 1440, height: 1500 },
  { name: 'progress-dark', path: '/progress', width: 1440, height: 1500, theme: 'dark' },
  { name: 'settings', path: '/settings', width: 1440, height: 1250 },
  { name: 'help', path: '/help', width: 1440, height: 1250 },
  { name: 'home-phone', path: '/', width: 390, height: 1400, mobile: true },
  { name: 'mistake-phone', path: '/mistakes/do-support', width: 390, height: 1400, mobile: true, theme: 'dark' },
]

mkdirSync(out, { recursive: true })
const browser = await chromium.launch({ channel: 'msedge', headless: true })
let failures = 0
for (const shot of SHOTS.filter((s) => !only.length || only.includes(s.name))) {
  const context = await browser.newContext({
    viewport: { width: shot.width, height: shot.height },
    colorScheme: shot.theme === 'dark' ? 'dark' : 'light',
    isMobile: Boolean(shot.mobile),
    hasTouch: Boolean(shot.mobile),
    deviceScaleFactor: 1,
  })
  const page = await context.newPage()
  const errors = []
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))
  page.on('pageerror', (e) => errors.push(String(e)))
  const sep = shot.path.includes('?') ? '&' : '?'
  await page.goto(`${base}${shot.path}${sep}theme=${shot.theme ?? 'light'}`, { waitUntil: 'networkidle' })
  await page.waitForSelector('main h1, h1', { timeout: 15000 }).catch(() => errors.push('no <h1> rendered'))
  await page.waitForTimeout(shot.path.startsWith('/progress') ? 1800 : 500)
  const file = path.join(out, `${shot.name}.png`)
  await page.screenshot({ path: file, fullPage: false })
  console.log(`${errors.length ? 'ERR' : 'ok '} ${file}${errors.length ? '  ' + errors.join(' | ') : ''}`)
  failures += errors.length ? 1 : 0
  await context.close()
}
await browser.close()
process.exit(failures ? 1 : 0)
