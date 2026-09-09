<script setup lang="ts">
const navItems = [
  { to: '/archive', label: 'Archive', meta: '直播档案', icon: 'AR' },
  { to: '/search', label: 'Search', meta: '事件检索', icon: 'SE' },
  { to: '/highlights', label: 'Highlights', meta: '高光候选', icon: 'HI' },
  { to: '/investigate', label: 'Investigate', meta: '调查入口', icon: 'IN' },
]

defineProps<{
  backendStatus: 'checking' | 'online' | 'offline'
}>()
</script>

<template>
  <aside class="app-sidebar">
    <div class="brand">
      <div class="brand-mark" aria-hidden="true"><span></span><span></span><span></span></div>
      <div>
        <strong>VTUBER</strong>
        <span>ARCHIVE / V0</span>
      </div>
    </div>

    <nav class="primary-nav" aria-label="主要导航">
      <RouterLink v-for="item in navItems" :key="item.to" :to="item.to" class="nav-item">
        <span class="nav-icon">{{ item.icon }}</span>
        <span class="nav-copy"><strong>{{ item.label }}</strong><small>{{ item.meta }}</small></span>
      </RouterLink>
    </nav>

    <div class="sidebar-footer">
      <div class="system-status">
        <span class="status-dot" :class="backendStatus"></span>
        <div>
          <span>FastAPI</span>
          <small>{{ backendStatus === 'online' ? '服务已连接' : backendStatus === 'checking' ? '检查连接中' : '离线 · Mock 模式' }}</small>
        </div>
      </div>
      <p>Stream → Event → Evidence</p>
    </div>
  </aside>
</template>
