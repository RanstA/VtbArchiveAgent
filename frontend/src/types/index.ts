export interface Stream {
  id: string

  vtuberId: string
  vtuberName: string

  title: string
  liveTime: string
  bvIds: string[]

  hasDanmaku: boolean

  /**
   * 当前真实后端字段。
   */
  hasHighlights?: boolean
  highlightCount?: number

  /**
   * 旧 mock / Event UI 暂时保留。
   * 后续迁移 Search / Investigate 时删除。
   */
  hasEvents?: boolean

  durationMs?: number | null
}

export interface StreamDetail
  extends Stream {
  partCount: number
}

export interface DetectedHighlight {
  id: string

  streamId: string
  partId: string

  startMs: number
  endMs: number
  peakMs: number

  score: number

  densityScore: number
  repetitionScore: number
  reactionScore: number

  danmakuCount: number
  uniqueTextCount: number

  repetitionRatio: number
  reactionRatio: number

  laughCount: number
  questionCount: number
  exclamationCount: number

  detectorVersion: string
}


/**
 * 下面是旧 Event frontend model。
 *
 * 暂时保留给：
 *
 * Search
 * Highlights legacy page
 * Investigate mock
 *
 * 不再用于 Stream Timeline。
 */
export type EventType =
  | 'talk'
  | 'gameplay'
  | 'reaction'
  | 'announcement'
  | 'collab'

export interface Event {
  id: string
  streamId: string
  startMs: number
  endMs: number
  title: string
  summary: string
  eventType: EventType
  confidence: number
}

export type EvidenceLevel =
  | 'E0_METADATA'
  | 'E1_AUDIENCE_REACTION'
  | 'E2_EVENT_INFERENCE'
  | 'E3_ASR_SUBTITLE'
  | 'E4_VIDEO_VLM'
  | 'E5_HUMAN_VERIFIED'

export interface Evidence {
  id: string
  eventId: string
  level: EvidenceLevel
  source: string
  content: string
  timestampMs: number
}

export type ReviewStatus =
  | 'pending'
  | 'approved'
  | 'rejected'

export interface HighlightCandidate {
  event: Event
  score: number
  reason: string
  reviewStatus: ReviewStatus
}

export interface EventSearchParams {
  query: string
  from?: string
  to?: string
  person?: string
  topic?: string
}

export interface EventSearchResult {
  event: Event
  stream: Stream
  matchedText?: string
}

export type AgentTraceStatus =
  | 'done'
  | 'active'
  | 'pending'

export interface AgentTraceStep {
  id: string
  label: string
  detail?: string
  status: AgentTraceStatus
}

export interface InvestigationResult {
  query: string

  trace: AgentTraceStep[]

  candidates: Array<{
    event: Event
    stream: Stream
    evidence: Evidence[]
    confidence: number
  }>
}