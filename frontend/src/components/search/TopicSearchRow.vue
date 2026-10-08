<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { getTopicEvidence } from '@/api/search'
import type { SearchHit, TopicEvidenceBundle } from '@/types'
import { formatTimestamp } from '@/utils/time'

const props = defineProps<{ result: SearchHit; vtuberId: string }>()
const expanded = ref(false)
const evidence = ref<TopicEvidenceBundle>()
const loading = ref(false)
const error = ref('')
let evidenceController: AbortController | undefined

async function loadEvidence() {
  const topicId = props.result.topicSegmentId
  if (!topicId || loading.value) return

  const controller = new AbortController()
  evidenceController = controller
  loading.value = true
  error.value = ''
  try {
    const bundle = await getTopicEvidence(topicId, controller.signal)
    if (!controller.signal.aborted) evidence.value = bundle
  } catch (reason) {
    if (!controller.signal.aborted) {
      error.value = reason instanceof Error ? reason.message : '无法展开话题证据'
    }
  } finally {
    if (evidenceController === controller) loading.value = false
  }
}

function toggleEvidence() {
  expanded.value = !expanded.value
  if (expanded.value && !evidence.value) void loadEvidence()
}

onBeforeUnmount(() => evidenceController?.abort())
</script>

<template>
  <article class="search-result-card">
    <div class="result-time">
      <strong class="mono">{{ result.startMs != null ? formatTimestamp(result.startMs) : '时间未提供' }}</strong>
      <span v-if="result.endMs != null" class="mono">至 {{ formatTimestamp(result.endMs) }}</span>
      <span>整场直播时间</span>
    </div>
    <div class="result-content">
      <div class="event-meta-row"><span class="event-type">话题</span></div>
      <h2>{{ result.title }}</h2>
      <p>{{ result.snippet }}</p>
      <div class="result-actions">
        <button v-if="result.topicSegmentId" type="button" class="button button-secondary"
          :aria-expanded="expanded" :aria-controls="`topic-evidence-${result.topicSegmentId}`"
          @click="toggleEvidence">{{ expanded ? '收起证据' : '展开字幕与弹幕' }}</button>
        <RouterLink :to="{ name: 'timeline', params: { vtuberId, streamId: result.streamId } }">
          查看所属直播时间线 <span aria-hidden="true">↗</span>
        </RouterLink>
      </div>
    </div>
    <div class="result-confidence">
      <span class="mono">{{ result.score.toFixed(1) }}</span>
      <small>匹配分</small>
    </div>

    <section v-if="expanded" :id="`topic-evidence-${result.topicSegmentId}`" class="topic-evidence" aria-label="话题证据">
      <div v-if="loading" class="page-loading" role="status">正在加载字幕与弹幕…</div>
      <div v-else-if="error">
        <p class="error-banner" role="alert">证据展开失败：{{ error }}。证据可能暂时不可用或引用不完整。</p>
        <button type="button" class="button button-secondary" @click="loadEvidence">重试</button>
      </div>
      <template v-else-if="evidence">
        <p class="evidence-time-note">以下时间均为对应分段（Part）内时间；上方话题位置为整场直播时间。</p>
        <div class="topic-evidence-grid">
          <section aria-label="字幕证据">
            <h3>字幕 <span>{{ evidence.transcripts.length }} 条</span></h3>
            <div v-if="evidence.transcripts.length" class="evidence-list">
              <article v-for="item in evidence.transcripts" :key="item.id" class="evidence-card">
                <div class="evidence-rail e3"></div>
                <div class="evidence-body">
                  <header>
                    <span class="evidence-level e3">字幕 · {{ item.partId }}</span>
                    <time class="mono">{{ formatTimestamp(item.startMs) }} – {{ formatTimestamp(item.endMs) }}</time>
                  </header>
                  <p>{{ item.text || item.rawText }}</p>
                  <footer>{{ item.source }} · {{ item.id }}</footer>
                </div>
              </article>
            </div>
            <p v-else class="evidence-time-note">暂无关联字幕。</p>
          </section>
          <section aria-label="弹幕证据">
            <h3>代表性弹幕 <span>{{ evidence.danmaku.length }} 条</span></h3>
            <div v-if="evidence.danmaku.length" class="evidence-list">
              <article v-for="item in evidence.danmaku" :key="item.id" class="evidence-card">
                <div class="evidence-rail e1"></div>
                <div class="evidence-body">
                  <header>
                    <span class="evidence-level e1">弹幕 · {{ item.partId }}</span>
                    <time class="mono">{{ formatTimestamp(item.timestampMs) }}</time>
                  </header>
                  <p>{{ item.text || item.rawText }}</p>
                  <footer>弹幕 ID · {{ item.id }}</footer>
                </div>
              </article>
            </div>
            <p v-else class="evidence-time-note">暂无关联弹幕。</p>
          </section>
        </div>
      </template>
    </section>
  </article>
</template>

<style scoped>
.result-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; }
.result-actions .button { min-height: 34px; padding: 0 12px; font-size: .74rem; }
.topic-evidence { grid-column: 1 / -1; padding: 20px; border-top: 1px solid var(--line); background: var(--surface-deep); }
.evidence-time-note { margin: 0 0 14px; color: var(--muted); font-size: .76rem; line-height: 1.6; }
.topic-evidence-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
.topic-evidence-grid h3 { margin: 0; color: var(--text-strong); font-size: .84rem; }
.topic-evidence-grid h3 span { margin-left: 8px; color: var(--faint); font-size: .72rem; font-weight: 400; }
.evidence-list { max-height: 420px; overflow-y: auto; }
.evidence-body { min-width: 0; }
.evidence-body header { flex-wrap: wrap; gap: 8px; }
.evidence-body p, .evidence-body footer { overflow-wrap: anywhere; }

@media (max-width: 1000px) {
  .topic-evidence-grid { grid-template-columns: 1fr; }
}
</style>
