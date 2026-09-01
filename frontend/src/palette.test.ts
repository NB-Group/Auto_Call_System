import { describe, expect, it } from 'vitest'
import { initial, reduce } from './palette'
import type { PaletteState } from './palette'

const S = { id: 1, name: '梁皓文', class_name: '高二(3)班', pinyin_initials: 'lhw' }
const SN = { id: 7, text: '订正数学作业', use_count: 3 }

describe('palette 状态机', () => {
  it('选生:回车进入拼装', () => {
    let st = initial
    st = reduce(st, { t: 'type', ch: 'l' }).state
    const { state } = reduce(st, { t: 'enter', students: [S], snippets: [] })
    expect(state.phase).toBe('compose')
    expect(state.student?.name).toBe('梁皓文')
  })

  it('拼装:回车挂短语 chip,空 query 回车发送', () => {
    // brief 原稿 `reduce({...}, {})` 传 {} 不在 PaletteEvent 联合内(TS 非法),
    // 按裁定直接以字面量初始化,测试意图不变。
    // (另一处机械修正:as const 会把 st 收窄成 phase:'compose',
    // 回赋 reduce 结果时 TS 报错 —— 显式标注 PaletteState,意图不变)
    let st: PaletteState = { ...initial, phase: 'compose', student: S }
    st = reduce(st, { t: 'type', ch: 'd' }).state
    st = reduce(st, { t: 'enter', students: [], snippets: [SN] }).state
    expect(st.chips.map(c => c.text)).toEqual(['订正数学作业'])
    expect(st.query).toBe('')
    const { state, effect } = reduce(st, { t: 'enter', students: [], snippets: [SN] })
    expect(effect).toEqual({ kind: 'send', student: S, snippetIds: [7], freeText: '' })
    expect(state.phase).toBe('student')
  })

  it('拼装:无匹配短语时把 query 作为自由文本直接发送', () => {
    const st = { ...initial, phase: 'compose' as const, student: S, query: '记得带圆规' }
    const { effect } = reduce(st, { t: 'enter', students: [], snippets: [] })
    expect(effect).toEqual({ kind: 'send', student: S, snippetIds: [], freeText: '记得带圆规' })
  })

  it('Tab 切自由文本,回车带 freeText 发送', () => {
    let st: PaletteState = { ...initial, phase: 'compose', student: S }
    st = reduce(st, { t: 'tab' }).state
    st = reduce(st, { t: 'type', ch: '带书' }).state
    const { effect } = reduce(st, { t: 'enter', students: [], snippets: [] })
    expect(effect?.kind === 'send' && effect.freeText === '带书').toBe(true)
  })

  it('空 query 退格:先弹 chip,再退回选生', () => {
    let st: PaletteState = { ...initial, phase: 'compose', student: S, chips: [SN] }
    st = reduce(st, { t: 'backspace' }).state
    expect(st.chips).toEqual([])
    st = reduce(st, { t: 'backspace' }).state
    expect(st.phase).toBe('student')
  })

  it('Esc 清空回到选生;sent 重置全部', () => {
    let st: PaletteState = { ...initial, phase: 'compose', student: S, chips: [SN] }
    st = reduce(st, { t: 'esc' }).state
    expect(st.chips).toEqual([])
    st = reduce(st, { t: 'esc' }).state
    expect(st).toEqual(initial)
    const sent = reduce({ ...initial, phase: 'compose' as const, student: S }, { t: 'sent' })
    expect(sent.state).toEqual(initial)
  })

  it('compose 直接回车 = 无附加消息发送(最快路径)', () => {
    const { effect } = reduce({ ...initial, phase: 'compose' as const, student: S },
      { t: 'enter', students: [], snippets: [SN] })
    expect(effect).toEqual({ kind: 'send', student: S, snippetIds: [], freeText: '' })
  })

  it('set 事件绝对覆盖 query(IME compositionend/@input 用),非追加', () => {
    let st: PaletteState = reduce(initial, { t: 'set', query: 'abc' }).state
    expect(st.query).toBe('abc')
    st = reduce(st, { t: 'set', query: 'xy' }).state
    expect(st.query).toBe('xy')
    // set 同时重置高亮,且不触发发送
    st = reduce({ ...st, activeIndex: 3 }, { t: 'set', query: 'xy' }).state
    expect(st.activeIndex).toBe(0)
  })
})
