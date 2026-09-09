<script setup lang="ts">
import { computed, ref } from 'vue'
import { investigate } from '@/api/investigate'
import AgentTrace from '@/components/agent/AgentTrace.vue'
import EvidenceCard from '@/components/evidence/EvidenceCard.vue'
import type { AgentTraceStep, InvestigationResult } from '@/types'
import { formatTimestamp } from '@/utils/time'

const query = ref('新衣装准备期间提到过哪些确定的信息？')
const running = ref(false)
const result = ref<InvestigationResult>()
const error = ref('')
const trace = ref<AgentTraceStep[]>([
  { id: 'trace-1', label: '搜索相关直播', detail: '等待调查问题', status: 'pending' },
  { id: 'trace-2', label: '筛选候选事件', detail: '等待 Event Retrieval', status: 'pending' },
  { id: 'trace-3', label: '展开事件上下文', detail: '等待候选结果', status: 'pending' },
  { id: 'trace-4', label: '整理证据层级', detail: '等待 Evidence', status: 'pending' },
])

const hasStarted = computed(() => running.value || Boolean(result.value))

async function runInvestigation() {
  if (!query.value.trim() || running.value) return
  running.value = true
  result.value = undefined
  error.value = ''
  trace.value = trace.value.map((step, index) => ({ ...step, status: index === 0 ? 'active' : 'pending' }))

  const traceTimer = window.setInterval(() => {
    const activeIndex = trace.value.findIndex((step) => step.status === 'active')
    if (activeIndex < 0) return
    trace.value[activeIndex]!.status = 'done'
    const nextStep = trace.value[activeIndex + 1]
    if (nextStep) nextStep.status = 'active'
  }, 230)

  try {
    result.value = await investigate(query.value.trim())
    trace.value = result.value.trace
  } catch (reason) {
    error.value = reason instanceof Error ? reason.message : '调查请求失败'
  } finally {
    window.clearInterval(traceTimer)
    running.value = false
  }
}
</script>

<template>
  <main class="page investigate-page">
    <header class="page-header">
      <div><span class="eyebrow">EVIDENCE-LED INVESTIGATION</span><h1>档案调查</h1></div>
      <div class="header-metric"><span>MODE</span><strong>MOCK TRACE / LOCAL</strong></div>
    </header>

    <form class="investigate-input" @submit.prevent="runInvestigation">
      <label for="investigation-query">调查问题</label>
      <div>
        <textarea id="investigation-query" v-model="query" rows="2" placeholder="例如：主播是否提到过新衣装的具体安排？"></textarea>
        <button class="button" type="submit" :disabled="running || !query.trim()">{{ running ? '调查中…' : '开始调查' }}</button>
      </div>
      <p>调查将围绕 Event Store 展开，并按 Evidence 层级给出候选，不生成主播原话。</p>
    </form>
    <p v-if="error" class="error-banner">{{ error }}</p>

    <div class="investigation-grid" :class="{ dormant: !hasStarted }">
      <AgentTrace :steps="trace" :running="running" />

      <section class="candidate-panel">
        <header class="section-heading compact">
          <div><span class="section-index">02</span><h2>候选 Event</h2></div>
          <span>{{ result?.candidates.length ?? 0 }} FOUND</span>
        </header>

        <div v-if="running" class="candidate-loading"><i></i><span>正在核对事件与证据…</span></div>
        <div v-else-if="result?.candidates.length" class="candidate-list">
          <article v-for="candidate in result.candidates" :key="candidate.event.id" class="investigation-candidate">
            <header>
              <span class="event-type">{{ candidate.event.eventType }}</span>
              <span class="candidate-confidence mono">{{ Math.round(candidate.confidence * 100) }}% CONFIDENCE</span>
            </header>
            <h3>{{ candidate.event.title }}</h3>
            <p>{{ candidate.event.summary }}</p>
            <RouterLink :to="{ name: 'timeline', params: { streamId: candidate.stream.id }, hash: `#${candidate.event.id}` }">
              {{ candidate.stream.title }} · <span class="mono">{{ formatTimestamp(candidate.event.startMs) }}</span> ↗
            </RouterLink>
            <div class="candidate-evidence">
              <EvidenceCard v-for="item in candidate.evidence" :key="item.id" :evidence="item" />
            </div>
          </article>
        </div>
        <div v-else class="candidate-empty">输入问题后，候选 Event 与 Evidence 将显示在这里。</div>
      </section>
    </div>
  </main>
</template>
