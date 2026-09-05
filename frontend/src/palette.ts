// 老师端命令面板纯状态机:多选学生(space/点击) → 拼装(chip/自由文本) → 发送。
import type { Snippet, StudentHit } from './api'

export interface PaletteState {
  phase: 'student' | 'compose'
  query: string
  /** 学生阶段已多选的学生(空格/点击累积,dedupe by id) */
  picked: StudentHit[]
  /** 拼装阶段的全部目标学生(由 picked 或单项选择转入) */
  students: StudentHit[]
  chips: Snippet[]
  freeText: boolean
  activeIndex: number
}

export type SendEffect = {
  kind: 'send'
  students: StudentHit[]
  snippetIds: number[]
  freeText: string
}

export type PaletteEvent =
  | { t: 'type'; ch: string }
  | { t: 'set'; query: string }
  | { t: 'backspace' }
  | { t: 'up' }
  | { t: 'down' }
  | { t: 'space'; students: StudentHit[]; snippets?: Snippet[] }
  | { t: 'unpick'; id: number }
  | { t: 'enter'; students: StudentHit[]; snippets: Snippet[] }
  | { t: 'tab' }
  | { t: 'esc' }
  | { t: 'sent' }
  | { t: 'clear' }

export const initial: PaletteState = {
  phase: 'student', query: '', picked: [], students: [], chips: [],
  freeText: false, activeIndex: 0,
}

export function reduce(
  s: PaletteState,
  e: PaletteEvent,
): { state: PaletteState; effect: SendEffect | null } {
  switch (e.t) {
    case 'type':
      return { state: { ...s, query: s.query + e.ch, activeIndex: 0 }, effect: null }
    // IME/输入框绝对设置:输入法 compositionend 或 @input 直接以输入框当前值覆盖 query
    case 'set':
      return { state: { ...s, query: e.query, activeIndex: 0 }, effect: null }
    case 'backspace':
      if (s.query) return { state: { ...s, query: s.query.slice(0, -1) }, effect: null }
      if (s.phase === 'compose') {
        // 先弹最后一个短语 chip;然后逐个退学生;只剩 1 人时整体退回选生阶段
        if (s.chips.length)
          return { state: { ...s, chips: s.chips.slice(0, -1) }, effect: null }
        if (s.students.length > 1)
          return { state: { ...s, students: s.students.slice(0, -1) }, effect: null }
        return { state: { ...initial }, effect: null }
      }
      return { state: s, effect: null }
    case 'up':
      return { state: { ...s, activeIndex: Math.max(0, s.activeIndex - 1) }, effect: null }
    case 'down':
      return { state: { ...s, activeIndex: s.activeIndex + 1 }, effect: null }
    case 'space':
      return onSpace(s, e.students, e.snippets)
    case 'unpick':
      return { state: { ...s, picked: s.picked.filter(p => p.id !== e.id) }, effect: null }
    case 'enter':
      return onEnter(s, e)
    case 'tab':
      if (s.phase === 'compose')
        return { state: { ...s, freeText: !s.freeText, query: '', activeIndex: 0 }, effect: null }
      return { state: s, effect: null }
    case 'esc':
      // 拼装阶段:先清短语;再退回选生且清掉已选(fresh start)
      if (s.phase === 'compose' && s.chips.length)
        return { state: { ...s, chips: [] }, effect: null }
      return { state: { ...initial }, effect: null }
    case 'sent':
      return { state: { ...initial }, effect: null }
    // B3 清空输入(Ctrl+L):只清 query(拼音/自由文本),保留已选学生、
    // 短语与阶段 —— 用户流程是连着叫下一批:敲 lhw→空格选人→Ctrl+L 清
    // 掉→敲下一人。无条件全清是 esc 的活(fresh start)。
    case 'clear':
      return { state: { ...s, query: '', activeIndex: 0 }, effect: null }
  }
}

