<script setup lang="ts">
import {
  computed,
  nextTick,
  ref,
  watch,
} from 'vue'

import {
  useRoute,
} from 'vue-router'

import {
  getStream,
  getStreamTimeline,
} from '@/api/streams'

import type {
  StreamDetail,
  StreamTimeline,
  TimelineItem,
} from '@/types'

import {
  formatDateTime,
  formatTimestamp,
} from '@/utils/time'


const IMPORTANT_THRESHOLD = 0.95
const REPLAY_LEAD_MS = 20_000


const route =
  useRoute()

const stream =
  ref<
    StreamDetail
    | undefined
  >()

const timeline =
  ref<
    StreamTimeline
    | undefined
  >()

const activeItemId =
  ref<
    string
    | undefined
  >()

const loading =
  ref(true)

const error =
  ref('')


const items =
  computed(
    () =>
      [...(
        timeline.value
          ?.items
        ?? []
      )].sort(
        (
          first,
          second,
        ) =>
          first.startMs
          - second.startMs,
      ),
  )


const duration =
  computed(
    () => {
      if (
        timeline.value
          ?.durationMs
      ) {
        return (
          timeline.value
            .durationMs
        )
      }

      if (
        stream.value
          ?.durationMs
      ) {
        return (
          stream.value
            .durationMs
        )
      }

      // A last reaction is not a reliable measure of the full stream length.
      return null
    },
  )

const durationLabel = computed(() =>
  duration.value === null ? '时长暂未提供' : formatTimestamp(duration.value),
)

const halfDurationLabel = computed(() =>
  duration.value === null
    ? '—'
    : formatTimestamp(
      duration.value / 2,
    ),
)

// Only stagger crowded markers vertically; horizontal positions stay stream-global.
const timelineMarkers = computed(() => {
  if (!duration.value) return []
  const laneEnds: number[] = []
  return [...items.value].sort((a, b) => a.anchorMs - b.anchorMs).map((item) => {
    const position = item.anchorMs / duration.value! * 100
    let lane = laneEnds.findIndex((last) => position - last >= 3.6)
    if (lane === -1) lane = laneEnds.length
    laneEnds[lane] = position
    return { item, lane }
  })
})

const trackHeight = computed(() =>
  Math.max(2, ...timelineMarkers.value.map(({ lane }) => lane + 1)) * 28,
)


const importantItems =
  computed(
    () =>
      items.value.filter(
        (item) =>
          isImportant(
            item,
          ),
      ),
  )


function isImportant(
  item: TimelineItem,
): boolean {
  return (
    item.salienceScore
    >= IMPORTANT_THRESHOLD
  )
}


function isSemantic(item: TimelineItem): boolean {
  // Also tolerate responses from older archives that omit semantic fields.
  return Boolean(item.title?.trim())
}

function itemTitle(item: TimelineItem): string {
  return isSemantic(item) ? item.title! : '观众高反应片段'
}

function formatScore(
  value: number,
): string {
  return value.toFixed(3)
}


function timelinePosition(
  value: number,
): string {
  if (
    !duration.value
  ) {
    return '0%'
  }

  const ratio = Math.min(
    1,
    Math.max(
      0,
      value
      / duration.value,
    ),
  )

  return `${ratio * 100}%`
}

function getBilibiliPartNumber(
  item: TimelineItem,
): number | null {
  if (
    item.sourcePartIds.length
    !== 1
  ) {
    return null
  }

  const partId =
    item.sourcePartIds[0]

  const match =
    /^p(\d+)$/.exec(
      partId,
    )

  if (!match) {
    return null
  }

  return (
    Number(match[1])
    + 1
  )
}


function buildBilibiliJumpUrl(
  item: TimelineItem,
): string | undefined {
  if (
    !stream.value
    || stream.value.bvIds.length
    !== 1
  ) {
    return undefined
  }

  const bvId =
    stream.value.bvIds[0]

  const partNumber =
    getBilibiliPartNumber(
      item,
    )

  if (
    !bvId
    || partNumber === null
  ) {
    return undefined
  }

  const seconds =
    Math.floor(
      Math.max(
        0,
        item.localAnchorMs
        - REPLAY_LEAD_MS,
      )
      / 1000,
    )

  const params =
    new URLSearchParams()

  if (
    partNumber > 1
  ) {
    params.set(
      'p',
      String(
        partNumber,
      ),
    )
  }

  params.set(
    't',
    String(seconds),
  )

  return (
    `https://www.bilibili.com/video/${bvId}/?${params.toString()}`
  )
}

