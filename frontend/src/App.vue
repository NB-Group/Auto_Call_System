<script setup lang="ts">
import { onMounted } from 'vue'
import { useDark } from './composables/useDark'

const { initTheme } = useDark()
onMounted(initTheme)
</script>

<template>
  <router-view />
</template>
