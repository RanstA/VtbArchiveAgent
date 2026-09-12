<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { getEventEvidence, getStreamEvents } from '@/api/events'
import { getStream } from '@/api/streams'
import EventCard from '@/components/event/EventCard.vue'
import TimelineIntensityChart from '@/components/event/TimelineIntensityChart.vue'
import type { Event, Evidence, Stream } from '@/types'
import { formatDateTime, formatTimestamp } from '@/utils/time'

const route = useRoute()
const stream = ref<Stream>()
const events = ref<Event[]>([])
const evidenceByEvent = ref<Record<string, Evidence[]>>({})
const activeEventId = ref<string>()
const loading = ref(true)
const error = ref('')

const duration = computed(() => stream.value?.durationMs ?? Math.max(...events.value.map((event) => event.endMs), 1))

async function loadTimeline() {
  loading.value = true
  error.value = ''
  try {
    const streamId = String(route.params.streamId)
    const [streamResult, eventResults] = await Promise.all([getStream(streamId), getStreamEvents(streamId)])
    stream.value = streamResult
    events.value = eventResults
    const evidenceEntries = await Promise.all(eventResults.map(async (event) => [event.id, await getEventEvidence(event.id)] as const))
    evidenceByEvent.value = Object.fromEntries(evidenceEntries)

    const hashEventId = route.hash.replace('#', '')
    if (hashEventId && eventResults.some((event) => event.id === hashEventId)) {
      activeEventId.value = hashEventId
      await nextTick()
      document.getElementById(hashEventId)?.scrollIntoView({ block: 'center' })
    }
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '无法读取直播时间线'
  } finally {
    loading.value = false
  }
}

function toggleEvent(eventId: string) {
  activeEventId.value = activeEventId.value === eventId ? undefined : eventId
}

function selectFromChart(eventId: string) {
  activeEventId.value = eventId
  nextTick(() => document.getElementById(eventId)?.scrollIntoView({ behavior: 'smooth', block: 'center' }))
}

onMounted(loadTimeline)
watch(() => route.params.streamId, loadTimeline)
</script>

<template>
  <main class="page timeline-page">
    <RouterLink class="back-link" to="/archive">← 返回直播档案</RouterLink>
    <header v-if="stream" class="page-header timeline-header">
      <div>
        <span class="eyebrow">STREAM TIMELINE / {{ stream.bvIds.join(' · ') }}</span>
        <h1>{{ stream.title }}</h1>
        <div class="stream-facts">
          <span>{{ formatDateTime(stream.liveTime) }}</span>
          <span class="mono">{{ formatTimestamp(duration) }}</span>
          <span>{{ events.length }} EVENTS</span>
        </div>
      </div>
      <div class="archive-stamp"><span>ARCHIVED</span><strong>{{ stream.hasDanmaku ? 'DANMAKU READY' : 'NO DANMAKU' }}</strong></div>
    </header>

    <div v-if="loading" class="page-loading">正在重建直播时间线…</div>
    <p v-else-if="error || !stream" class="error-banner">{{ error || '未找到该直播档案。' }}</p>
    <template v-else>
      <section class="timeline-visual content-panel">
        <div class="section-heading compact">
          <div><span class="section-index">01</span><h2>强度概览</h2></div>
          <span class="chart-legend"><i></i> 弹幕相对强度 <b></b> EVENT</span>
        </div>
        <TimelineIntensityChart :events="events" :duration-ms="duration" :active-event-id="activeEventId" @select="selectFromChart" />
      </section>

      <section class="timeline-events">
        <header class="section-heading">
          <div><span class="section-index">02</span><h2>Event 时间线</h2></div>
          <span>{{ events.length }} 个已识别事件 · 点击展开 Evidence</span>
        </header>
        <div class="event-list">
          <EventCard
            v-for="event in events"
            :id="event.id"
            :key="event.id"
            :event="event"
            :evidence="evidenceByEvent[event.id] ?? []"
            :expanded="activeEventId === event.id"
            @toggle="toggleEvent"
          />
          <div v-if="!events.length" class="empty-panel">该直播尚未生成 Event。</div>
        </div>
      </section>
    </template>
  </main>
</template>