function toggleItem(
  itemId: string,
) {
  activeItemId.value =
    activeItemId.value
      === itemId
      ? undefined
      : itemId
}


async function focusItem(
  itemId: string,
) {
  activeItemId.value =
    itemId

  await nextTick()

  const card = document.getElementById(`timeline-${itemId}`)
  card?.focus({ preventScroll: true })
  card?.scrollIntoView({
    behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth',
    block: 'center',
  })
}

let loadVersion = 0

async function loadTimeline() {
  const version = ++loadVersion
  loading.value = true
  error.value = ''
  stream.value = undefined
  timeline.value = undefined
  activeItemId.value = undefined

  try {
    const streamId =
      String(
        route.params
          .streamId,
      )

    const routeVtuberId =
      String(
        route.params
          .vtuberId,
      )

    const [
      streamResult,
      timelineResult,
    ] = await Promise.all([
      getStream(
        streamId,
      ),

      getStreamTimeline(
        streamId,
      ),
    ])

    if (version !== loadVersion) return

    if (!streamResult) {
      throw new Error(
        '未找到该直播档案',
      )
    }

    if (
      streamResult.vtuberId
      !== routeVtuberId
    ) {
      throw new Error(
        'Stream workspace mismatch: '
        + `route="${routeVtuberId}", `
        + `stream="${streamResult.vtuberId}".`,
      )
    }

    if (timelineResult.streamId !== streamId) {
      throw new Error('时间线响应与当前直播不一致，请重试。')
    }

    stream.value =
      streamResult

    timeline.value =
      timelineResult

    activeItemId.value =
      undefined

  } catch (reason) {
    if (version !== loadVersion) return
    stream.value =
      undefined

    timeline.value =
      undefined

    error.value =
      reason instanceof Error
        ? reason.message
        : '无法读取直播时间线'

  } finally {
    if (version === loadVersion) loading.value = false
  }
}

watch(
  () => [route.params.vtuberId, route.params.streamId],
  () => { void loadTimeline() },
  { immediate: true },
)
</script>


