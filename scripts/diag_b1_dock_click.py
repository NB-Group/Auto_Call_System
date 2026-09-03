"""B1 因果诊断:pywebview GTK(WebKitGTK)真窗口里,teacher 页 Dock 的
短语/资料 router-link 上报"点不动"。jsdom 整链测试(Dock.test.ts)已绿,
故嫌疑在环境层。本探针在真实 WebView 里依次回答:

  1) 链接存不存在、rect 在哪(视口内?)
  2) elementFromPoint(rect 中心)命中的是谁 —— 有没有东西盖住(hit-testing)
  3) 派发带坐标的完整 mousedown/mouseup/click 序列 —— 事件→路由链路通不通
  4) hash 与页面文本在点击后有没有变、chunk 资源有没有加载失败
  5) window.onerror / unhandledrejection 全程记录

用法: .venv-gui/bin/python scripts/diag_b1_dock_click.py [server_url]
结果写 /tmp/b1_diag.json(脚本结束自动关窗)。只读诊断,不改任何状态。
"""
import json
import sys
import threading
import time

import webview

OUT = "/tmp/b1_diag.json"
URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8800/"
result: dict = {"url": URL}

# onerror/unhandledrejection 要在页面早期就挂上(晚挂只漏早期错,点击期错误必在)
JS_HOOK_ERRS = """
window.__errs = [];
window.addEventListener('error', e => __errs.push('err:' + e.message + '@' + (e.filename||'') + ':' + e.lineno));
window.addEventListener('unhandledrejection', e => __errs.push('rej:' + String(e.reason && e.reason.message || e.reason)));
"""

JS_LOGIN = """
fetch('/api/auth/login', {method:'POST', headers:{'Content-Type':'application/json'},
  body: JSON.stringify({username:'zheng', password:'pw123456'})})
  .then(r => r.json())
  .then(j => { if (!j.token) { window.__errs.push('login-no-token:' + JSON.stringify(j)); return; }
               localStorage.setItem('cc_token', j.token); location.hash = '#/teacher'; })
  .catch(e => window.__errs.push('login:' + String(e)));
"""

JS_STATE = """(function(){
  // 实现无关:Dock(header.glass-card)里按文案找「短语」(兼容 a 与 button)
  const dock = document.querySelector('header.glass-card');
  const els = Array.from((dock || document).querySelectorAll('a, button'));
  const a = els.find(e => (e.innerText || '').trim() === '短语');
  if (!a) return {found: false, hash: location.hash,
                  head: document.body ? document.body.innerText.slice(0, 160) : 'no-body'};
  const r = a.getBoundingClientRect();
  const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
  const top = document.elementFromPoint(cx, cy);
  return {found: true, tag: a.tagName, hash: location.hash,
          rect: {x: r.left, y: r.top, w: r.width, h: r.height},
          inViewport: r.top >= 0 && r.bottom <= innerHeight && r.left >= 0 && r.right <= innerWidth,
          hit: top ? {tag: top.tagName, cls: String(top.className), href: top.getAttribute && top.getAttribute('href'),
                      isSelf: top === a, text: (top.innerText || '').slice(0, 24)} : null,
          ua: navigator.userAgent};
})()"""

JS_CLICK = """(function(){
  const dock = document.querySelector('header.glass-card');
  const els = Array.from((dock || document).querySelectorAll('a, button'));
  const a = els.find(e => (e.innerText || '').trim() === '短语');
  if (!a) return {clicked: false};
  const r = a.getBoundingClientRect();
  const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
  const o = {bubbles: true, cancelable: true, view: window, clientX: cx, clientY: cy,
             screenX: cx, screenY: cy, button: 0, buttons: 1};
  a.dispatchEvent(new MouseEvent('mouseover', o));
  a.dispatchEvent(new MouseEvent('mousedown', o));
  a.dispatchEvent(new MouseEvent('mouseup', o));
  a.dispatchEvent(new MouseEvent('click', o));
  return {clicked: true, hashNow: location.hash};
})()"""

JS_AFTER = """({hash: location.hash,
  snippetPage: document.body.innerText.includes('短语管理'),
  res: performance.getEntriesByType('resource')
       .filter(e => e.name.includes('Snippet') || e.name.includes('assets/'))
       .map(e => ({n: e.name.split('/').pop(), ok: e.responseStatus === undefined ? null : e.responseStatus}))})"""


def diag(window):
    try:
        time.sleep(4)                       # 等首页加载
        window.evaluate_js(JS_HOOK_ERRS)
        window.evaluate_js(JS_LOGIN)         # 登录 + 进 teacher
        time.sleep(3)
        result["state"] = window.evaluate_js(JS_STATE)
        result["click"] = window.evaluate_js(JS_CLICK)
        time.sleep(2)                        # 等路由 + 异步 chunk
        result["after"] = window.evaluate_js(JS_AFTER)
        result["errs"] = window.evaluate_js("window.__errs || []")
    except Exception as e:                   # noqa: BLE001 —— 诊断脚本要吞错留痕
        result["exc"] = repr(e)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    window.destroy()


def main():
    window = webview.create_window("B1诊断(自动关闭)", URL, width=900, height=860)
    threading.Thread(target=diag, args=(window,), daemon=True).start()
    # 与生产同配置 private_mode=False:GTK 后端 private 模式会整体禁用
    # HTML5 localStorage(首跑即栽在 "Can't find variable: localStorage")
    webview.start(private_mode=False)
    print(json.dumps(result, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
