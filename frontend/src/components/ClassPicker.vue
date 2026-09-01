<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'

const emit = defineEmits<{ picked: [classId: number, className: string] }>()
const classes = ref<{ id: number; name: string }[]>([])
onMounted(async () => { classes.value = await api.classes() })
</script>

<template>
  <div h-full flex="~ col items-center justify-center" gap-6>
    <h1 text-28px font-600 m-0>本教室是哪个班?</h1>
    <div grid="~ cols-3 gap-3" w-560px>
      <button v-for="c in classes" :key="c.id" class="glass-card" p-6 text-18px
              style="cursor:pointer" @click="emit('picked', c.id, c.name)">
        {{ c.name }}
      </button>
    </div>
    <p text-13px style="color: var(--cc-text-3)">选择后本机将记住,可在设置中修改</p>
  </div>
</template>
