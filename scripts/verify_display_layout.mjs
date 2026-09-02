/**
 * verify_display_layout.mjs —— Task-23 live-test 修复验证(真实布局,Chrome headless CDP)。
 *
 * 验证 /#/display 两形态在任意视口下的几何(不依赖 pywebview,纯浏览器):
 *   1) corner 形态:400×250 视口内卡片恰好满幅 (0,0,400,250);大视口居中(浏览器回退)。
 *   2) expanded 形态:点 [⛶ 全屏] 后根节点 fixed inset-0 —— rect == 视口全幅(1280×800 与
 *      1920×1080 两组),footer 贴底。vw 字号随视口缩放。
 *   3) 因果 A/B:运行时把 expanded 根换回旧写法(h-full w-full + 祖先去 h-full),
 *      高度应塌陷为内容高(< 视口)—— 证明修复命中根因而非碰巧。
 *
 * 用法:先起静态服务(python -m http.server -d frontend/dist 8899)与本脚本自带 chrome:
 *   node scripts/verify_display_layout.mjs [baseUrl=127.0.0.1]
 */
import { spawn } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'

const BASE = process.argv[2] || '127.0.0.1'
const URL = `http://${BASE}:8899/#/display`
const DBG_PORT = 9333
const SHOT_DIR = '/tmp/cc-verify'
mkdirSync(SHOT_DIR, { recursive: true })

const sleep = ms => new Promise(r => setTimeout(r, ms))

// ---- 极简 CDP 客户端(原生 WebSocket,node>=21)----
class CDP {
  constructor(ws) { this.ws = ws; this.id = 0; this.pending = new Map()
    this.listeners = []
    ws.addEventListener('message', ev => {
      const m = JSON.parse(ev.data)
      if (m.id && this.pending.has(m.id)) {
        const { res, rej } = this.pending.get(m.id); this.pending.delete(m.id)
        m.error ? rej(new Error(m.error.message)) : res(m.result)
      } else this.listeners.forEach(f => f(m))
    })
  }
  static async connect(url) {
    const ws = new WebSocket(url)
    await new Promise((res, rej) => { ws.addEventListener('open', res)
      ws.addEventListener('error', rej) })
    return new CDP(ws)
  }
  send(method, params = {}) {
    const id = ++this.id
    this.ws.send(JSON.stringify({ id, method, params }))
    return new Promise((res, rej) => this.pending.set(id, { res, rej }))
  }
  onEvent(f) { this.listeners.push(f) }
}

