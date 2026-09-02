// 显示端"突发聚合"纯状态机:多人叫号时前端循环 N 次 api.call,服务端连发 N 条
// call 广播 —— 大屏按「同老师+同办公室+同消息、1.2s 窗口内」聚成一卡同屏显示。
import type { CallItem } from './api'

export const GROUP_WINDOW_MS = 1200
/** 当前组 + 最多 2 个历史组 */
export const GROUP_STACK_MAX = 3

export interface CallGroup {
  id: number
  calls: CallItem[]
  openedAt: number
  /** 窗口到期(setTimeout 兜底)后置位:不再接受追加;时间检查本身也会拦 */
  closed: boolean
}

export interface GroupsState {
  /** groups[0] = 当前 hero 组;[1]/[2] = 缩小形态的历史组 */
  groups: CallGroup[]
  seq: number
}

export const initGroups = (): GroupsState => ({ groups: [], seq: 1 })

const sameTarget = (g: CallGroup, c: CallItem) =>
  g.calls[0].teacher_name === c.teacher_name
  && g.calls[0].office === c.office
  && g.calls[0].message === c.message

const open = (g: CallGroup, now: number, windowMs: number) =>
  !g.closed && now - g.openedAt <= windowMs

/**
 * 收到一条叫号:
 * - 存在「未关组 且 未超窗 且 老师/办公室/消息相同」的组 → 追加并把该组提到最前
 *   (它刚收到最新呼叫,理应成为当前展示组);
 * - 否则开新组置顶,栈深截到 GROUP_STACK_MAX。
 */
export function onCall(
  s: GroupsState,
  call: CallItem,
  now: number,
  windowMs = GROUP_WINDOW_MS,
): GroupsState {
  const hit = s.groups.findIndex(g => open(g, now, windowMs) && sameTarget(g, call))
  if (hit >= 0) {
    const groups = s.groups.map((g, i) =>
      i === hit ? { ...g, calls: [...g.calls, call] } : g)
    const [moved] = groups.splice(hit, 1)
    return { ...s, groups: [moved, ...groups] }
  }
  const fresh: CallGroup = { id: s.seq, calls: [call], openedAt: now, closed: false }
  return { groups: [fresh, ...s.groups].slice(0, GROUP_STACK_MAX), seq: s.seq + 1 }
}

/** 撤销:从所在组移除该叫号;组空了整组消失(FLIP 由视图层接管) */
export function onRetract(s: GroupsState, id: number): GroupsState {
  const groups = s.groups
    .map(g => ({ ...g, calls: g.calls.filter(c => c.id !== id) }))
    .filter(g => g.calls.length > 0)
  return { ...s, groups }
}

/** setTimeout 兜底:把所有超窗组显式置 closed(时间检查已拦,这只是清旗) */
export function closeExpired(
  s: GroupsState,
  now: number,
  windowMs = GROUP_WINDOW_MS,
): GroupsState {
  return {
    ...s,
    groups: s.groups.map(g => (g.closed || now - g.openedAt > windowMs ? { ...g, closed: true } : g)),
  }
}
