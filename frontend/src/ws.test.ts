// ws.ts 重连语义:close() 取消退避定时器、4401 停止重试、重连后自动重订阅。
// jsdom 无 WebSocket,用 FakeWS 桩替换;退避时序用假定时器精确推进。
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { connectWS } from './ws'

class FakeWS {
  static instances: FakeWS[] = []
  static OPEN = 1
  static CONNECTING = 0
  static CLOSING = 2
  static CLOSED = 3
  readyState = FakeWS.CONNECTING
  onopen: (() => void) | null = null
  onmessage: ((ev: { data: string }) => void) | null = null
  onclose: ((ev: { code: number }) => void) | null = null
  sent: string[] = []
  constructor(public url: string) {
    FakeWS.instances.push(this)
  }
  send(data: string) {
    this.sent.push(data)
  }
  close() {
    this.readyState = FakeWS.CLOSED
    this.onclose?.({ code: 1000 })
  }
  // test helpers
  simulateOpen() {
    this.readyState = FakeWS.OPEN
    this.onopen?.()
  }
  simulateClose(code: number) {
    this.readyState = FakeWS.CLOSED
    this.onclose?.({ code })
  }
}

beforeEach(() => {
  vi.useFakeTimers()
  FakeWS.instances = []
  vi.stubGlobal('WebSocket', FakeWS)
  // 本 vitest+jsdom 组合的 window 是 opaque origin,localStorage 不可用;
  // api.ts 的 token.get() 会读它,桩一个空实现(无 token → /ws 不带参数)
  vi.stubGlobal('localStorage', {
    getItem: () => null,
    setItem: () => {},
    removeItem: () => {},
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('ws 重连', () => {
  it('close_during_backoff_does_not_reconnect', () => {
    const handle = connectWS({})
    FakeWS.instances[0].simulateClose(1006) // 排上退避重连
    handle.close() // 落在退避等待窗内
    vi.advanceTimersByTime(15000)
    expect(FakeWS.instances.length).toBe(1)
  })

  it('resubscribes_after_reconnect', () => {
    const onHello = vi.fn()
    connectWS({ classId: 3, onHello })
    const first = FakeWS.instances[0]
    first.simulateOpen()
    first.onmessage?.({ data: '{"type":"hello"}' })
    expect(onHello).toHaveBeenCalled()
    expect(first.sent).toContain('{"type":"subscribe","class_id":3}')
    first.simulateClose(1006)
    vi.advanceTimersByTime(1600) // 首次退避 1000×1.6
    expect(FakeWS.instances.length).toBe(2)
    const second = FakeWS.instances[1]
    second.simulateOpen()
    expect(second.sent).toContain('{"type":"subscribe","class_id":3}')
  })

  it('4401_stops_retrying', () => {
    const onStatus = vi.fn()
    connectWS({ onStatus })
    FakeWS.instances[0].simulateClose(4401) // 契约:token 无效
    expect(onStatus).toHaveBeenCalledWith(false)
    vi.advanceTimersByTime(15000)
    expect(FakeWS.instances.length).toBe(1)
  })

  it('first_retry_between_1s_and_2s', () => {
    // 实际首次退避 = 1000×1.6 = 1600ms:落在 [1s, 2s) 窗口内
    connectWS({})
    FakeWS.instances[0].simulateClose(1006)
    vi.advanceTimersByTime(999)
    expect(FakeWS.instances.length).toBe(1) // <1s 不重连
    vi.advanceTimersByTime(1001) // 共 2s,越过 1600ms
    expect(FakeWS.instances.length).toBe(2)
  })
})
