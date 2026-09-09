<script setup lang="ts">
import type { EventSearchResult } from '@/types'
import { formatDateTime, formatTimestamp } from '@/utils/time'

defineProps<{ result: EventSearchResult }>()
</script>

<template>
  <article class="search-result-card">
    <div class="result-time">
      <strong class="mono">{{ formatTimestamp(result.event.startMs) }}</strong>
      <span>{{ formatDateTime(result.stream.liveTime).slice(0, 10) }}</span>
    </div>
    <div class="result-content">
      <div class="event-meta-row">
        <span class="event-type">{{ result.event.eventType }}</span>
        <span class="mono result-stream">{{ result.stream.bvId }}</span>
      </div>
      <h2>{{ result.event.title }}</h2>
      <p>{{ result.matchedText }}</p>
      <RouterLink :to="{ name: 'timeline', params: { streamId: result.stream.id }, hash: `#${result.event.id}` }">
        {{ result.stream.title }} <span aria-hidden="true">↗</span>
      </RouterLink>
    </div>
    <div class="result-confidence">
      <span class="mono">{{ Math.round(result.event.confidence * 100) }}%</span>
      <small>CONFIDENCE</small>
    </div>
  </article>
</template>
