<script setup lang="ts">
defineProps<{
  query: string
  status: string
  count: number
  loading: boolean
}>()

const emit = defineEmits<{
  'update:query': [value: string]
  'update:status': [value: 'all' | 'danmaku' | 'events' | 'pending']
  search: []
}>()
</script>

<template>
  <form class="filter-bar" @submit.prevent="emit('search')">
    <label class="search-field">
      <span class="sr-only">搜索标题或 BV 号</span>
      <span aria-hidden="true" class="search-symbol"></span>
      <input
        :value="query"
        type="search"
        placeholder="搜索标题或 BV 号"
        @input="emit('update:query', ($event.target as HTMLInputElement).value)"
      />
      <kbd>↵</kbd>
    </label>
    <label class="select-field">
      <span>状态</span>
      <select :value="status" @change="emit('update:status', ($event.target as HTMLSelectElement).value as 'all' | 'danmaku' | 'events' | 'pending')">
        <option value="all">全部档案</option>
        <option value="danmaku">已有弹幕</option>
        <option value="events">已有 Event</option>
        <option value="pending">待生成 Event</option>
      </select>
    </label>
    <button class="button button-secondary" type="submit" :disabled="loading">{{ loading ? '检索中' : '筛选' }}</button>
    <span class="result-count">{{ count }} 场直播</span>
  </form>
</template>
