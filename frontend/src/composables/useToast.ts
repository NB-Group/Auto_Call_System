import { ref } from 'vue'

const toasts = ref<{ id: number; text: string }[]>([])
let seq = 0

export function useToast() {
  function push(text: string) {
    const id = ++seq
    toasts.value.push({ id, text })
    setTimeout(() => (toasts.value = toasts.value.filter(t => t.id !== id)), 2500)
  }
  return { toasts, push }
}
