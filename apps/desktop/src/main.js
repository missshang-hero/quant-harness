const { app, BrowserWindow, dialog, shell } = require('electron')
const { spawn } = require('node:child_process')
const fs = require('node:fs')
const http = require('node:http')
const path = require('node:path')

const API_PORT = Number(process.env.QUANT_DESKTOP_API_PORT || 8010)
const WEB_PORT = Number(process.env.QUANT_DESKTOP_WEB_PORT || 3010)

let apiProcess = null
let webProcess = null
let staticServer = null

function getRuntimeRoot() {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, 'quant-harness')
  }
  return path.resolve(__dirname, '..', '..', '..')
}

function getPythonExecutable(rootDir) {
  const venvPython = path.join(rootDir, 'apps', 'api', '.venv', 'bin', 'python')
  return fs.existsSync(venvPython) ? venvPython : 'python3'
}

function getNpmExecutable() {
  return process.platform === 'win32' ? 'npm.cmd' : 'npm'
}

function requestUrl(url, timeoutMs = 1500) {
  return new Promise((resolve) => {
    const req = http.get(url, (res) => {
      res.resume()
      resolve(res.statusCode >= 200 && res.statusCode < 500)
    })
    req.on('error', () => resolve(false))
    req.setTimeout(timeoutMs, () => {
      req.destroy()
      resolve(false)
    })
  })
}

async function waitForUrl(url, timeoutMs, label) {
  const startedAt = Date.now()
  while (Date.now() - startedAt < timeoutMs) {
    if (await requestUrl(url)) {
      return
    }
    await new Promise((resolve) => setTimeout(resolve, 500))
  }
  throw new Error(`${label} 启动超时：${url}`)
}

function spawnService(command, args, options, label) {
  const child = spawn(command, args, {
    ...options,
    stdio: ['ignore', 'pipe', 'pipe'],
  })

  child.stdout.on('data', (chunk) => {
    console.log(`[${label}] ${chunk.toString().trimEnd()}`)
  })
  child.stderr.on('data', (chunk) => {
    console.error(`[${label}] ${chunk.toString().trimEnd()}`)
  })
  child.on('exit', (code, signal) => {
    console.log(`[${label}] exited code=${code ?? 'null'} signal=${signal ?? 'null'}`)
  })

  return child
}

async function ensureApi(rootDir) {
  const healthUrl = `http://127.0.0.1:${API_PORT}/health`
  if (await requestUrl(healthUrl)) {
    return
  }

  const runtimeDir = path.join(app.getPath('userData'), 'runtime')
  const reportDir = path.join(app.getPath('userData'), 'reports', 'daily')
  fs.mkdirSync(runtimeDir, { recursive: true })
  fs.mkdirSync(reportDir, { recursive: true })

  apiProcess = spawnService(
    getPythonExecutable(rootDir),
    ['-m', 'uvicorn', 'apps.api.main:app', '--host', '127.0.0.1', '--port', String(API_PORT)],
    {
      cwd: rootDir,
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1',
        QUANT_HARNESS_RUNTIME_DIR: runtimeDir,
        QUANT_HARNESS_REPORT_DIR: reportDir,
      },
    },
    'api',
  )

  await waitForUrl(healthUrl, 45000, '后端服务')
}

function contentTypeFor(filePath) {
  const ext = path.extname(filePath).toLowerCase()
  const types = {
    '.css': 'text/css; charset=utf-8',
    '.html': 'text/html; charset=utf-8',
    '.ico': 'image/x-icon',
    '.js': 'text/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.map': 'application/json; charset=utf-8',
    '.svg': 'image/svg+xml',
    '.txt': 'text/plain; charset=utf-8',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
  }
  return types[ext] || 'application/octet-stream'
}

function resolveStaticFile(outDir, requestPath) {
  const cleanPath = decodeURIComponent(requestPath.split('?')[0] || '/')
  const normalized = cleanPath === '/' ? '/index.html' : cleanPath
  const candidates = [
    path.join(outDir, normalized),
    path.join(outDir, normalized, 'index.html'),
  ]

  for (const candidate of candidates) {
    const resolved = path.resolve(candidate)
    if (resolved.startsWith(path.resolve(outDir)) && fs.existsSync(resolved) && fs.statSync(resolved).isFile()) {
      return resolved
    }
  }

  return path.join(outDir, 'index.html')
}

function startStaticWeb(rootDir) {
  const outDir = path.join(rootDir, 'apps', 'web', 'out')
  if (!fs.existsSync(path.join(outDir, 'index.html'))) {
    throw new Error('未找到桌面前端静态文件，请先运行 apps/desktop 里的 npm run build:web')
  }

  staticServer = http.createServer((req, res) => {
    const filePath = resolveStaticFile(outDir, req.url || '/')
    fs.readFile(filePath, (err, body) => {
      if (err) {
        res.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' })
        res.end('读取桌面前端文件失败')
        return
      }
      res.writeHead(200, { 'Content-Type': contentTypeFor(filePath) })
      res.end(body)
    })
  })

  return new Promise((resolve, reject) => {
    staticServer.once('error', reject)
    staticServer.listen(WEB_PORT, '127.0.0.1', () => {
      staticServer.off('error', reject)
      resolve(`http://127.0.0.1:${WEB_PORT}`)
    })
  })
}

async function ensureWeb(rootDir) {
  const webUrl = `http://127.0.0.1:${WEB_PORT}`
  if (await requestUrl(webUrl)) {
    return webUrl
  }

  if (app.isPackaged || process.env.QUANT_DESKTOP_STATIC === '1') {
    return startStaticWeb(rootDir)
  }

  webProcess = spawnService(
    getNpmExecutable(),
    ['run', 'dev', '--', '-p', String(WEB_PORT)],
    {
      cwd: path.join(rootDir, 'apps', 'web'),
      env: {
        ...process.env,
        NEXT_PUBLIC_API_BASE_URL: `http://127.0.0.1:${API_PORT}`,
      },
    },
    'web',
  )

  await waitForUrl(webUrl, 60000, '前端服务')
  return webUrl
}

function createWindow(webUrl) {
  const win = new BrowserWindow({
    width: 1400,
    height: 940,
    minWidth: 1100,
    minHeight: 720,
    title: '极投雷达',
    backgroundColor: '#f4f6f8',
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, 'preload.js'),
    },
  })

  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })
  win.loadURL(webUrl)
}

function stopServices() {
  for (const child of [webProcess, apiProcess]) {
    if (child && !child.killed) {
      child.kill()
    }
  }
  if (staticServer) {
    staticServer.close()
  }
}

async function startApp() {
  try {
    const rootDir = getRuntimeRoot()
    await ensureApi(rootDir)
    const webUrl = await ensureWeb(rootDir)
    createWindow(webUrl)
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    dialog.showErrorBox('极投雷达启动失败', message)
    app.quit()
  }
}

app.whenReady().then(startApp)

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    startApp()
  }
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('before-quit', stopServices)
