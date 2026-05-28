import { spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve('.')
const venvPython = resolve(root, '.venv', 'Scripts', 'python.exe')
const python = existsSync(venvPython) ? venvPython : 'python'

const result = spawnSync(python, ['scripts/generate_report.py'], {
  cwd: root,
  stdio: 'inherit'
})

process.exit(result.status ?? 1)

