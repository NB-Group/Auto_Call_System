// 显示端形态决策(纯状态机,Task-23):右下角小窗常驻,
// 来号自动展开全屏(hero+TTS),末组结束 12s 后自动收回小窗;
// 手动按钮翻转 manualFS 后抑制自动收回(来号仍会保持全屏��清手动位)。
export const COLLAPSE_DELAY_MS = 12000

export interface DisplayModeState {
  /** 当前是否处于全屏(展开)形态 */
  expanded: boolean
  /** 用户手动全屏置位:抑制自动收起 */
  manual: boolean
  /** 组栈最近一次清空的时间戳(ms);组非空时为 null */
  lastGroupClosedAt: number | null
}

export const initDisplayMode = (): DisplayModeState =>
  ({ expanded: false, manual: false, lastGroupClosedAt: null })

/** 来号(组 0→非空,或倒计时中来了新组):展开 + 清手动位 + 重置计时锚点 */
export function onGroupCall(s: DisplayModeState): DisplayModeState {
  return { expanded: true, manual: false, lastGroupClosedAt: null }
}

/** 组栈清空:记录时间戳供 autoCollapse 判定(形态不动) */
export function onGroupsEmpty(s: DisplayModeState, now: number): DisplayModeState {
  return { ...s, lastGroupClosedAt: now }
}

/**
 * 空组冷却期判定:距末组清空 > delayMs → 收回小窗。
 * 手动全屏(manual)或未展开时不动;从未有过组(lastGroupClosedAt=null,
 * 即页面刚启动)也不动。幂等:已收起时原样返回。
 */
export function autoCollapse(
  s: DisplayModeState,
  now: number,
  delayMs = COLLAPSE_DELAY_MS,
): DisplayModeState {
  if (!s.expanded || s.manual || s.lastGroupClosedAt === null) return s
  if (now - s.lastGroupClosedAt <= delayMs) return s
  return { ...s, expanded: false }
}

/** 手动切换:展开 → manual=true(抑制自动收起);收起 → manual=false */
export function toggleManual(s: DisplayModeState): DisplayModeState {
  return { ...s, expanded: !s.expanded, manual: !s.expanded }
}
