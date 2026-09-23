<script setup lang="ts">
import {
  computed,
  onMounted,
  ref,
  watch,
} from 'vue'

import {
  useRoute,
} from 'vue-router'

import {
  getStream,
  getStreamHighlights,
} from '@/api/streams'

import type {
  DetectedHighlight,
  StreamDetail,
} from '@/types'

import {
  formatDateTime,
  formatTimestamp,
} from '@/utils/time'


const route =
  useRoute()

const stream =
  ref<
    StreamDetail
    | undefined
  >()

const highlights =
  ref<
    DetectedHighlight[]
  >([])

const activeHighlightId =
  ref<
    string
    | undefined
  >()

const loading =
  ref(true)

const error =
  ref('')


const duration =
  computed(
    () => {
      if (
        stream.value
          ?.durationMs
      ) {
        return (
          stream.value
            .durationMs
        )
      }

      return Math.max(
        ...highlights.value.map(
          (item) =>
            item.endMs,
        ),
        1,
      )
    },
  )


const sortedHighlights =
  computed(
    () =>
      [...highlights.value]
        .sort(
          (
            first,
            second,
          ) => {
            const partCompare =
              first.partId
                .localeCompare(
                  second.partId,
                  undefined,
                  {
                    numeric: true,
                  },
                )

            if (
              partCompare
              !== 0
            ) {
              return partCompare
            }

            return (
              first.startMs
              - second.startMs
            )
          },
        ),
  )


function formatScore(
  value: number,
): string {
  return (
    value
      .toFixed(3)
  )
}


function percent(
  value: number,
): string {
  return (
    `${Math.round(
      value * 100,
    )}%`
  )
}


function toggleHighlight(
  highlightId: string,
) {
  activeHighlightId.value =
    activeHighlightId.value
      === highlightId
      ? undefined
      : highlightId
}


async function loadTimeline() {
  loading.value = true
  error.value = ''

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
      highlightResults,
    ] = await Promise.all([
      getStream(
        streamId,
      ),

      getStreamHighlights(
        streamId,
      ),
    ])

    if (!streamResult) {
      throw new Error(
        '未找到该直播档案',
      )
    }

    /**
     * URL workspace 与 Stream owner
     * 必须一致。
     *
     * 不允许：
     *
     * /v/aza/streams/<mikoto-stream>
     *
     * 静默展示跨 VTuber 数据。
     */
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

    stream.value =
      streamResult

    highlights.value =
      highlightResults

    activeHighlightId.value =
      undefined

  } catch (reason) {
    stream.value =
      undefined

    highlights.value = []

    error.value =
      reason instanceof Error
        ? reason.message
        : '无法读取直播时间线'

  } finally {
    loading.value = false
  }
}


onMounted(
  loadTimeline,
)


watch(
  () =>
    route.params
      .streamId,

  () => {
    void loadTimeline()
  },
)
</script>