<template>
  <main class="
      page
      timeline-page
    ">
    <RouterLink class="back-link" :to="{
      name: 'archive',
      params: {
        vtuberId:
          route.params
            .vtuberId,
      },
    }">
      ← 返回直播档案
    </RouterLink>


    <header v-if="stream" class="
        page-header
        timeline-header
      ">
      <div>
        <span class="eyebrow">
          STREAM TIMELINE /
          {{
            stream.bvIds
              .join(' · ')
          }}
        </span>

        <h1>
          {{ stream.title }}
        </h1>

        <div class="stream-facts">
          <span>
            {{
              formatDateTime(
                stream.liveTime,
              )
            }}
          </span>

          <span>
            {{
              stream.partCount
            }}
            PARTS
          </span>

          <span>
            {{ durationLabel }}
          </span>
        </div>
      </div>

      <div class="archive-stamp">
        <span>
          TIMELINE
        </span>

        <strong>
          STREAM GLOBAL
        </strong>
      </div>
    </header>


    <div v-if="loading" class="page-loading">
      正在构建整场直播时间线…
    </div>


    <p v-else-if="
      error
      || !stream
      || !timeline
    " class="error-banner">
      {{
        error
        || '未找到该直播时间线。'
      }}
    </p>


    <template v-else>
      <section class="
          content-panel
          timeline-overview
        ">
        <div class="
            section-heading
            compact
          ">
          <div>
            <span class="section-index">
              01
            </span>

            <h2>
              直播话题时间轴
            </h2>
          </div>

          <span>
            话题与观众反应片段 · 整场时间
          </span>
        </div>


        <div class="summary-grid">
          <div class="summary-item">
            <span>
              DURATION
            </span>

            <strong>
              {{ durationLabel }}
            </strong>
          </div>

          <div class="summary-item">
            <span>
              PARTS
            </span>

            <strong>
              {{
                stream.partCount
              }}
            </strong>
          </div>

          <div class="summary-item">
            <span>
              TIMELINE ITEMS
            </span>

            <strong>
              {{
                items.length
              }}
            </strong>
          </div>

          <div class="summary-item">
            <span>
              IMPORTANT
            </span>

            <strong>
              {{
                importantItems.length
              }}
            </strong>
          </div>
        </div>


        <div v-if="items.length" class="timeline-map">
          <div class="timeline-track">
            <button v-for="item in items" :key="item.id" type="button" class="timeline-marker" :class="{
              semantic: isSemantic(item),
              fallback: !isSemantic(item),
              important:
                isImportant(
                  item,
                ),
              active:
                activeItemId
                === item.id,
            }" :style="{
              left:
                timelinePosition(
                  item.anchorMs,
                ),
            }" :aria-label="`${formatTimestamp(item.anchorMs)} · ${itemTitle(item)}${isImportant(item) ? ' · 重点' : ''}`"
              :aria-controls="`timeline-${item.id}`"
              :aria-pressed="activeItemId === item.id"
              :title="`${formatTimestamp(item.anchorMs)} · ${itemTitle(item)}`
              " @click="
                focusItem(
                  item.id,
                )
                "></button>
          </div>

          <div class="timeline-axis">
            <span>
              00:00:00
            </span>

            <span>
              {{ halfDurationLabel }}
            </span>

            <span>
              {{ durationLabel }}
            </span>
          </div>

          <div class="timeline-legend">
            <span>
              <i class="semantic"></i>
              话题
            </span>
            <span>
              <i class="fallback"></i>
              观众反应 · 暂无语义
            </span>

            <span>
              <i class="important"></i>
              重点节点
              ≥
              {{
                IMPORTANT_THRESHOLD
              }}
            </span>
          </div>
        </div>
      </section>


      <section class="timeline-section">
        <header class="section-heading">
          <div>
            <span class="section-index">
              02
            </span>

            <h2>
              按时间回顾
            </h2>
          </div>

          <span>
            {{
              items.length
            }}
            个时间线片段 ·
            {{
              importantItems.length
            }}
            个重点
          </span>
        </header>


        <div v-if="items.length" class="timeline-list">
          <article v-for="item in items" :id="`timeline-${item.id}`
            " :key="item.id" class="timeline-card" tabindex="-1" :class="{
              semantic: isSemantic(item),
              fallback: !isSemantic(item),
              important:
                isImportant(
                  item,
                ),
              active:
                activeItemId
                === item.id,
            }">
            <button type="button" class="timeline-main"
              :aria-expanded="activeItemId === item.id"
              :aria-controls="`timeline-detail-${item.id}`" @click="
              toggleItem(
                item.id,
              )
              ">
              <div class="timeline-time">
                <strong class="mono">
                  {{
                    formatTimestamp(
                      item.startMs,
                    )
                  }}
                </strong>

                <span>
                  →
                  {{
                    formatTimestamp(
                      item.endMs,
                    )
                  }}
                </span>
              </div>


              <span class="timeline-copy">
                <span class="timeline-kind">
                  <span class="importance-badge">{{ isSemantic(item) ? '话题' : '观众反应信号' }}</span>
                  <span v-if="isImportant(item)" class="importance-badge strong">重点</span>
                </span>
                <strong class="timeline-title">{{ itemTitle(item) }}</strong>
                <span class="timeline-summary" :class="{ pending: !isSemantic(item) || !item.summary?.trim() }">
                  {{ isSemantic(item) && item.summary?.trim() ? item.summary : '暂未生成语义摘要' }}
                </span>
                <span v-if="isSemantic(item) && (item.keywords?.length || item.entities?.length)" class="semantic-tags">
                  <span v-for="(keyword, index) in item.keywords ?? []" :key="`keyword-${index}`" class="semantic-tag" :title="`关键词：${keyword}`">
                    # {{ keyword }}
                  </span>
                  <span v-for="(entity, index) in item.entities ?? []" :key="`entity-${index}`" class="semantic-tag entity" :title="`实体：${entity}`">
                    <span class="entity-label">实体</span> {{ entity }}
                  </span>
                </span>
                <span class="timeline-meta">
                  <span>显著度 <span class="mono">{{ formatScore(item.salienceScore) }}</span></span>
                  <span>{{ item.evidenceRefs?.length ? `${item.evidenceRefs.length} 条证据引用` : '暂无证据引用' }}</span>
                </span>
              </span>


              <span class="expand-indicator">
                {{
                  activeItemId
                    === item.id
                    ? '−'
                    : '+'
                }}
              </span>
            </button>

            <a v-if="
              buildBilibiliJumpUrl(
                item,
              )
            " class="replay-jump-link" :href="buildBilibiliJumpUrl(
                item,
              )
                " target="_blank" rel="noopener noreferrer">
              空降回放 ↗
            </a>

            <div v-if="
              activeItemId
              === item.id
            " class="timeline-detail" :id="`timeline-detail-${item.id}`">
              <div class="detail-grid">
                <div>
                  <span>
                    定位时间（整场）
                  </span>

                  <strong>
                    {{
                      formatTimestamp(
                        item.anchorMs,
                      )
                    }}
                  </strong>
                </div>

                <div>
                  <span>
                    来源 Part
                  </span>

                  <strong>
                    {{
                      item
                        .sourcePartIds
                        .join(', ')
                    }}
                  </strong>
                </div>

                <div>
                  <span>
                    来源 Highlight Signal
                  </span>

                  <strong>
                    {{
                      item
                        .sourceHighlightIds
                        .length
                    }}
                  </strong>
                </div>

                <div>
                  <span>
                    重点标记
                  </span>

                  <strong>
                    {{
                      isImportant(
                        item,
                      )
                        ? '重点'
                        : '普通'
                    }}
                  </strong>
                </div>
              </div>

              <div v-if="item.evidenceRefs?.length" class="evidence-references">
                <strong>证据引用 · {{ item.evidenceRefs.length }}</strong>
                <ul aria-label="证据引用标识">
                  <li v-for="(reference, index) in item.evidenceRefs" :key="index"><code>{{ reference }}</code></li>
                </ul>
              </div>

              <div class="evidence-note">
                <strong>
                  Evidence boundary
                </strong>

                <p v-if="isSemantic(item)">
                  标题与摘要来自后端语义化结果。证据引用用于追溯来源，不代表内容已经人工核实；可空降回放查看上下文。
                </p>
                <p v-else>
                  当前片段仅表示观众出现较强的集中反应，暂未生成语义摘要，不能据此断言主播具体说了什么或做了什么。
                </p>
              </div>
            </div>
          </article>
        </div>


        <div v-else class="empty-panel">
          该直播已有档案，
          但暂未检测到 Timeline Item。
        </div>
      </section>
    </template>
  </main>
