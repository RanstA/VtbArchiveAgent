<script setup lang="ts">
import type { Evidence } from '@/types'
import { formatTimestamp } from '@/utils/time'

defineProps<{ evidence: Evidence }>()

const levelLabels = {
  direct: 'L1 直接证据',
  corroborating: 'L2 支持证据',
  contextual: 'L3 上下文',
}
</script>

<template>
  <article class="evidence-card">
    <div class="evidence-rail" :class="evidence.level"></div>
    <div class="evidence-body">
      <header>
        <span class="evidence-level" :class="evidence.level">{{ levelLabels[evidence.level] }}</span>
        <time class="mono">{{ formatTimestamp(evidence.timestampMs) }}</time>
      </header>
      <p>{{ evidence.content }}</p>
      <footer>{{ evidence.source }}</footer>
    </div>
  </article>
</template>
