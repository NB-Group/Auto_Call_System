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
  | { t: 'space'; students: StudentHit[] }
  | { t: 'unpick'; id: number }
  | { t: 'enter'; students: StudentHit[]; snippets: Snippet[] }
  | { t: 'tab' }
  | { t: 'esc' }
  | { t: 'sent' }

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
      return onSpace(s, e.students)
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
  }
}

// 空格:把当前高亮的学生加入/移出 picked(dedupe by id)。
// 保留 query 与 activeIndex —— 老师可以继续输入拼音缩小范围接着选。
function onSpace(
  s: PaletteState,
  students: StudentHit[],
): { state: PaletteState; effect: null } {
  if (s.phase !== 'student' || !students.length) return { state: s, effect: null }
  const hit = students[Math.min(s.activeIndex, students.length - 1)]
  const has = s.picked.some(p => p.id === hit.id)
  return {
    state: { ...s, picked: has ? s.picked.filter(p => p.id !== hit.id) : [...s.picked, hit] },
    effect: null,
  }
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
