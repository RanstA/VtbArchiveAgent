<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { isMultiVtuberMode } from '@/config/app'
import { useVtuberStore } from '@/stores/vtuber'

const vtuberStore = useVtuberStore()
const { currentVtuber, currentVtuberId } = storeToRefs(vtuberStore)

const navItems = computed(() => {
  const vtuberId = currentVtuberId.value

  return [
    { name: 'archive', label: 'Archive', meta: '直播档案', icon: 'AR' },
    { name: 'search', label: 'Search', meta: '事件检索', icon: 'SE' },
    { name: 'highlights', label: 'Highlights', meta: '高光候选', icon: 'HI' },
    { name: 'investigate', label: 'Investigate', meta: '调查入口', icon: 'IN' },
  ].map((item) => ({ ...item, to: { name: item.name, params: { vtuberId } } }))
})

defineProps<{
  backendStatus: 'checking' | 'online' | 'offline'
}>()
</script>

<template>
  <aside class="app-sidebar">
    <div class="brand">
      <div class="brand-mark" aria-hidden="true"><span></span><span></span><span></span></div>
      <div>
        <strong>{{ currentVtuber?.displayName ?? 'VTUBER' }}</strong>
        <span>ARCHIVE</span>
      </div>
    </div>

    <nav class="primary-nav" aria-label="主要导航">
      <RouterLink v-for="item in navItems" :key="item.name" :to="item.to" class="nav-item">
        <span class="nav-icon">{{ item.icon }}</span>
        <span class="nav-copy"><strong>{{ item.label }}</strong><small>{{ item.meta }}</small></span>
      </RouterLink>
    </nav>

    <RouterLink v-if="isMultiVtuberMode" class="archive-switch" to="/vtubers">
      切换档案馆
      <span aria-hidden="true">↗</span>
    </RouterLink>

    <div class="sidebar-footer">
      <div class="system-status">
        <span class="status-dot" :class="backendStatus"></span>
        <div>
          <span>FastAPI</span>
          <small>{{ backendStatus === 'online' ? '服务已连接' : backendStatus === 'checking' ? '检查连接中' : '离线 · Mock 模式' }}</small>
        </div>
      </div>
      <p>Stream → Highlight → Evidence</p>
    </div>
  </aside>
</template>

<style scoped>
.archive-switch {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 14px 10px 0;
  padding: 9px 2px;
  color: var(--faint);
  border-bottom: 1px solid var(--line);
  font-size: .72rem;
  text-decoration: none;
}

.archive-switch:hover {
  color: var(--accent);
}
</style>