</template>


<style scoped>
.stream-facts {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  margin-top: 14px;

  color: var(--muted);

  font:
    600 .72rem/1 ui-monospace,
    monospace;

  letter-spacing: .07em;
}


.timeline-overview {
  margin-top: 26px;
}


.summary-grid {
  display: grid;

  grid-template-columns:
    repeat(4,
      minmax(0, 1fr));

  border-top:
    1px solid var(--line);
}


.summary-item {
  padding: 22px;

  border-right:
    1px solid var(--line);
}


.summary-item:last-child {
  border-right: 0;
}


.summary-item span {
  display: block;

  color: var(--faint);

  font:
    600 .66rem/1 ui-monospace,
    monospace;

  letter-spacing: .12em;
}


.summary-item strong {
  display: block;
  margin-top: 10px;

  color:
    var(--text-strong);

  font-size: 1.3rem;
}


.timeline-map {
  padding:
    34px 24px 22px;

  border-top:
    1px solid var(--line);
}


.timeline-track {
  position: relative;

  height: 6px;

  background:
    var(--line);

  border-radius:
    999px;
}


.timeline-marker {
  position: absolute;
  top: 50%;

  width: 9px;
  height: 18px;

  padding: 0;

  transform:
    translate(-50%,
      -50%);

  border:
    2px solid var(--surface);

  border-radius:
    999px;

  background:
    var(--muted);

  cursor: pointer;
}


