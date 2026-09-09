<script setup lang="ts">
import type { Evidence, EvidenceLevel } from '@/types'
import { formatTimestamp } from '@/utils/time'

defineProps<{ evidence: Evidence }>()

const levelMeta = {
  E0_METADATA: { label: 'E0 元数据', tone: 'e0' },
  E1_AUDIENCE_REACTION: { label: 'E1 观众反应', tone: 'e1' },
  E2_EVENT_INFERENCE: { label: 'E2 事件推断', tone: 'e2' },
  E3_ASR_SUBTITLE: { label: 'E3 ASR / 字幕', tone: 'e3' },
  E4_VIDEO_VLM: { label: 'E4 视频 / VLM', tone: 'e4' },
  E5_HUMAN_VERIFIED: { label: 'E5 人工核验', tone: 'e5' },
} satisfies Record<EvidenceLevel, { label: string; tone: string }>
</script>

<template>
  <article class="evidence-card">
    <div class="evidence-rail" :class="levelMeta[evidence.level].tone"></div>
    <div class="evidence-body">
      <header>
        <span class="evidence-level" :class="levelMeta[evidence.level].tone">{{ levelMeta[evidence.level].label }}</span>
        <time class="mono">{{ formatTimestamp(evidence.timestampMs) }}</time>
      </header>
      <p>{{ evidence.content }}</p>
      <footer>{{ evidence.source }}</footer>
    </div>
  </article>
</template>
