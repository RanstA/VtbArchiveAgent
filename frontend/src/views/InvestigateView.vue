<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { investigate } from '@/api/investigate'
import { useVtuberStore } from '@/stores/vtuber'
import type { ResearchEvidenceKind, ResearchLocation, ResearchReport } from '@/types'
import { formatTimestamp } from '@/utils/time'

const { currentVtuber, currentVtuberId } = storeToRefs(useVtuberStore())
const query = ref('')
const running = ref(false)
const result = ref<ResearchReport>()
const error = ref('')
let controller: AbortController | undefined

const sourceLabels: Record<ResearchEvidenceKind, string> = {
  speech: '字幕转写 · 发言证据',
  audience_reaction: '弹幕 · 观众反应',
  archived_interpretation: '话题 · 已有归档解释',
}
const hasStarted = computed(() => running.value || Boolean(result.value))

function timelineTarget(location: ResearchLocation) {
  return {
    name: 'timeline',
    params: { vtuberId: result.value!.vtuberId, streamId: location.streamId },
    query: { atMs: String(location.streamStartMs) },
  }
}

function resetInvestigation() {
  controller?.abort()
  controller = undefined
  query.value = ''
  running.value = false
  result.value = undefined
  error.value = ''
}

async function runInvestigation() {
  const vtuberId = currentVtuberId.value
  const question = query.value.trim()
  if (!question || !vtuberId || running.value) return
  const requestController = new AbortController()
  controller = requestController
  running.value = true
  result.value = undefined
  error.value = ''
  try {
    const report = await investigate(vtuberId, question, requestController.signal)
    if (requestController.signal.aborted || controller !== requestController) return
    if (report.vtuberId !== vtuberId) throw new Error('研究报告与当前主播不一致。')
    result.value = report
  } catch (reason) {
    if (!requestController.signal.aborted && controller === requestController) {
      error.value = reason instanceof Error ? reason.message : '调查请求失败'
    }
  } finally {
    if (controller === requestController) running.value = false
  }
}

// Discard stale reports when switching workspace or leaving this page.
watch(currentVtuberId, resetInvestigation, { flush: 'sync' })
onBeforeUnmount(() => controller?.abort())
</script>

