<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { searchEvents } from '@/api/search'
import SearchEventRow from '@/components/event/SearchEventRow.vue'
import type { EventSearchResult } from '@/types'

const filters = reactive({ query: '', from: '', to: '', person: 'all', topic: 'all' })
const results = ref<EventSearchResult[]>([])
const loading = ref(false)
const searched = ref(false)
const error = ref('')

async function runSearch() {
  loading.value = true
  error.value = ''
  try {
    results.value = await searchEvents(filters)
    searched.value = true
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '无法检索 Event Store'
  } finally {
    loading.value = false
  }
}

onMounted(runSearch)
</script>

<template>
  <main class="page search-page">
    <header class="page-header">
      <div><span class="eyebrow">EVENT RETRIEVAL</span><h1>历史事件检索</h1></div>
      <div class="header-metric"><span>SEARCH UNIT</span><strong>EVENT / FTS READY</strong></div>
    </header>

    <section class="search-workbench content-panel">
      <form class="search-form" @submit.prevent="runSearch">
        <label class="search-field main-search">
          <span class="sr-only">检索历史事件</span>
          <span aria-hidden="true" class="search-symbol"></span>
          <input v-model="filters.query" type="search" placeholder="输入人物、话题或事件关键词" />
          <kbd>↵</kbd>
        </label>
        <button class="button" type="submit" :disabled="loading">{{ loading ? '检索中…' : '搜索 Event' }}</button>
        <div class="advanced-filters">
          <label><span>从</span><input v-model="filters.from" type="date" /></label>
          <label><span>至</span><input v-model="filters.to" type="date" /></label>
          <label><span>人物</span><select v-model="filters.person"><option value="all">全部人物</option><option value="host">主播本人</option><option value="guest">联动嘉宾</option></select></label>
          <label><span>话题</span><select v-model="filters.topic"><option value="all">全部话题</option><option value="新衣装">新衣装</option><option value="游戏">游戏</option><option value="活动">活动</option></select></label>
        </div>
      </form>
    </section>

    <section class="search-results">
      <header class="section-heading">
        <div><span class="section-index">RESULT</span><h2>匹配事件</h2></div>
        <span>{{ loading ? '正在查询索引' : `${results.length} 条结果` }}</span>
      </header>
      <p v-if="error" class="error-banner">{{ error }}</p>
      <div v-if="loading" class="page-loading">正在检索 Event Store…</div>
      <div v-else-if="results.length" class="search-result-list">
        <SearchEventRow v-for="result in results" :key="result.event.id" :result="result" />
      </div>
      <div v-else-if="searched" class="empty-panel">没有找到匹配事件。可以缩短关键词或清除时间范围。</div>
    </section>
  </main>
</template>
