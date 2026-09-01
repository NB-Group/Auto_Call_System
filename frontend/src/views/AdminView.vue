<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api, token } from '../api'
import Toasts from '../components/Toasts.vue'
import { useToast } from '../composables/useToast'

type Teacher = { id: number; username: string; role: string; display_name: string; office: string; disabled: number }
type Cls = { id: number; name: string; ord: number }

const tab = ref<'teachers' | 'classes' | 'history'>('teachers')
const teachers = ref<Teacher[]>([])
const classes = ref<Cls[]>([])
const history = ref<Awaited<ReturnType<typeof api.admin.history>>['calls']>([])
const { push } = useToast()

const nt = { username: '', password: '', display_name: '', office: '' }
const newTeacher = ref({ ...nt })
const newClass = ref('')
const importText = ref('')
const importTarget = ref<number | null>(null)
const historyDate = ref(new Date().toISOString().slice(0, 10))

async function refresh() {
  if (tab.value === 'teachers') teachers.value = await api.admin.teachers() as any
  else if (tab.value === 'classes') classes.value = await api.classes() as any
  else history.value = (await api.admin.history(historyDate.value)).calls
}
onMounted(async () => {
  if (!token.get()) return location.assign('#/login')
  try { await refresh() } catch { /* 401 已跳转 */ }
})

async function addTeacher() {
  try {
    await api.admin.addTeacher({ ...newTeacher.value })
    newTeacher.value = { ...nt }; push('老师已添加'); await refresh()
  } catch (e: any) { push(`添加失败:${e.message}`) }
}
async function addClass() {
  try {
    await api.admin.addClass(newClass.value.trim())
    newClass.value = ''; push('班级已添加'); await refresh()
  } catch (e: any) { push(`添加失败:${e.message}`) }
}
async function importStudents() {
  if (!importTarget.value) return
  try {
    const r = await api.admin.importStudents(importTarget.value, importText.value)
    importText.value = ''
    push(`导入 ${r.imported} 人${r.skipped.length ? `,跳过 ${r.skipped.join('、')}` : ''}`)
  } catch (e: any) { push(`导入失败:${e.message}`) }
}
// 停/启用与删班提到具名函数:409/400 拒绝时给出 toast,而非静默 unhandled rejection
async function toggleTeacher(t: Teacher) {
  try {
    await api.admin.updateTeacher(t.id, { disabled: t.disabled ? 0 : 1 })
    await refresh()
  } catch (e: any) { push(`操作失败:${e.message}`) }
}
async function removeClass(c: Cls) {
  try {
    await api.admin.delClass(c.id)
    await refresh()
  } catch (e: any) { push(`删除失败:${e.message}`) }
}
</script>

<template>
  <div max-w-980px mx-auto px-6 py-6>
    <header flex="~ items-center justify-between" mb-4>
      <h1 text-20px font-600 m-0>管理后台</h1>
      <div flex gap-2>
        <button v-for="t in (['teachers','classes','history'] as const)" :key="t"
                :class="['cc-btn', { 'cc-btn-primary': tab === t }]" @click="tab = t; refresh()">
          {{ { teachers: '老师', classes: '班级', history: '历史' }[t] }}
        </button>
        <a href="#/login" class="cc-btn" style="text-decoration:none">退出</a>
      </div>
    </header>

    <!-- 老师 -->
    <section v-if="tab === 'teachers'" class="glass-card" p-4 flex="~ col gap-3">
      <div class="glass-card" p-3 flex="~ items-end gap-2" style="background: var(--cc-fill-1)">
        <input v-model="newTeacher.username" class="cc-input" placeholder="用户名">
        <input v-model="newTeacher.password" class="cc-input" type="password" placeholder="密码">
        <input v-model="newTeacher.display_name" class="cc-input" placeholder="称呼(郑老师)">
        <input v-model="newTeacher.office" class="cc-input" placeholder="办公室">
        <button class="cc-btn cc-btn-primary" @click="addTeacher">添加</button>
      </div>
      <div v-for="t in teachers" :key="t.id" flex="~ items-center gap-3" px-2 py-1>
        <b>{{ t.display_name || t.username }}</b>
        <span class="cc-chip" v-if="t.role === 'admin'">管理员</span>
        <span text-13px style="color:var(--cc-text-3)">{{ t.username }} · {{ t.office }}</span>
        <span flex-1 />
        <button v-if="!t.disabled" class="cc-btn" text-13px @click="toggleTeacher(t)">停用</button>
        <button v-else class="cc-btn" text-13px @click="toggleTeacher(t)">启用</button>
      </div>
    </section>

    <!-- 班级 -->
    <section v-else-if="tab === 'classes'" flex="~ col gap-3">
      <div class="glass-card" p-4 flex="~ items-center gap-2">
        <input v-model="newClass" class="cc-input" placeholder="新班级名,如 高二(3)班"
               @keydown.enter="addClass">
        <button class="cc-btn cc-btn-primary" @click="addClass">添加</button>
      </div>
      <div v-for="c in classes" :key="c.id" class="glass-card" p-4 flex="~ col gap-2">
        <div flex="~ items-center gap-3">
          <b text-16px>{{ c.name }}</b>
          <span flex-1 />
          <button class="cc-btn" text-13px @click="removeClass(c)">删除班级</button>
        </div>
        <div flex="~ items-end gap-2">
          <textarea v-model="importText" class="cc-input" flex-1 rows-3
                    placeholder="粘贴学生名单,每行一个(可带学号:梁皓文 0305)" />
          <button class="cc-btn cc-btn-primary" @click="importTarget = c.id; importStudents()">
            导入名单
          </button>
        </div>
      </div>
    </section>

    <!-- 历史 -->
    <section v-else class="glass-card" p-4 flex="~ col gap-1">
      <div flex="~ items-center justify-between" mb-2>
        <input v-model="historyDate" class="cc-input" type="date" @change="refresh">
      </div>
      <div v-for="c in history" :key="c.id" flex="~ items-center gap-3" px-2 py-1 text-14px>
        <span w-64px style="color:var(--cc-text-3)">{{ c.created_at.slice(11, 16) }}</span>
        <b>{{ c.student_name }}</b>
        <span style="color:var(--cc-text-3)">{{ c.class_name }}</span>
        <span class="cc-chip" v-if="c.message">{{ c.message }}</span>
        <span flex-1 />
        <span text-12px style="color:var(--cc-text-3)">{{ c.teacher_name }}</span>
        <span v-if="c.retracted_at" class="cc-chip" style="color:var(--cc-text-4)">已撤销</span>
      </div>
      <div v-if="!history.length" px-2 py-4 text-13px style="color:var(--cc-text-4)">当日无记录</div>
    </section>
    <Toasts />
  </div>
</template>
