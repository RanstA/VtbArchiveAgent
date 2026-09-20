<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoute } from 'vue-router'
import { getBackendHealth } from '@/api/system'
import AppSidebar from '@/components/layout/AppSidebar.vue'
import { useThemeStore } from '@/stores/theme'

const backendStatus = ref<'checking' | 'online' | 'offline'>('checking')
const route = useRoute()
const themeStore = useThemeStore()
const { isDark } = storeToRefs(themeStore)
const isWorkspace = computed(() => route.meta.workspace === true)

onMounted(async () => {
  try {
    const result = await getBackendHealth()
    backendStatus.value = result.status === 'ok' ? 'online' : 'offline'
  } catch {
    backendStatus.value = 'offline'
  }
})
</script>

<template>
  <div v-if="isWorkspace" class="app-shell">
    <AppSidebar :backend-status="backendStatus" />
    <div class="workspace-shell">
      <div class="workspace-topbar">
        <span>LOCAL RESEARCH WORKSPACE</span>
        <div class="topbar-actions">
          <span class="mono">INDEX / V0.1</span>
          <button
            class="theme-toggle"
            type="button"
            :aria-label="isDark ? '切换至浅色模式' : '切换至深色模式'"
            :aria-pressed="!isDark"
            @click="themeStore.toggleTheme"
          >
            <span aria-hidden="true" class="theme-icon">{{ isDark ? '☾' : '☼' }}</span>
            <span>{{ isDark ? '深色' : '浅色' }}</span>
            <i aria-hidden="true"><b></b></i>
          </button>
        </div>
      </div>
      <RouterView />
    </div>
  </div>
  <RouterView v-else />
</template>
