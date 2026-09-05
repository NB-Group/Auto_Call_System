import { describe, expect, it } from 'vitest'
import { initial, planKeydown, reduce } from './palette'
import type { PaletteState } from './palette'
import type { Snippet } from './api'

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
    expect(st.query).toBe('d') // 2026-09-05:挂载后现场保留(query 不清)
    // 挂载过的短语上再回车 = 发送确认(不再哑火)
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

  it('B3 clear:只清输入框(query),保留已选学生/短语/阶段(用户流程:连着叫下一批)', () => {
    const dirty: PaletteState = {
      phase: 'compose', students: [S, S2], chips: [SN], query: 'd',
      freeText: true, activeIndex: 3, picked: [],
    }
    const { state, effect } = reduce(dirty, { t: 'clear' })
    expect(state).toEqual({ ...dirty, query: '', activeIndex: 0 }) // 其余原样
    expect(effect).toBeNull()
    // 选生阶段:query 清空,picked 留住接着选下一人
    let st = reduce(initial, { t: 'type', ch: 'l' }).state
    st = reduce(st, { t: 'space', students: [S] }).state
    st = reduce(st, { t: 'clear' }).state
    expect(st.query).toBe('')
    expect(st.picked).toEqual([S])
    expect(st.phase).toBe('student')
  })

  it('B3 clear 与 esc 语义不同:esc 才是无条件全清(fresh start)', () => {
    const compose: PaletteState = { ...initial, phase: 'compose', students: [S], chips: [SN] }
    let once = reduce(compose, { t: 'esc' }).state
    expect(once.chips).toEqual([])          // 渐进:第一下只弹短语
    expect(once.phase).toBe('compose')      // 仍在拼装,学生留着
    expect(reduce(once, { t: 'esc' }).state).toEqual(initial) // 第二下才 fresh start
    expect(reduce(compose, { t: 'clear' }).state.students).toEqual([S]) // clear 不动结构
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

// ===== 2026-09-05 用户反馈:短语输入与姓名输入同肌肉记忆(空格挂载) =====
describe('compose 阶段空格挂短语', () => {
  const compose = { ...initial, phase: 'compose' as const, students: [S] }

  it('空格 = 挂高亮短语 chip,现场不动(query/高亮保留,同选生肌肉记忆)', () => {
    const st = reduce({ ...compose, query: 'dz', activeIndex: 1 }, { t: 'space', students: [], snippets: [SN] }).state
    expect(st.chips).toEqual([SN])
    expect(st.query).toBe('dz')
    expect(st.activeIndex).toBe(1)
  })

  it('重复挂载去重:同短语再空格状态不变', () => {
    const st = reduce({ ...compose, query: 'dz', chips: [SN] },
      { t: 'space', students: [], snippets: [SN] }).state
    expect(st.chips).toEqual([SN])
  })

  it('无匹配短语时空格不动(不误清、不误发;发送仍走回车)', () => {
    const st = { ...compose, query: 'zzz' }
    expect(reduce(st, { t: 'space', students: [], snippets: [] }).state).toEqual(st)
  })

  it('连挂两条:dz 空格 → 敲第二条空格,chips 依序累积', () => {
    const SN2: Snippet = { id: 9, text: '带上练习册', use_count: 0 }
    let st = reduce({ ...compose, query: 'dz' }, { t: 'space', students: [], snippets: [SN] }).state
    st = reduce({ ...st, query: 'lx' }, { t: 'space', students: [], snippets: [SN2] }).state
    expect(st.chips.map(c => c.text)).toEqual([SN.text, SN2.text])
  })
})
