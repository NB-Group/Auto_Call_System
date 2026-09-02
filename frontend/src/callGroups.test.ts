import { describe, expect, it } from 'vitest'
import { closeExpired, initGroups, onCall, onRetract } from './callGroups'
import type { CallItem } from './api'

let nid = 1
const C = (over: Partial<CallItem> = {}): CallItem => ({
  id: nid++, student_id: 1, class_id: 1, teacher_id: 1,
  message: '订正数学作业', announce: '', created_at: '2026-09-01 09:00:00',
  student_name: '梁皓文', class_name: '高二(3)班',
  teacher_name: '郑老师', office: '203办公室',
  ...over,
})

describe('callGroups 显示端突发聚合', () => {
  it('突发 N 条同师同消息 → 聚成一组', () => {
    let s = initGroups()
    s = onCall(s, C({ student_name: '甲' }), 0)
    s = onCall(s, C({ student_name: '乙' }), 300)
    s = onCall(s, C({ student_name: '丙' }), 900)
    expect(s.groups.length).toBe(1)
    expect(s.groups[0].calls.map(c => c.student_name)).toEqual(['甲', '乙', '丙'])
    expect(s.groups[0].closed).toBe(false)
  })

  it('跨老师不并组:后来者成为当前组', () => {
    let s = initGroups()
    s = onCall(s, C({ teacher_name: '郑老师' }), 0)
    s = onCall(s, C({ teacher_name: '李老师' }), 300)
    expect(s.groups.length).toBe(2)
    expect(s.groups[0].calls[0].teacher_name).toBe('李老师') // 最新 = hero
  })

  it('跨办公室 / 跨消息不并组', () => {
    let s = initGroups()
    s = onCall(s, C({ office: '203办公室' }), 0)
    s = onCall(s, C({ office: '305办公室' }), 100)
    expect(s.groups.length).toBe(2)
    s = onCall(s, C({ message: '带圆规' }), 200)
    expect(s.groups.length).toBe(3)
  })

  it('超窗(>1.2s)不并组', () => {
    let s = initGroups()
    s = onCall(s, C(), 0)
    s = onCall(s, C({ student_name: '乙' }), 1201)
    expect(s.groups.length).toBe(2)
  })

  it('窗口边界内(≤1.2s)仍并组', () => {
    let s = initGroups()
    s = onCall(s, C(), 0)
    s = onCall(s, C({ student_name: '乙' }), 1200)
    expect(s.groups.length).toBe(1)
  })

  it('追加到旧组时,该组提为当前组', () => {
    let s = initGroups()
    s = onCall(s, C({ teacher_name: '郑老师' }), 0)
    s = onCall(s, C({ teacher_name: '李老师' }), 600) // 开新组置顶
    s = onCall(s, C({ teacher_name: '郑老师', student_name: '乙' }), 1100) // 郑组仍在窗内
    expect(s.groups[0].calls[0].teacher_name).toBe('郑老师')
    expect(s.groups[0].calls.length).toBe(2)
    expect(s.groups.length).toBe(2)
  })

  it('历史组栈上限:当前 + 2 个旧组', () => {
    let s = initGroups()
    s = onCall(s, C({ teacher_name: 'A' }), 0)
    s = onCall(s, C({ teacher_name: 'B' }), 2000)
    s = onCall(s, C({ teacher_name: 'C' }), 4000)
    s = onCall(s, C({ teacher_name: 'D' }), 6000)
    expect(s.groups.length).toBe(3)
    expect(s.groups.map(g => g.calls[0].teacher_name)).toEqual(['D', 'C', 'B'])
  })

  it('retract:从所在组移除,组空整组消失', () => {
    let s = initGroups()
    const a = C({ student_name: '甲' })
    const b = C({ student_name: '乙' })
    const c = C({ teacher_name: '李老师', student_name: '丙' })
    s = onCall(s, a, 0)
    s = onCall(s, b, 100)
    s = onCall(s, c, 2000)
    s = onRetract(s, a.id)
    expect(s.groups.length).toBe(2)
    expect(s.groups[1].calls.map(x => x.student_name)).toEqual(['乙'])
    s = onRetract(s, b.id)
    expect(s.groups.length).toBe(1) // 空组消失
    expect(s.groups[0].calls[0].student_name).toBe('丙')
  })

  it('closeExpired 置 closed;显式关组后即使未超窗也不并组', () => {
    let s = initGroups()
    s = onCall(s, C(), 0)
    s = closeExpired(s, 1300)
    expect(s.groups[0].closed).toBe(true)
    s = onCall(s, C({ student_name: '乙' }), 1300) // closed 旗标拦截
    expect(s.groups.length).toBe(2)
  })
})
