import { describe, expect, it } from 'vitest'
import {
  autoCollapse,
  initDisplayMode,
  onGroupCall,
  onGroupsEmpty,
  toggleManual,
} from './displayMode'

describe('displayMode 显示端小窗形态(Task-23)', () => {
  it('初始:小窗、非手动、无计时锚点', () => {
    const s = initDisplayMode()
    expect(s).toEqual({ expanded: false, manual: false, lastGroupClosedAt: null })
  })

  it('来号自动展开:首组 expand + 清手动位', () => {
    let s = initDisplayMode()
    s = toggleManual(s) // 先手动展开,再验证来号会清手动位
    expect(s.manual).toBe(true)
    s = onGroupCall(s)
    expect(s.expanded).toBe(true)
    expect(s.manual).toBe(false)
    expect(s.lastGroupClosedAt).toBeNull()
  })

  it('组清空后 12s 自动收起:边界内不收,过界即收', () => {
    let s = onGroupCall(initDisplayMode())
    s = onGroupsEmpty(s, 1000)
    expect(s.expanded).toBe(true) // 清空瞬间仍展开
    expect(autoCollapse(s, 1000 + 12000).expanded).toBe(true) // 恰好 12s:不收(> 才收)
    expect(autoCollapse(s, 1000 + 12001).expanded).toBe(false) // 过 1ms 收回小窗
  })

  it('手动全屏抑制自动收起;手动收起解除抑制', () => {
    let s = onGroupCall(initDisplayMode())
    s = onGroupsEmpty(s, 0)
    s = { ...s, manual: true } // 展开态手动置位
    expect(autoCollapse(s, 99999).expanded).toBe(true) // 永不自动收
    s = toggleManual(s) // 手动收起 → manual 清零
    expect(s.expanded).toBe(false)
    expect(s.manual).toBe(false)
  })

  it('冷却期内来新组:计时锚点重置,从头再数 12s', () => {
    let s = onGroupCall(initDisplayMode())
    s = onGroupsEmpty(s, 0)
    s = onGroupCall(s) // 5s 处来了新组:取消本次收起
    s = onGroupsEmpty(s, 5000)
    expect(autoCollapse(s, 5000 + 12000).expanded).toBe(true) // 旧锚点(0)早已过界,不得误收
    expect(autoCollapse(s, 5000 + 12001).expanded).toBe(false) // 新锚点过界才收
  })

  it('从未有过组(页面刚启动)不触发收起', () => {
    const s = initDisplayMode()
    expect(autoCollapse(s, 99999)).toBe(s) // 原样返回,不产新状态
  })

  it('manual toggle 翻转:小窗 → 全屏+manual;全屏 → 小窗+非manual', () => {
    const idle = initDisplayMode()
    const up = toggleManual(idle)
    expect(up).toEqual({ ...idle, expanded: true, manual: true })
    const down = toggleManual(up)
    expect(down).toEqual({ ...up, expanded: false, manual: false })
  })
})
