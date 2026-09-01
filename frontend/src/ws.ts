// 显示端 WS:自动重连(指数退避,上限 10s)+ 重连后自动重订阅。
import type { CallItem } from './api'
import { token } from './api'

export interface WSHandlers {
  classId?: number
  onCall?: (call: CallItem) => void
  onRetract?: (callId: number) => void
  onHello?: () => void
  onStatus?: (online: boolean) => void
}

export function connectWS(h: WSHandlers) {
  let closed = false
  let ws: WebSocket | null = null
  let delay = 1000

  function open() {
    const t = token.get()
    const url = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws${t ? `?token=${t}` : ''}`
    ws = new WebSocket(url)
    ws.onopen = () => {
      delay = 1000
      if (h.classId !== undefined)
        ws?.send(JSON.stringify({ type: 'subscribe', class_id: h.classId }))
      h.onStatus?.(true)
    }
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data)
      if (msg.type === 'hello') h.onHello?.()
      else if (msg.type === 'call') h.onCall?.(msg.call as CallItem)
      else if (msg.type === 'retract') h.onRetract?.(msg.call_id)
    }
    ws.onclose = () => {
      h.onStatus?.(false)
      if (!closed) setTimeout(open, delay = Math.min(delay * 1.6, 10000))
    }
  }
  open()

  return {
    subscribe(classId: number) {
      h.classId = classId
      if (ws?.readyState === WebSocket.OPEN)
        ws.send(JSON.stringify({ type: 'subscribe', class_id: classId }))
    },
    close() { closed = true; ws?.close() },
  }
}