<template>
  <main
    class="
      page
      timeline-page
    "
  >
    <RouterLink
      class="back-link"
      :to="{
        name: 'archive',
        params: {
          vtuberId:
            route.params
              .vtuberId,
        },
      }"
    >
      ← 返回直播档案
    </RouterLink>


    <header
      v-if="stream"
      class="
        page-header
        timeline-header
      "
    >
      <div>
        <span
          class="eyebrow"
        >
          STREAM ARCHIVE /
          {{
            stream.bvIds
              .join(' · ')
          }}
        </span>

        <h1>
          {{ stream.title }}
        </h1>

        <div
          class="stream-facts"
        >
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
            {{
              highlights.length
            }}
            HIGHLIGHTS
          </span>
        </div>
      </div>

      <div
        class="archive-stamp"
      >
        <span>
          AUDIENCE SIGNAL
        </span>

        <strong>
          {{
            stream.hasDanmaku
              ? 'DANMAKU READY'
              : 'NO DANMAKU'
          }}
        </strong>
      </div>
    </header>


    <div
      v-if="loading"
      class="page-loading"
    >
      正在读取真实直播档案…
    </div>


    <p
      v-else-if="
        error
        || !stream
      "
      class="error-banner"
    >
      {{
        error
        || '未找到该直播档案。'
      }}
    </p>


    <template
      v-else
    >
      <section
        class="
          content-panel
          highlight-overview
        "
      >
        <div
          class="
            section-heading
            compact
          "
        >
          <div>
            <span
              class="section-index"
            >
              01
            </span>

            <h2>
              Archive Summary
            </h2>
          </div>

          <span>
            Highlight 是观众反应锚点，
            不是主播事实。
          </span>
        </div>

        <div
          class="summary-grid"
        >
          <div
            class="summary-item"
          >
            <span>
              PARTS
            </span>

            <strong>
              {{
                stream.partCount
              }}
            </strong>
          </div>

          <div
            class="summary-item"
          >
            <span>
              DANMAKU
            </span>

            <strong>
              {{
                stream.hasDanmaku
                  ? 'READY'
                  : 'MISSING'
              }}
            </strong>
          </div>

          <div
            class="summary-item"
          >
            <span>
              HIGHLIGHTS
            </span>

            <strong>
              {{
                highlights.length
              }}
            </strong>
          </div>

          <div
            class="summary-item"
          >
            <span>
              DETECTOR
            </span>

            <strong>
              {{
                highlights[0]
                  ?.detectorVersion
                ?? '—'
              }}
            </strong>
          </div>
        </div>
      </section>


      <section
        class="
          highlight-section
        "
      >
        <header
          class="section-heading"
        >
          <div>
            <span
              class="section-index"
            >
              02
            </span>

            <h2>
              Highlight Timeline
            </h2>
          </div>

          <span>
            {{
              highlights.length
            }}
            个观众反应高峰
          </span>
        </header>


        <div
          v-if="
            sortedHighlights
              .length
          "
          class="highlight-list"
        >
          <article
            v-for="
              highlight
              in sortedHighlights
            "
            :id="
              highlight.id
            "
            :key="
              highlight.id
            "
            class="
              highlight-card
            "
            :class="{
              active:
                activeHighlightId
                === highlight.id,
            }"
          >
            <button
              class="
                highlight-main
              "
              type="button"
              @click="
                toggleHighlight(
                  highlight.id,
                )
              "
            >
              <div
                class="
                  highlight-time
                "
              >
                <span
                  class="
                    part-label
                    mono
                  "
                >
                  {{
                    highlight.partId
                  }}
                </span>

                <strong
                  class="mono"
                >
                  {{
                    formatTimestamp(
                      highlight
                        .startMs,
                    )
                  }}
                </strong>

                <span>
                  →
                  {{
                    formatTimestamp(
                      highlight
                        .endMs,
                    )
                  }}
                </span>
              </div>


              <div
                class="
                  score-column
                "
              >
                <div
                  class="
                    score-header
                  "
                >
                  <span>
                    SIGNAL SCORE
                  </span>

                  <strong
                    class="mono"
                  >
                    {{
                      formatScore(
                        highlight
                          .score,
                      )
                    }}
                  </strong>
                </div>

                <div
                  class="
                    score-track
                  "
                >
                  <i
                    :style="{
                      width:
                        percent(
                          highlight
                            .score,
                        ),
                    }"
                  ></i>
                </div>
              </div>


              <div
                class="
                  highlight-count
                "
              >
                <strong>
                  {{
                    highlight
                      .danmakuCount
                  }}
                </strong>

                <span>
                  DANMAKU
                </span>
              </div>


              <span
                class="
                  expand-indicator
                "
              >
                {{
                  activeHighlightId
                    === highlight.id
                    ? '−'
                    : '+'
                }}
              </span>
            </button>


            <div
              v-if="
                activeHighlightId
                === highlight.id
              "
              class="
                highlight-detail
              "
            >
              <div
                class="
                  metric-grid
                "
              >
                <div>
                  <span>
                    DENSITY
                  </span>

                  <strong>
                    {{
                      formatScore(
                        highlight
                          .densityScore,
                      )
                    }}
                  </strong>
                </div>

                <div>
                  <span>
                    REPETITION
                  </span>

                  <strong>
                    {{
                      formatScore(
                        highlight
                          .repetitionScore,
                      )
                    }}
                  </strong>
                </div>

                <div>
                  <span>
                    REACTION
                  </span>

                  <strong>
                    {{
                      formatScore(
                        highlight
                          .reactionScore,
                      )
                    }}
                  </strong>
                </div>

                <div>
                  <span>
                    UNIQUE TEXT
                  </span>

                  <strong>
                    {{
                      highlight
                        .uniqueTextCount
                    }}
                  </strong>
                </div>
              </div>


              <div
                class="
                  evidence-note
                "
              >
                <strong>
                  Evidence boundary
                </strong>

                <p>
                  当前只能确认这里出现了明显的
                  观众集中反应。
                  在获得 ASR 或其他高等级证据前，
                  系统不能据此断言主播当时具体
                  说了什么或做了什么。
                </p>
              </div>


              <div
                class="
                  raw-stats
                "
              >
                <span>
                  peak
                  <b>
                    {{
                      formatTimestamp(
                        highlight
                          .peakMs,
                      )
                    }}
                  </b>
                </span>

                <span>
                  repeat ratio
                  <b>
                    {{
                      percent(
                        highlight
                          .repetitionRatio,
                      )
                    }}
                  </b>
                </span>

                <span>
                  reaction ratio
                  <b>
                    {{
                      percent(
                        highlight
                          .reactionRatio,
                      )
                    }}
                  </b>
                </span>

                <span>
                  laugh
                  <b>
                    {{
                      highlight
                        .laughCount
                    }}
                  </b>
                </span>

                <span>
                  question
                  <b>
                    {{
                      highlight
                        .questionCount
                    }}
                  </b>
                </span>

                <span>
                  exclamation
                  <b>
                    {{
                      highlight
                        .exclamationCount
                    }}
                  </b>
                </span>
              </div>
            </div>
          </article>
        </div>


        <div
          v-else
          class="
            empty-panel
          "
        >
          该直播已有档案，
          但尚未生成 Highlight。
        </div>
      </section>
    </template>
  </main>
