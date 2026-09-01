// CONTRACTS 的唯一前端 HTTP 绑定层。token 持久化在 localStorage。
const TOKEN_KEY = 'cc_token'

export interface CallItem {
  id: number; student_id: number; class_id: number; teacher_id: number
  message: string; announce: string; created_at: string
  student_name: string; class_name: string; teacher_name: string
  office: string; retracted_at?: string | null
}
export interface StudentHit { id: number; name: string; class_name: string; pinyin_initials: string }
export interface Snippet { id: number; text: string; use_count: number }
export interface MeInfo { id: number; username: string; role: string; display_name: string; office: string; default_template: string }

export const token = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t: string) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
}

async function j<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token.get() ? { Authorization: `Bearer ${token.get()}` } : {}),
      ...init?.headers,
    },
  })
  if (r.status === 401 && location.hash !== '#/login') {
    token.clear(); location.hash = '#/login'
    throw new Error('unauthorized')
  }
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || `http ${r.status}`)
  return r.status === 204 ? (undefined as T) : r.json()
}

export const api = {
  login: (username: string, password: string) =>
    j<{ token: string; role: string; display_name: string; office: string }>(
      '/api/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  logout: () => j<{ ok: boolean }>('/api/auth/logout', { method: 'POST' }),
  me: () => j<MeInfo>('/api/me'),
  updateMe: (patch: Partial<Pick<MeInfo, 'display_name' | 'office' | 'default_template'>>) =>
    j<MeInfo>('/api/me', { method: 'PUT', body: JSON.stringify(patch) }),
  bootstrapStatus: () => j<{ needs_admin: boolean; version: string }>('/api/bootstrap/status'),
  bootstrapAdmin: (username: string, password: string, display_name?: string) =>
    j<{ token: string; role: string }>('/api/bootstrap/admin',
      { method: 'POST', body: JSON.stringify({ username, password, display_name }) }),
  classes: () => j<{ id: number; name: string; ord: number }[]>('/api/classes'),
  searchStudents: (q: string, limit = 8) =>
    j<StudentHit[]>(`/api/students/search?q=${encodeURIComponent(q)}&limit=${limit}`),
  searchSnippets: (q: string, limit = 6) =>
    j<Snippet[]>(`/api/snippets/search?q=${encodeURIComponent(q)}&limit=${limit}`),
  call: (student_id: number, snippet_ids: number[], free_text: string) =>
    j<{ call: CallItem }>('/api/calls',
      { method: 'POST', body: JSON.stringify({ student_id, snippet_ids, free_text }) }),
  undo: (id: number) => j<{ ok: boolean }>(`/api/calls/${id}`, { method: 'DELETE' }),
  today: () => j<{ calls: CallItem[] }>('/api/calls/today'),
  snippets: () => j<Snippet[]>('/api/snippets'),
  // 契约:POST /api/snippets → 201 增后全表(同 GET 形状),非 {ok}(Task 5-review 修正)
  addSnippet: (text: string) => j<Snippet[]>('/api/snippets',
    { method: 'POST', body: JSON.stringify({ text }) }),
  delSnippet: (id: number) => j<{ ok: boolean }>(`/api/snippets/${id}`, { method: 'DELETE' }),
  admin: {
    teachers: () => j<any[]>('/api/admin/teachers'),
    addTeacher: (t: any) => j<{ id: number }>('/api/admin/teachers',
      { method: 'POST', body: JSON.stringify(t) }),
    updateTeacher: (id: number, patch: any) => j<{ ok: boolean }>(`/api/admin/teachers/${id}`,
      { method: 'PUT', body: JSON.stringify(patch) }),
    delTeacher: (id: number) => j<{ ok: boolean }>(`/api/admin/teachers/${id}`, { method: 'DELETE' }),
    addClass: (name: string, ord = 0) => j<{ id: number; name: string; ord: number }>(
      '/api/admin/classes', { method: 'POST', body: JSON.stringify({ name, ord }) }),
    delClass: (id: number) => j<{ ok: boolean }>(`/api/admin/classes/${id}`, { method: 'DELETE' }),
    importStudents: (classId: number, text: string) =>
      j<{ imported: number; skipped: string[] }>(`/api/admin/classes/${classId}/students`,
        { method: 'POST', body: JSON.stringify({ text }) }),
    history: (date?: string) => j<{ calls: CallItem[] }>(
      `/api/admin/calls${date ? `?date=${date}` : ''}`),
    serverInfo: () => j<{ version: string; displays: number }>('/api/server/info'),
  },
}
