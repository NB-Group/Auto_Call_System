// 老师端命令面板纯状态机:选生 → 拼装(chip/自由文本) → 发送。
import type { Snippet, StudentHit } from './api'

export interface PaletteState {
  phase: 'student' | 'compose'
  query: string
  student: StudentHit | null
  chips: Snippet[]
  freeText: boolean
  activeIndex: number
}

export type SendEffect = {
  kind: 'send'
  student: StudentHit
  snippetIds: number[]
  freeText: string
}

export type PaletteEvent =
  | { t: 'type'; ch: string }
  | { t: 'set'; query: string }
  | { t: 'backspace' }
  | { t: 'up' }
  | { t: 'down' }
  | { t: 'enter'; students: StudentHit[]; snippets: Snippet[] }
  | { t: 'tab' }
  | { t: 'esc' }
  | { t: 'sent' }

export const initial: PaletteState = {
  phase: 'student', query: '', student: null, chips: [],
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
        if (s.chips.length)
          return { state: { ...s, chips: s.chips.slice(0, -1) }, effect: null }
        return { state: { ...initial }, effect: null }
      }
      return { state: s, effect: null }
    case 'up':
      return { state: { ...s, activeIndex: Math.max(0, s.activeIndex - 1) }, effect: null }
    case 'down':
      return { state: { ...s, activeIndex: s.activeIndex + 1 }, effect: null }
    case 'enter':
      return onEnter(s, e)
    case 'tab':
      if (s.phase === 'compose')
        return { state: { ...s, freeText: !s.freeText, query: '', activeIndex: 0 }, effect: null }
      return { state: s, effect: null }
    case 'esc':
      if (s.phase === 'compose' && s.chips.length)
        return { state: { ...s, chips: [] }, effect: null }
      return { state: { ...initial }, effect: null }
    case 'sent':
      return { state: { ...initial }, effect: null }
  }
}

function onEnter(
  s: PaletteState,
  e: Extract<PaletteEvent, { t: 'enter' }>,
): { state: PaletteState; effect: SendEffect | null } {
  if (s.phase === 'student') {
    if (!e.students.length) return { state: s, effect: null }
    const student = e.students[Math.min(s.activeIndex, e.students.length - 1)]
    return {
      state: { phase: 'compose', query: '', student, chips: [], freeText: false, activeIndex: 0 },
      effect: null,
    }
  }
  if (!s.student) return { state: initial, effect: null }

  if (s.freeText) {
    return {
      state: { ...initial },
      effect: {
        kind: 'send', student: s.student,
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
        kind: 'send', student: s.student,
        snippetIds: s.chips.map(c => c.id), freeText: s.query.trim(),
      },
    }
  }
  return {
    state: { ...initial },
    effect: {
      kind: 'send', student: s.student,
      snippetIds: s.chips.map(c => c.id), freeText: '',
    },
  }
}
