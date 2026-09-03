import { describe, expect, it } from 'vitest'
import { initial, planKeydown, reduce } from './palette'
import type { PaletteState } from './palette'

const S = { id: 1, name: '梁皓文', class_name: '高二(3)班', pinyin_initials: 'lhw' }
const S2 = { id: 2, name: '王小雨', class_name: '高二(3)班', pinyin_initials: 'wxy' }
const S3 = { id: 3, name: '陈子昂', class_name: '高二(3)班', pinyin_initials: 'cza' }
const SN = { id: 7, text: '订正数学作业', use_count: 3 }

describe('palette 状态机', () => {
  it('选生:无多选时回车仍单项进入拼装', () => {
    let st = initial
    st = reduce(st, { t: 'type', ch: 'l' }).state
    const { state } = reduce(st, { t: 'enter', students: [S], snippets: [] })
    expect(state.phase).toBe('compose')
    expect(state.students.map(x => x.name)).toEqual(['梁皓文'])
  })

  it('空格多选:加入 picked 保留 query/activeIndex,再按移除', () => {
    let st = initial
    st = reduce(st, { t: 'type', ch: 'l' }).state
    st = reduce(st, { t: 'space', students: [S] }).state
    expect(st.picked.map(p => p.id)).toEqual([1])
    expect(st.query).toBe('l') // 保留 query,老师可继续输入
    expect(st.activeIndex).toBe(0)
    st = reduce(st, { t: 'space', students: [S] }).state
    expect(st.picked).toEqual([]) // toggle 移除
  })

  it('空格多选:跨搜索累积 + 按 id 去重', () => {
    let st = initial
    st = reduce(st, { t: 'space', students: [S] }).state
    st = reduce(st, { t: 'set', query: 'w' }).state // 换搜索词
    st = reduce(st, { t: 'space', students: [S2] }).state
    expect(st.picked.map(p => p.id)).toEqual([1, 2]) // 换词后仍在累积
    // 同一学生换了列表位次再按 → 移除而非重复添加
    st = reduce(st, { t: 'set', query: 'l' }).state
    st = reduce(st, { t: 'down' }).state // activeIndex=1 → students[1] 是 S
    st = reduce(st, { t: 'space', students: [S2, S] }).state
    expect(st.picked.map(p => p.id)).toEqual([2])
  })

  it('空格:选生阶段无结果 / 拼装阶段 → 无操作', () => {
    expect(reduce(initial, { t: 'space', students: [] }).state).toBe(initial)
    const compose: PaletteState = { ...initial, phase: 'compose', students: [S] }
    expect(reduce(compose, { t: 'space', students: [S] }).state).toBe(compose)
  })

  it('unpick:按 id 移除已选', () => {
    let st = reduce(initial, { t: 'space', students: [S] }).state
    st = reduce(st, { t: 'space', students: [S2] }).state
    st = reduce(st, { t: 'unpick', id: 1 }).state
    expect(st.picked.map(p => p.id)).toEqual([2])
  })

  it('多选后回车:带全部 picked 进入拼装(忽略当前高亮)', () => {
    let st = initial
    st = reduce(st, { t: 'space', students: [S] }).state
    st = reduce(st, { t: 'space', students: [S2] }).state
    const { state } = reduce(st, { t: 'enter', students: [S3], snippets: [] })
    expect(state.phase).toBe('compose')
    expect(state.students.map(x => x.id)).toEqual([1, 2]) // S3 只是高亮,不带入
    expect(state.picked).toEqual([]) // picked 清空,防二次进入
  })

  it('拼装:回车挂短语 chip,空 query 回车发送', () => {
    // brief 原稿 `reduce({...}, {})` 传 {} 不在 PaletteEvent 联合内(TS 非法),
    // 按裁定直接以字面量初始化,测试意图不变。
    // (另一处机械修正:as const 会把 st 收窄成 phase:'compose',
    // 回赋 reduce 结果时 TS 报错 —— 显式标注 PaletteState,意图不变)
    let st: PaletteState = { ...initial, phase: 'compose', students: [S] }
    st = reduce(st, { t: 'type', ch: 'd' }).state
    st = reduce(st, { t: 'enter', students: [], snippets: [SN] }).state
    expect(st.chips.map(c => c.text)).toEqual(['订正数学作业'])
    expect(st.query).toBe('')
    const { state, effect } = reduce(st, { t: 'enter', students: [], snippets: [SN] })
    expect(effect).toEqual({ kind: 'send', students: [S], snippetIds: [7], freeText: '' })
    expect(state.phase).toBe('student')
  })

  it('多人发送:send effect 携带全部学生', () => {
    const st: PaletteState = { ...initial, phase: 'compose', students: [S, S2, S3], chips: [SN] }
    const { effect } = reduce(st, { t: 'enter', students: [], snippets: [] })
    expect(effect).toEqual({
      kind: 'send', students: [S, S2, S3], snippetIds: [7], freeText: '',
    })
  })

  it('拼装:无匹配短语时把 query 作为自由文本直接发送', () => {
    const st = { ...initial, phase: 'compose' as const, students: [S], query: '记得带圆规' }
    const { effect } = reduce(st, { t: 'enter', students: [], snippets: [] })
    expect(effect).toEqual({ kind: 'send', students: [S], snippetIds: [], freeText: '记得带圆规' })
  })

  it('Tab 切自由文本,回车带 freeText 发送', () => {
    let st: PaletteState = { ...initial, phase: 'compose', students: [S] }
    st = reduce(st, { t: 'tab' }).state
    st = reduce(st, { t: 'type', ch: '带书' }).state
    const { effect } = reduce(st, { t: 'enter', students: [], snippets: [] })
    expect(effect?.kind === 'send' && effect.freeText === '带书').toBe(true)
  })

  it('空 query 退格:先弹 chip,再逐个退学生,最后退回选生', () => {
    let st: PaletteState = { ...initial, phase: 'compose', students: [S, S2], chips: [SN] }
    st = reduce(st, { t: 'backspace' }).state
    expect(st.chips).toEqual([]) // 1) 弹短语 chip
    expect(st.phase).toBe('compose')
    st = reduce(st, { t: 'backspace' }).state
    expect(st.phase).toBe('compose') // 2) 退最后一名学生,留在拼装
    expect(st.students.map(x => x.id)).toEqual([1])
    st = reduce(st, { t: 'backspace' }).state
    expect(st).toEqual(initial) // 3) 只剩 1 人 → 整体退回选生(picked 清空)
  })

  it('Esc 清空回到选生;sent 重置全部', () => {
    let st: PaletteState = { ...initial, phase: 'compose', students: [S], chips: [SN] }
    st = reduce(st, { t: 'esc' }).state
    expect(st.chips).toEqual([])
    st = reduce(st, { t: 'esc' }).state
    expect(st).toEqual(initial)
    const sent = reduce({ ...initial, phase: 'compose' as const, students: [S] }, { t: 'sent' })
    expect(sent.state).toEqual(initial)
  })

  it('compose 直接回车 = 无附加消息发送(最快路径)', () => {
    const { effect } = reduce({ ...initial, phase: 'compose' as const, students: [S] },
      { t: 'enter', students: [], snippets: [SN] })
    expect(effect).toEqual({ kind: 'send', students: [S], snippetIds: [], freeText: '' })
  })

  it('set 事件绝对覆盖 query(IME compositionend/@input 用),非追加', () => {
    let st = reduce(initial, { t: 'set', query: 'abc' }).state
    expect(st.query).toBe('abc')
    st = reduce(st, { t: 'set', query: 'xy' }).state
    expect(st.query).toBe('xy')
    // set 同时重置高亮,且不触发发送
    st = reduce({ ...st, activeIndex: 3 }, { t: 'set', query: 'xy' }).state
    expect(st.activeIndex).toBe(0)
  })

  it('B3 clear:从任意脏状态一键全清(query/chips/students/picked),回选生阶段', () => {
    const dirty: PaletteState = {
      phase: 'compose', students: [S, S2], chips: [SN], query: 'd',
      freeText: true, activeIndex: 3, picked: [],
    }
    const { state, effect } = reduce(dirty, { t: 'clear' })
    expect(state).toEqual(initial)
    expect(effect).toBeNull()
    // 选生阶段的 query + picked 同样全清
    let st = reduce(initial, { t: 'type', ch: 'l' }).state
    st = reduce(st, { t: 'space', students: [S] }).state
    st = reduce(st, { t: 'clear' }).state
    expect(st).toEqual(initial)
    expect(st.picked).toEqual([])
    expect(st.query).toBe('')
  })

  it('B3 clear 与 esc 语义不同:esc 在拼装阶段先只弹 chips,clear 无条件全清', () => {
    const compose: PaletteState = { ...initial, phase: 'compose', students: [S], chips: [SN] }
    expect(reduce(compose, { t: 'esc' }).state.chips).toEqual([]) // 渐进退出
    expect(reduce(compose, { t: 'esc' }).state.phase).toBe('compose')
    expect(reduce(compose, { t: 'clear' }).state).toEqual(initial) // 一步到位
  })

  it('B3 planKeydown:Ctrl+L 映射 clear,裸 l 放行(不吞输入)', () => {
    expect(planKeydown({ key: 'l', ctrlKey: true })).toEqual({ kind: 'clear' })
    expect(planKeydown({ key: 'L', ctrlKey: true })).toEqual({ kind: 'clear' })
    expect(planKeydown({ key: 'l' })).toBeNull()
    expect(planKeydown({ key: 'l', ctrlKey: false })).toBeNull()
  })

  it('B3 planKeydown:IME 组合期一律放行(含组合期 Ctrl+L)', () => {
    expect(planKeydown({ key: 'Enter', isComposing: true })).toBeNull()
    expect(planKeydown({ key: 'Enter', keyCode: 229 })).toBeNull()
    expect(planKeydown({ key: 'l', ctrlKey: true, isComposing: true })).toBeNull()
  })

  it('B3 planKeydown:其余按键映射不回归(Esc 仍走 esc 语义)', () => {
    expect(planKeydown({ key: 'Escape' })).toEqual({ kind: 'esc' })
    expect(planKeydown({ key: 'ArrowDown' })).toEqual({ kind: 'down' })
    expect(planKeydown({ key: 'ArrowUp' })).toEqual({ kind: 'up' })
    expect(planKeydown({ key: 'Enter' })).toEqual({ kind: 'enter' })
    expect(planKeydown({ key: ' ' })).toEqual({ kind: 'space' })
    expect(planKeydown({ key: 'Tab' })).toEqual({ kind: 'tab' })
    expect(planKeydown({ key: 'Backspace' })).toEqual({ kind: 'backspace' })
    expect(planKeydown({ key: 'x' })).toBeNull()
  })
})
