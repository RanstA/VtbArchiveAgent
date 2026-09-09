<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { getHighlightCandidates } from '@/api/highlights'
import HighlightCard from '@/components/event/HighlightCard.vue'
import type { HighlightCandidate, ReviewStatus } from '@/types'

const candidates = ref<HighlightCandidate[]>([])
const loading = ref(true)
const error = ref('')

const reviewed = computed(() => candidates.value.filter((candidate) => candidate.reviewStatus !== 'pending').length)

function updateReview(index: number, status: Exclude<ReviewStatus, 'pending'>) {
  const candidate = candidates.value[index]
  if (candidate) candidate.reviewStatus = status
}

onMounted(async () => {
  try {
    candidates.value = await getHighlightCandidates()
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '无法读取高光候选'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <main class="page highlights-page">
    <header class="page-header">
      <div><span class="eyebrow">REVIEW QUEUE</span><h1>高光候选</h1></div>
      <div class="review-progress"><span>{{ reviewed }} / {{ candidates.length }}</span><small>已完成审核</small></div>
    </header>

    <div class="highlights-note">
      <span class="mono">LOCAL STATE</span>
      审核结果仅保存在当前页面状态，尚未写回后端。
    </div>

    <div v-if="loading" class="page-loading">正在加载高光候选…</div>
    <p v-else-if="error" class="error-banner">{{ error }}</p>
    <section v-else class="highlight-list">
      <HighlightCard v-for="(candidate, index) in candidates" :key="candidate.event.id" :candidate="candidate" @review="updateReview(index, $event)" />
    </section>
  </main>
</template>