.timeline-marker:hover,
.timeline-marker.active {
  width: 12px;
  height: 24px;

  background:
    var(--accent);
}


.timeline-marker.important {
  width: 12px;
  height: 26px;

  background:
    var(--accent);
}


.timeline-marker.important::after {
  content: '';

  position: absolute;

  inset: -5px;

  border:
    1px solid color-mix(in srgb,
      var(--accent) 45%,
      transparent);

  border-radius:
    999px;
}

.timeline-marker.semantic,
.timeline-legend i.semantic {
  border-radius: 3px;
}

.timeline-marker.fallback,
.timeline-legend i.fallback {
  background: var(--surface);
  border: 2px solid var(--muted);
}

.timeline-marker.fallback.important,
.timeline-marker.fallback.active,
.timeline-marker.fallback:hover {
  border-color: var(--accent);
}

.timeline-marker:focus-visible {
  z-index: 2;
}

.timeline-axis {
  display: flex;

  justify-content:
    space-between;

  margin-top: 14px;

  color:
    var(--faint);

  font:
    .66rem/1 ui-monospace,
    monospace;
}


.timeline-legend {
  display: flex;
  flex-wrap: wrap;

  gap:
    12px 22px;

  margin-top: 22px;

  color:
    var(--muted);

  font-size:
    .72rem;
}


.timeline-legend span {
  display: flex;

  gap: 8px;

  align-items:
    center;
}


.timeline-legend i {
  width: 7px;
  height: 12px;

  border-radius:
    999px;

  background:
    var(--muted);
}


.timeline-legend i.important {
  width: 9px;
  height: 16px;

  background:
    var(--accent);
}


.timeline-section {
  margin-top: 36px;
}


.timeline-list {
  display: grid;
  gap: 10px;
}


.timeline-card {
  scroll-margin-top: 76px;
  overflow: hidden;

  border:
    1px solid var(--line);

  border-radius:
    var(--radius-md);

  background:
    var(--surface-glass);
}


.timeline-card.important {
  border-left:
    3px solid var(--accent);
}


.timeline-card.active {
  border-color:
    color-mix(in srgb,
      var(--accent) 45%,
      var(--line));
}


.timeline-main {
  width: 100%;
  min-height: 84px;

  display: grid;

  grid-template-columns:
    140px minmax(0, 1fr) 32px;

  gap: 20px;

  align-items: start;

  padding:
    15px 20px;

  color:
    var(--text);

  background:
    transparent;

  border: 0;

  text-align: left;

  cursor: pointer;
}


.timeline-main:hover {
  background:
    var(--surface-hover);
}


.timeline-time {
  padding-top: 4px;
  display: grid;

  gap: 5px;
}


.timeline-time strong {
  color:
    var(--text-strong);

  font-size:
    1.08rem;
}


.timeline-time span {
  color:
    var(--muted);

  font-size:
    .72rem;
}


.timeline-kind {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 7px;
}

.timeline-copy {
  display: block;
  min-width: 0;
  overflow-wrap: anywhere;
}

.timeline-title {
  display: block;
  margin-top: 10px;
  color: var(--text-strong);
  font-size: 1.02rem;
  font-weight: 620;
  line-height: 1.55;
}

.timeline-summary {
  display: block;
  margin-top: 7px;
  color: var(--text);
  font-size: .83rem;
  line-height: 1.8;
  white-space: pre-line;
}

.timeline-summary.pending,
.timeline-card.fallback .timeline-title {
  color: var(--muted);
}

.semantic-tags,
.timeline-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px 10px;
  margin-top: 12px;
}

.semantic-tag {
  padding: 3px 7px;
  color: var(--muted);
  background: var(--surface-deep);
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  font-size: .7rem;
  line-height: 1.5;
}

.semantic-tag.entity {
  background: transparent;
}

.entity-label {
  margin-right: 4px;
  color: var(--faint);
  font-size: .62rem;
}

.timeline-meta {
  gap: 8px 18px;
  color: var(--muted);
  font-size: .69rem;
  line-height: 1.5;
}