const results = []
const check = (name, ok, detail) => {
  results.push({ name, ok, detail })
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}  ${detail}`)
}

async function evalJS(cdp, expr) {
  const r = await cdp.send('Runtime.evaluate',
    { expression: expr, returnByValue: true, awaitPromise: true })
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.text)
  return r.result.value
}
const rect = sel => evalJS(cdp0, `(function(){
  const el = document.querySelector(${JSON.stringify(sel)})
  if (!el) return null
  const r = el.getBoundingClientRect()
  return { x: r.x, y: r.y, w: r.width, h: r.height }
})()`)

let cdp0
async function shot(name) {
  const r = await cdp0.send('Page.captureScreenshot', { format: 'png' })
  writeFileSync(`${SHOT_DIR}/${name}.png`, Buffer.from(r.data, 'base64'))
}

async function setViewport(w, h) {
  await cdp0.send('Emulation.setDeviceMetricsOverride',
    { width: w, height: h, deviceScaleFactor: 1, mobile: false })
  await sleep(120)
}
/** 等 expanded 根出现 + out-in 过渡(两段 550ms)结束 */
async function waitExpanded() {
  for (let i = 0; i < 60; i++) {
    if (await evalJS(cdp0, `!!document.querySelector('.exit-fs')`)) break
    await sleep(100)
  }
  await sleep(900)
}
/** 等 corner 卡出现(切回/初载) */
async function waitCorner() {
  for (let i = 0; i < 60; i++) {
    if (await evalJS(cdp0, `!!document.querySelector('.glass-card')`)) break
    await sleep(100)
  }
  await sleep(900)
}

const chrome = spawn('google-chrome-stable', [
  '--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
  `--remote-debugging-port=${DBG_PORT}`, '--user-data-dir=/tmp/cc-verify-profile',
  '--no-first-run', '--no-default-browser-check', 'about:blank',
], { stdio: 'ignore' })

try {
  // 等 devtools 端口就绪
  let target
  for (let i = 0; i < 50; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${DBG_PORT}/json/list`)).json()
      target = list.find(t => t.type === 'page')
      if (target) break
    } catch { /* not up yet */ }
    await sleep(200)
  }
  if (!target) throw new Error('devtools 端口未就绪')
  cdp0 = await CDP.connect(target.webSocketDebuggerUrl)
  await cdp0.send('Page.enable')
  await cdp0.send('Runtime.enable')

  // ---- 1) corner @400×250:卡片恰好满幅 ----
  await setViewport(400, 250)
  await cdp0.send('Page.navigate', { url: URL })
  await sleep(1200)
  // 记忆班级 → 跳过选班卡(localStorage 与页面同源,load 后即可写)
  await evalJS(cdp0, `localStorage.setItem('cc_class','1');
                      localStorage.setItem('cc_class_name','测试班级'); location.reload()`)
  await waitCorner()
  let r = await rect('.glass-card')
  // 注:UnoCSS preset-uno 不带 box-sizing 重置 → content-box,glass-card 1px 边框
  // 外扩 → 实测约 402×252。断言"覆盖视口"而非精确 400×250。
  check('corner@400x250 卡片满幅', r && r.x <= 0.5 && r.y <= 0.5 && r.w >= 400 && r.h >= 250,
    JSON.stringify(r))
  await shot('1-corner-400x250')

  // ---- 2) corner @1280×800:浏览器回退居中 ----
  await setViewport(1280, 800)
  await sleep(600)
  r = await rect('.glass-card')
  const cx = r && r.x + r.w / 2, cy = r && r.y + r.h / 2
  check('corner@1280x800 居中回退', r && Math.abs(cx - 640) <= 2 && Math.abs(cy - 400) <= 2,
    `center=(${cx},${cy}) ${JSON.stringify(r)}`)

  // ---- 3) expanded @1280×800:fixed inset-0 撑满视口 ----
  await evalJS(cdp0, `[...document.querySelectorAll('button')].find(b => b.textContent.includes('全屏'))?.click()`)
  await waitExpanded()
  // expanded 根 = .exit-fs 的父节点
  r = await evalJS(cdp0, `(function(){
    const el = document.querySelector('.exit-fs').parentElement
    const rr = el.getBoundingClientRect()
    const cs = getComputedStyle(el)
    const foot = document.querySelector('footer')
    return { x: rr.x, y: rr.y, w: rr.width, h: rr.height,
      pos: cs.position, top: cs.top, right: cs.right,
      footBottom: foot ? foot.getBoundingClientRect().bottom : null }
  })()`)
  check('expanded@1280x800 fixed 定位', r.pos === 'fixed' && r.top === '0px' && r.right === '0px',
    `pos=${r.pos} top=${r.top} right=${r.right}`)
  check('expanded@1280x800 撑满视口', r.x === 0 && r.y === 0 && r.w === 1280 && r.h === 800
    && r.footBottom === 800, JSON.stringify(r))
  await shot('2-expanded-1280x800')

  // ---- 4) expanded @1920×1080:任意视口都撑满(vw 字号随动)----
  await setViewport(1920, 1080)
  await sleep(600)
  r = await evalJS(cdp0, `(function(){
    const el = document.querySelector('.exit-fs').parentElement
    const rr = el.getBoundingClientRect()
    const names = document.querySelector('.names')   // 无叫号时不存在,仅观测
    return { x: rr.x, y: rr.y, w: rr.width, h: rr.height,
      nameFs: names ? getComputedStyle(names).fontSize : null }
  })()`)
  check('expanded@1920x1080 撑满视口', r.x === 0 && r.y === 0 && r.w === 1920 && r.h === 1080,
    JSON.stringify(r))
  await shot('3-expanded-1920x1080')

  // ---- 5) 因果 A/B:换回旧写法(h-full w-full + 祖先去 h-full)→ 高度应塌陷 ----
  const old = await evalJS(cdp0, `(function(){
    const full = document.querySelector('.exit-fs').parentElement
    full.removeAttribute('fixed'); full.removeAttribute('inset-0')
    full.setAttribute('h-full', ''); full.setAttribute('w-full', '')
    document.querySelector('#app > div').removeAttribute('h-full')  // 还原 App.vue 旧包裹
    const rr = full.getBoundingClientRect()
    return { w: rr.width, h: rr.height, vh: innerHeight, vw: innerWidth }
  })()`)
  check('A/B 旧写法高度塌陷(bug 复现)', old.h < old.vh - 40,
    `旧写法 content=${Math.round(old.w)}x${Math.round(old.h)} < viewport=${old.vw}x${old.vh}`)
  await shot('4-old-css-broken')

  const failed = results.filter(x => !x.ok)
  console.log(`\n${results.length - failed.length}/${results.length} checks passed`)
  process.exitCode = failed.length ? 1 : 0
} finally {
  chrome.kill()
}
