<script setup lang="ts">
import EvidenceCard from '@/components/evidence/EvidenceCard.vue'
import type { Event, Evidence } from '@/types'
import { formatDuration, formatTimestamp } from '@/utils/time'

defineProps<{
  event: Event
  evidence: Evidence[]
  expanded: boolean
}>()

const emit = defineEmits<{ toggle: [eventId: string] }>()

const typeLabels = {
  talk: '杂谈',
  gameplay: '游戏',
  reaction: '反应',
  announcement: '公告',
  collab: '联动',
}
</script>

<template>
  <article class="event-card" :class="{ expanded }">
    <button class="event-card-main" type="button" :aria-expanded="expanded" @click="emit('toggle', event.id)">
      <span class="event-time mono">{{ formatTimestamp(event.startMs) }}</span>
      <span class="event-copy">
        <span class="event-meta-row">
          <span class="event-type">{{ typeLabels[event.eventType] }}</span>
          <span class="event-duration mono">{{ formatDuration(event.startMs, event.endMs) }}</span>
        </span>
        <strong>{{ event.title }}</strong>
        <span class="event-summary">{{ event.summary }}</span>
      </span>
      <span class="event-metrics">
        <span class="confidence-value mono">{{ Math.round(event.confidence * 100) }}%</span>
        <span class="confidence-track"><i :style="{ width: `${event.confidence * 100}%` }"></i></span>
        <small>CONFIDENCE</small>
      </span>
      <span class="evidence-count"><b>{{ evidence.length }}</b><small>EVIDENCE</small></span>
      <span class="expand-button" aria-hidden="true">{{ expanded ? '−' : '+' }}</span>
    </button>

    <div v-if="expanded" class="event-detail">
      <div class="event-boundary">
        <span><small>START</small><strong class="mono">{{ formatTimestamp(event.startMs) }}</strong></span>
        <span class="boundary-line"><i></i></span>
        <span><small>END</small><strong class="mono">{{ formatTimestamp(event.endMs) }}</strong></span>
      </div>
      <div class="evidence-list">
        <EvidenceCard v-for="item in evidence" :key="item.id" :evidence="item" />
        <div v-if="!evidence.length" class="inline-empty">该事件暂未关联 Evidence。</div>
      </div>
    </div>
  </article>
</template>
