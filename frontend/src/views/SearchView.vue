<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { searchTopics } from '@/api/search'
import TopicSearchRow from '@/components/search/TopicSearchRow.vue'
import { useVtuberStore } from '@/stores/vtuber'
import type { SearchHit } from '@/types'

const { currentVtuber, currentVtuberId } = storeToRefs(useVtuberStore())
const query = ref('')
const submittedQuery = ref('')
const results = ref<SearchHit[]>([])
const loading = ref(false)
const searched = ref(false)
const error = ref('')
let searchController: AbortController | undefined

function resetSearch() {
  searchController?.abort()
  searchController = undefined
  query.value = ''
  submittedQuery.value = ''
  results.value = []
  loading.value = false
  searched.value = false
  error.value = ''
}

async function runSearch() {
  const term = query.value.trim()
  const vtuberId = currentVtuberId.value
  if (!term || !vtuberId) return

  searchController?.abort()
  const controller = new AbortController()
  searchController = controller
  loading.value = true
  searched.value = true
  submittedQuery.value = term
  results.value = []
  error.value = ''
  try {
    const hits = await searchTopics({ query: term, vtuberId, limit: 5 }, controller.signal)
    if (!controller.signal.aborted) results.value = hits
  } catch (reason) {
    if (!controller.signal.aborted) {
      error.value = reason instanceof Error ? reason.message : '无法检索直播话题'
    }
  } finally {
    if (searchController === controller) loading.value = false
  }
}

// A workspace change clears both hits and pending requests from the previous VTuber.
watch(currentVtuberId, resetSearch)
onBeforeUnmount(() => searchController?.abort())
</script>

<template>
  <main class="page search-page">
    <header class="page-header">
      <div><span class="eyebrow">TOPIC SEARCH / {{ currentVtuber?.displayName ?? '主播档案' }}</span><h1>直播历史检索</h1></div>
      <div class="header-metric"><span>SEARCH UNIT</span><strong>TOPIC</strong></div>
    </header>

    <section class="search-workbench content-panel">
      <form class="search-form" @submit.prevent="runSearch">
        <label class="search-field main-search">
          <span class="sr-only">检索直播历史</span>
          <span aria-hidden="true" class="search-symbol"></span>
          <input v-model="query" type="search" placeholder="输入歌曲、人物或话题关键词" />
          <kbd>↵</kbd>
        </label>
        <button class="button" type="submit" :disabled="loading || !query.trim() || !currentVtuberId">{{ loading ? '检索中…' : '搜索话题' }}</button>
      </form>
    </section>

    <section class="search-results">
      <header class="section-heading">
        <div><span class="section-index">RESULT</span><h2>匹配话题</h2></div>
        <span>{{ loading ? '正在检索' : `${results.length} 条结果 · 最多显示 5 条` }}</span>
      </header>
      <div v-if="loading" class="page-loading" role="status">正在检索直播话题…</div>
      <p v-else-if="error" class="error-banner" role="alert">检索失败：{{ error }}。请重试。</p>
      <div v-else-if="results.length && currentVtuberId" class="search-result-list">
        <TopicSearchRow v-for="result in results" :key="result.topicSegmentId ?? `${result.streamId}-${result.startMs}`" :result="result" :vtuber-id="currentVtuberId" />
      </div>
      <div v-else-if="searched" class="empty-panel">没有找到与“{{ submittedQuery }}”匹配的话题。可以缩短或更换关键词。</div>
      <div v-else class="empty-panel">输入关键词，查找{{ currentVtuber?.displayName ?? '当前主播' }}的直播话题，并展开字幕与弹幕证据。</div>
    </section>
  </main>
</template>