// 空格:与选生同肌肉记忆(2026-09-05 用户实测反馈)——
// 选生阶段:高亮学生加入/移出 picked(dedupe by id),保留 query 继续
// 输拼音缩小范围;拼装阶段:高亮短语挂为 chip(去重),清 query 备敲
// 下一个短语;无匹配时不动(发送仍走回车,防止误发)。
function onSpace(
  s: PaletteState,
  students: StudentHit[],
  snippets: Snippet[] = [],
): { state: PaletteState; effect: null } {
  if (s.phase === 'student') {
    if (!students.length) return { state: s, effect: null }
    const hit = students[Math.min(s.activeIndex, students.length - 1)]
    const has = s.picked.some(p => p.id === hit.id)
    return {
      state: { ...s, picked: has ? s.picked.filter(p => p.id !== hit.id) : [...s.picked, hit] },
      effect: null,
    }
  }
  const snip = snippets[Math.min(s.activeIndex, snippets.length - 1)]
  if (!snip) return { state: s, effect: null }
  if (s.chips.some(c => c.id === snip.id))
    return { state: { ...s, query: '', activeIndex: 0 }, effect: null }
  return { state: { ...s, chips: [...s.chips, snip], query: '', activeIndex: 0 }, effect: null }
}

function onEnter(
  s: PaletteState,
  e: Extract<PaletteEvent, { t: 'enter' }>,
): { state: PaletteState; effect: SendEffect | null } {
  if (s.phase === 'student') {
    if (s.picked.length)
      return {
        state: { phase: 'compose', query: '', picked: [], students: [...s.picked], chips: [], freeText: false, activeIndex: 0 },
        effect: null,
      }
    if (!e.students.length) return { state: s, effect: null }
    const student = e.students[Math.min(s.activeIndex, e.students.length - 1)]
    return {
      state: { phase: 'compose', query: '', picked: [], students: [student], chips: [], freeText: false, activeIndex: 0 },
      effect: null,
    }
  }
  if (!s.students.length) return { state: { ...initial }, effect: null }

  if (s.freeText) {
    return {
      state: { ...initial },
      effect: {
        kind: 'send', students: s.students,
        snippetIds: s.chips.map(c => c.id), freeText: s.query.trim(),
      },
    }
  }
  if (s.query) {
    if (e.snippets.length) {
      const snip = e.snippets[Math.min(s.activeIndex, e.snippets.length - 1)]
      if (s.chips.some(c => c.id === snip.id))
        return { state: { ...s, query: '' }, effect: null }
      return { state: { ...s, chips: [...s.chips, snip], query: '', activeIndex: 0 }, effect: null }
    }
    return {
      state: { ...initial },
      effect: {
        kind: 'send', students: s.students,
        snippetIds: s.chips.map(c => c.id), freeText: s.query.trim(),
      },
    }
  }
  return {
    state: { ...initial },
    effect: {
      kind: 'send', students: s.students,
      snippetIds: s.chips.map(c => c.id), freeText: '',
    },
  }
}

// keydown → 面板动作的纯映射(Palette.vue 用,单测直接打这里)。
// null = 不认(含 IME 组合期),原样放行给输入框/输入法。
// Ctrl+L 必须排在其余分支之前判定:裸 'l' 是要进 query 的输入字符,
// 唯一区分是 ctrlKey —— guard 顺序错了 'l' 就会被当输入或反过来误清空。
export type KeyPlanKind =
  | 'clear' | 'down' | 'up' | 'enter' | 'space' | 'tab' | 'esc' | 'backspace'

export function planKeydown(ev: {
  key: string
  ctrlKey?: boolean
  isComposing?: boolean
  keyCode?: number
}): { kind: KeyPlanKind } | null {
  if (ev.isComposing || ev.keyCode === 229) return null
  if (ev.ctrlKey && (ev.key === 'l' || ev.key === 'L')) return { kind: 'clear' }
  switch (ev.key) {
    case 'ArrowDown': return { kind: 'down' }
    case 'ArrowUp': return { kind: 'up' }
    case 'Enter': return { kind: 'enter' }
    case ' ': return { kind: 'space' }
    case 'Tab': return { kind: 'tab' }
    case 'Escape': return { kind: 'esc' }
    case 'Backspace': return { kind: 'backspace' }
  }
  return null
}
