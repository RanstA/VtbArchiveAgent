<script setup lang="ts">
import type { HighlightCandidate, ReviewStatus } from '@/types'
import { formatTimestamp } from '@/utils/time'

defineProps<{ candidate: HighlightCandidate }>()

const emit = defineEmits<{
  review: [status: Exclude<ReviewStatus, 'pending'>]
}>()

const reviewLabels = {
  pending: '待审核',
  approved: '值得切',
  rejected: '不值得切',
}
</script>

<template>
  <article class="highlight-card" :class="`review-${candidate.reviewStatus}`">
    <div class="highlight-score">
      <span class="score-ring" :style="{ '--score': `${candidate.score * 360}deg` }">
        <strong class="mono">{{ Math.round(candidate.score * 100) }}</strong>
      </span>
      <small>HIGHLIGHT<br/>SCORE</small>
    </div>
    <div class="highlight-main">
      <header>
        <span class="review-status" :class="candidate.reviewStatus">{{ reviewLabels[candidate.reviewStatus] }}</span>
        <span class="mono muted">{{ formatTimestamp(candidate.event.startMs) }} — {{ formatTimestamp(candidate.event.endMs) }}</span>
      </header>
      <h2>{{ candidate.event.title }}</h2>
      <p>{{ candidate.reason }}</p>
      <footer>
        <button class="button review-yes" type="button" @click="emit('review', 'approved')">值得切</button>
        <button class="button button-secondary review-no" type="button" @click="emit('review', 'rejected')">不值得切</button>
        <RouterLink class="detail-link" :to="{ name: 'timeline', params: { streamId: candidate.event.streamId }, hash: `#${candidate.event.id}` }">查看详情 ↗</RouterLink>
      </footer>
    </div>
  </article>
</template>