</template>


<style scoped>
.stream-facts {
  display: flex;
  gap: 18px;
  margin-top: 14px;
  color: var(--muted);
  font:
    600 .72rem/1
    ui-monospace,
    monospace;
  letter-spacing: .07em;
}

.highlight-overview {
  margin-top: 26px;
}

.summary-grid {
  display: grid;
  grid-template-columns:
    repeat(
      4,
      minmax(0, 1fr)
    );
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
    600 .66rem/1
    ui-monospace,
    monospace;
  letter-spacing: .12em;
}

.summary-item strong {
  display: block;
  margin-top: 10px;
  color: var(--text-strong);
  font-size: 1.3rem;
}


.highlight-section {
  margin-top: 36px;
}

.highlight-list {
  display: grid;
  gap: 10px;
}

.highlight-card {
  overflow: hidden;
  border:
    1px solid var(--line);
  border-radius:
    var(--radius-md);
  background:
    var(--surface-glass);
}

.highlight-card.active {
  border-color:
    color-mix(
      in srgb,
      var(--accent) 45%,
      var(--line)
    );
}

.highlight-main {
  width: 100%;
  min-height: 86px;

  display: grid;
  grid-template-columns:
    220px
    minmax(260px, 1fr)
    110px
    32px;

  gap: 22px;
  align-items: center;

  padding:
    16px 20px;

  color:
    var(--text);

  background:
    transparent;

  border: 0;

  text-align: left;
  cursor: pointer;
}

.highlight-main:hover {
  background:
    var(--surface-hover);
}

.highlight-time {
  display: grid;
  grid-template-columns:
    auto 1fr;

  gap: 5px 12px;
  align-items: center;
}

.highlight-time strong {
  color:
    var(--text-strong);

  font-size:
    1.1rem;
}

.highlight-time > span:last-child {
  grid-column: 2;
  color:
    var(--muted);

  font-size:
    .75rem;
}

.part-label {
  grid-row:
    1 / span 2;

  padding:
    6px 8px;

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
    6px;
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

.highlight-count {
  text-align: right;
}

.highlight-count strong {
  display: block;

  color:
    var(--text-strong);

  font-size:
    1.05rem;
}

.highlight-count span {
  display: block;

  margin-top: 5px;

  color:
    var(--faint);

  font:
    .62rem/1
    ui-monospace,
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

.highlight-detail {
  padding:
    20px;

  border-top:
    1px solid var(--line);

  background:
    var(--surface-deep);
}

.metric-grid {
  display: grid;

  grid-template-columns:
    repeat(
      4,
      minmax(0, 1fr)
    );

  gap: 10px;
}

.metric-grid > div {
  padding:
    14px;

  border:
    1px solid var(--line);

  border-radius:
    var(--radius-sm);

  background:
    var(--surface);
}

.metric-grid span {
  display: block;

  color:
    var(--faint);

  font:
    .62rem/1
    ui-monospace,
    monospace;

  letter-spacing:
    .08em;
}

.metric-grid strong {
  display: block;

  margin-top:
    8px;

  color:
    var(--text-strong);
}

.evidence-note {
  margin-top:
    16px;

  padding:
    16px;

  border-left:
    2px solid
    var(--accent);

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
  max-width:
    780px;

  margin:
    8px 0 0;

  color:
    var(--muted);

  font-size:
    .82rem;

  line-height:
    1.7;
}

.raw-stats {
  display: flex;
  flex-wrap: wrap;

  gap:
    8px 18px;

  margin-top:
    16px;

  color:
    var(--faint);

  font:
    .68rem/1.5
    ui-monospace,
    monospace;
}

.raw-stats b {
  margin-left:
    5px;

  color:
    var(--text);

  font-weight:
    600;
}
</style>