.evidence-references {
  margin-top: 16px;
  color: var(--muted);
  font-size: .75rem;
  line-height: 1.6;
}

.evidence-references ul {
  display: grid;
  gap: 5px;
  margin: 8px 0 0;
  padding-left: 18px;
}

.evidence-references code {
  font-size: .7rem;
  overflow-wrap: anywhere;
}

.timeline-kind small {
  color:
    var(--faint);

  font:
    .64rem/1 ui-monospace,
    monospace;
}


.importance-badge {
  padding:
    5px 8px;

  color:
    var(--muted);

  background:
    var(--surface-deep);

  border:
    1px solid var(--line);

  border-radius:
    999px;

  font-size:
    .67rem;
}


.importance-badge.strong {
  color:
    var(--accent);

  background:
    var(--accent-soft);

  border-color:
    color-mix(in srgb,
      var(--accent) 35%,
      var(--line));
}


.score-column {
  min-width: 0;
}


.score-header {
  display: flex;

  justify-content:
    space-between;

  gap: 16px;

  color:
    var(--faint);

  font-size:
    .68rem;
}


.score-header strong {
  color:
    var(--accent);
}


.score-track {
  height: 5px;

  margin-top: 10px;

  overflow: hidden;

  background:
    var(--line);

  border-radius:
    999px;
}


.score-track i {
  display: block;

  height: 100%;

  background:
    var(--accent);

  border-radius:
    inherit;
}


.source-count {
  text-align: right;
}


.source-count strong {
  display: block;

  color:
    var(--text-strong);

  font-size:
    1.05rem;
}


.source-count span {
  display: block;

  margin-top: 5px;

  color:
    var(--faint);

  font:
    .62rem/1 ui-monospace,
    monospace;

  letter-spacing:
    .08em;
}


.expand-indicator {
  color:
    var(--accent);

  font-size:
    1.35rem;

  text-align: center;
}

.replay-jump-link {
  display: inline-flex;
  align-items: center;

  margin:
    0 20px 14px;

  padding:
    7px 10px;

  color:
    var(--accent);

  background:
    var(--accent-soft);

  border:
    1px solid
    color-mix(
      in srgb,
      var(--accent) 30%,
      var(--line)
    );

  border-radius:
    999px;

  font-size:
    .72rem;

  text-decoration: none;
}


.replay-jump-link:hover {
  background:
    var(--surface-hover);
}

.timeline-detail {
  padding: 20px;

  border-top:
    1px solid var(--line);

  background:
    var(--surface-deep);
}


.detail-grid {
  display: grid;

  grid-template-columns:
    repeat(4,
      minmax(0, 1fr));

  gap: 10px;
}


.detail-grid>div {
  padding: 14px;

  border:
    1px solid var(--line);

  border-radius:
    var(--radius-sm);

  background:
    var(--surface);
}


.detail-grid span {
  display: block;

  color:
    var(--faint);

  font:
    .62rem/1 ui-monospace,
    monospace;

  letter-spacing:
    .08em;
}


.detail-grid strong {
  display: block;

  margin-top: 8px;

  color:
    var(--text-strong);
}


.evidence-note {
  margin-top: 16px;

  padding: 16px;

  border-left:
    2px solid var(--accent);

  background:
    var(--accent-soft);
}


.evidence-note strong {
  color:
    var(--accent);

  font-size:
    .78rem;
}


.evidence-note p {
  max-width: 820px;

  margin:
    8px 0 0;

  color:
    var(--muted);

  font-size:
    .82rem;

  line-height:
    1.7;
}


@media (max-width: 1000px) {
  .timeline-main {
    grid-template-columns:
      120px minmax(0, 1fr) 24px;

    gap: 12px;
  }
}


@media (max-width: 760px) {

  .summary-grid,
  .detail-grid {
    grid-template-columns:
      repeat(2,
        minmax(0, 1fr));
  }

  .timeline-main {
    grid-template-columns:
      1fr auto;
  }

  .timeline-copy {
    grid-column: 1 / -1;
    grid-row: 2;
  }

  .expand-indicator {
    grid-column: 2;
    grid-row: 1;
  }
}
</style>