<template>
  <main class="page investigate-page">
    <header class="page-header">
      <div><span class="eyebrow">DEEP RESEARCH / {{ currentVtuber?.displayName ?? '主播档案' }}</span><h1>档案调查</h1></div>
      <div class="header-metric"><span>MODE</span><strong>LOCAL RESEARCH</strong></div>
    </header>

    <form class="investigate-input" @submit.prevent="runInvestigation">
      <label for="investigation-query">调查问题</label>
      <div>
        <textarea id="investigation-query" v-model="query" rows="2" maxlength="1000" placeholder="例如：主播有没有提到过车祸？"></textarea>
        <button class="button" type="submit" :disabled="running || !query.trim() || !currentVtuberId">{{ running ? '调查中…' : '开始调查' }}</button>
      </div>
      <p>仅供本地开发，需后端显式启用。检索真实档案并校验引用；观众弹幕不等同于主播事实。</p>
    </form>
    <p v-if="error" class="error-banner" role="alert">{{ error }}</p>

    <div class="investigation-grid" :class="{ dormant: !hasStarted }" :aria-busy="running">
      <section class="trace-panel" aria-label="研究报告">
        <header class="section-heading compact">
          <div><span class="section-index">01</span><h2>研究报告</h2></div>
        </header>
        <div class="research-copy">
          <p v-if="running" role="status">正在检索证据并校验报告，请稍候。此过程可能需要数分钟。</p>
          <template v-else-if="result">
            <p class="research-question">{{ result.query }}</p>
            <p class="research-answer">{{ result.answer }}</p>
            <p class="research-meta">检索词：{{ result.searchTerms.join(' · ') }}</p>
            <h3>限制与证据边界</h3>
            <ul><li v-for="(limitation, index) in result.limitations" :key="index">{{ limitation }}</li></ul>
          </template>
          <p v-else>输入关于{{ currentVtuber?.displayName ?? '当前主播' }}的问题，查看带引用的档案研究报告。不会自动发起调查。</p>
        </div>
      </section>

      <section class="candidate-panel" aria-label="发现与证据位置">
        <header class="section-heading compact">
          <div><span class="section-index">02</span><h2>发现与引用</h2></div>
          <span>{{ result?.findings.length ?? 0 }} FINDINGS</span>
        </header>
        <div v-if="running" class="candidate-loading" role="status"><i aria-hidden="true"></i><span>等待真实研究结果…</span></div>
        <template v-else-if="result">
          <div v-if="result.findings.length" class="candidate-list">
            <article v-for="(finding, index) in result.findings" :key="index" class="investigation-candidate">
              <header><span class="event-type">{{ sourceLabels[finding.kind] }}</span></header>
              <h3>{{ finding.statement }}</h3>
              <div v-for="citation in finding.citations" :key="citation.evidenceRef" class="research-citation">
                <blockquote>{{ citation.quote }}</blockquote>
                <span class="mono">{{ citation.evidenceRef }}</span>
              </div>
            </article>
          </div>
          <div v-else class="candidate-empty">当前证据不足，没有可返回的研究发现；这不代表相关内容没有发生。</div>
          <section v-if="result.locations.length" class="research-copy" aria-label="证据时间位置">
            <h3>证据位置 · {{ result.evidenceRefs.length }} 条引用</h3>
            <article v-for="location in result.locations" :key="location.evidenceRef" class="research-location">
              <span class="mono">{{ location.evidenceRef }}</span>
              <RouterLink :to="timelineTarget(location)">
                整场 {{ formatTimestamp(location.streamStartMs) }}<template v-if="location.streamEndMs != null"> – {{ formatTimestamp(location.streamEndMs) }}</template> · 查看时间线 ↗
              </RouterLink>
              <small>直播 {{ location.streamId }} · 来源 {{ location.sourcePartIds.join(' · ') }}</small>
              <small v-if="location.partId != null && location.localStartMs != null">
                {{ location.partId }} 局部 {{ formatTimestamp(location.localStartMs) }}<template v-if="location.localEndMs != null"> – {{ formatTimestamp(location.localEndMs) }}</template>
              </small>
              <small v-else>话题为整场时间范围，不推断单一 Part 的局部位置。</small>
            </article>
          </section>
        </template>
        <div v-else class="candidate-empty">研究发现、原文引用与直播位置将显示在这里。</div>
      </section>
    </div>
  </main>
</template>

<style scoped>
.research-copy { padding: 18px; color: var(--muted); font-size: .8rem; line-height: 1.7; overflow-wrap: anywhere; }
.research-copy p { margin: 0 0 14px; }
.research-copy h3 { color: var(--text-strong); font-size: .85rem; }
.research-copy ul { padding-left: 18px; }
.research-copy li + li { margin-top: 8px; }
.research-question { color: var(--accent); }
.research-answer { white-space: pre-wrap; color: var(--text); }
.research-meta { color: var(--faint); font-size: .72rem; }
.research-citation { margin-top: 12px; padding-left: 12px; border-left: 2px solid var(--line-strong); overflow-wrap: anywhere; }
.research-citation blockquote { margin: 0 0 6px; color: var(--text); font-size: .82rem; line-height: 1.6; }
.research-citation > span, .research-location > span { color: var(--faint); font-size: .68rem; }
.research-location { display: grid; gap: 5px; padding: 12px 0; border-bottom: 1px solid var(--line); }
.research-location a { color: var(--accent); text-decoration: none; }
.research-location a:hover { text-decoration: underline; }
.research-location small { color: var(--faint); }
.investigation-candidate h3 { overflow-wrap: anywhere; line-height: 1.6; }
@media (max-width: 1100px) { .investigation-grid { grid-template-columns: 1fr; } }
</style>
