import { execFileSync, spawn } from 'node:child_process'
import { cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { resolve } from 'node:path'

process.env.PLAYWRIGHT_BROWSERS_PATH ||= 'E:\\缓存\\playwright'
const { chromium } = await import('playwright')
const root = resolve('.')
const screenshotDir = resolve(root, 'screenshots')
const dataDb = resolve(root, 'data', 'assistant.db')
const uploadDir = resolve(root, 'uploads')
const backupRoot = mkdtempSync(resolve(tmpdir(), 'ai-study-screenshots-'))
mkdirSync(screenshotDir, { recursive: true })
const venvPython = resolve(root, '.venv', 'Scripts', 'python.exe')
const python = existsSync(venvPython)
  ? venvPython
  : 'python'

function cleanUploads() {
  if (!existsSync(uploadDir)) return
  for (const file of readdirSync(uploadDir)) {
    if (file !== '.gitkeep') {
      rmSync(resolve(uploadDir, file), { force: true })
    }
  }
}

function backupRuntimeData() {
  const state = {
    hadDb: existsSync(dataDb),
    hadUploads: existsSync(uploadDir)
  }
  if (state.hadDb) cpSync(dataDb, resolve(backupRoot, 'assistant.db'))
  if (state.hadUploads) cpSync(uploadDir, resolve(backupRoot, 'uploads'), { recursive: true })
  return state
}

function resetDemoData() {
  rmSync(dataDb, { force: true })
  cleanUploads()
}

async function restoreRuntimeData(state) {
  await rmWithRetry(dataDb, { force: true })
  if (state.hadDb) cpSync(resolve(backupRoot, 'assistant.db'), dataDb)
  cleanUploads()
  const backupUploads = resolve(backupRoot, 'uploads')
  if (state.hadUploads && existsSync(backupUploads)) {
    for (const file of readdirSync(backupUploads)) {
      if (file !== '.gitkeep') {
        cpSync(resolve(backupUploads, file), resolve(uploadDir, file), { recursive: true })
      }
    }
  }
  rmSync(backupRoot, { recursive: true, force: true })
}

function run(command, args, cwd) {
  return spawn(command, args, {
    cwd,
    stdio: 'ignore',
    windowsHide: true
  })
}

function wait(ms) {
  return new Promise((resolveWait) => setTimeout(resolveWait, ms))
}

async function stopProcess(process) {
  if (!process || process.killed || process.exitCode !== null) return
  process.kill()
  await Promise.race([
    new Promise((resolveWait) => process.once('exit', resolveWait)),
    wait(5000)
  ])
}

async function rmWithRetry(path, options) {
  for (let attempt = 0; attempt < 8; attempt += 1) {
    try {
      rmSync(path, options)
      return
    } catch (error) {
      if (error.code !== 'EPERM' && error.code !== 'EBUSY') throw error
      await wait(250)
    }
  }
  rmSync(path, options)
}

function cleanupDevPorts() {
  if (process.platform !== 'win32') return
  for (const port of [8000, 5173]) {
    execFileSync(
      'powershell.exe',
      [
        '-NoProfile',
        '-Command',
        `Get-NetTCPConnection -LocalPort ${port} -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Listen' } | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }`
      ],
      { stdio: 'ignore' }
    )
  }
}

async function waitFor(url, timeoutMs = 45000) {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    try {
      const response = await fetch(url)
      if (response.ok) return
    } catch {
      await new Promise((resolveWait) => setTimeout(resolveWait, 800))
    }
  }
  throw new Error(`服务启动超时：${url}`)
}

async function post(url, body = {}) {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
  if (!response.ok) {
    throw new Error(await response.text())
  }
  return response.json()
}

async function uploadTestMaterial() {
  const materialPath = resolve(root, '测试资料', '0. AI提示语工程.pdf')
  const form = new FormData()
  form.append('file', new Blob([readFileSync(materialPath)], { type: 'application/pdf' }), '0. AI提示语工程.pdf')
  const response = await fetch('http://127.0.0.1:8000/api/documents/upload', {
    method: 'POST',
    body: form
  })
  if (!response.ok) {
    throw new Error(await response.text())
  }
}

const runtimeState = backupRuntimeData()
resetDemoData()

const backend = run(python, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000'], resolve(root, 'backend'))
const frontend =
  process.platform === 'win32'
    ? run('cmd.exe', ['/d', '/s', '/c', 'npm', 'run', 'dev', '--', '--host', '127.0.0.1', '--port', '5173'], resolve(root, 'frontend'))
    : run('npm', ['run', 'dev', '--', '--host', '127.0.0.1', '--port', '5173'], resolve(root, 'frontend'))

try {
  await waitFor('http://127.0.0.1:8000/api/health')
  await waitFor('http://127.0.0.1:5173')

  await uploadTestMaterial()
  const outline = await post('http://127.0.0.1:8000/api/outline', { provider: 'mock' })
  const chapter = outline.chapters[0]
  await post(`http://127.0.0.1:8000/api/chapters/${chapter.id}/content`, { provider: 'mock' })
  const quiz = await post(`http://127.0.0.1:8000/api/chapters/${chapter.id}/quiz`, { provider: 'mock' })
  const answers = Object.fromEntries(quiz.quizzes.map((item) => [String(item.id), item.options[1] || '']))
  await post(`http://127.0.0.1:8000/api/chapters/${chapter.id}/submit`, { answers })

  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } })
  await page.goto('http://127.0.0.1:5173', { waitUntil: 'networkidle' })
  await page.screenshot({ path: resolve(screenshotDir, '01-face-login.png'), fullPage: false })
  await page.evaluate(() => {
    const setupState = document.querySelector('#app')?.__vue_app__?._instance?.setupState
    if (!setupState) return
    setupState.face.ok = true
    setupState.status.warning = ''
    setupState.status.message = '人脸识别通过，可以开始学习。'
  })
  await page.waitForSelector('.app-nav')
  await page.locator('.app-nav button').nth(4).click()
  await page.screenshot({ path: resolve(screenshotDir, '02-provider-dashboard.png'), fullPage: false })
  await page.locator('.app-nav button').nth(0).click()
  await page.locator('.content-frame').screenshot({ path: resolve(screenshotDir, '03-knowledge-outline-workspace.png') })
  await page.locator('.app-nav button').nth(1).click()
  await page.locator('.content-panel').screenshot({ path: resolve(screenshotDir, '04-chapter-content.png') })
  await page.locator('.toolbar button').nth(1).click()
  await page.waitForSelector('.quiz-list')
  await page.locator('.content-frame').screenshot({ path: resolve(screenshotDir, '05-quiz-wrong-answers.png') })
  await page.locator('.app-nav button').nth(3).click()
  await page.locator('.voice-page').screenshot({ path: resolve(screenshotDir, '06-voice-control.png') })
  await browser.close()
  console.log(`Screenshots saved to ${screenshotDir}`)
} finally {
  await stopProcess(backend)
  await stopProcess(frontend)
  cleanupDevPorts()
  await restoreRuntimeData(runtimeState)
}
