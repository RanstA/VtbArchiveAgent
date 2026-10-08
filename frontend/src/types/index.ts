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

export type TopicType =
  | 'talk'
  | 'interaction'
  | 'singing'
  | 'gameplay'
  | 'reaction'
  | 'announcement'

export interface TimelineItem {
  id: string

  streamId: string

  sourcePartIds: string[]

  startMs: number
  endMs: number
  anchorMs: number
  localAnchorMs: number

  salienceScore: number
  topicType: TopicType | null

  /** Null title identifies a Highlight fallback, without semantic claims. */
  title: string | null
  summary: string | null
  keywords: string[]
  entities: string[]
  /** Opaque references; may include highlight:, danmaku:, asr:, vlm:, etc. */
  evidenceRefs: string[]

  sourceHighlightIds: string[]
}


export interface StreamTimeline {
  streamId: string

  durationMs: number | null

  mergeGapMs: number

  items: TimelineItem[]
}

export interface TopicSearchParams {
  query: string
  vtuberId?: string
  limit?: number
}

export interface SearchHit {
  streamId: string
  topicSegmentId: string | null
  /** Topic positions use the Stream-global timeline. */
  startMs: number | null
  endMs: number | null
  title: string
  snippet: string
  score: number
  evidenceIds: string[] | null
}

export interface TopicSegment {
  id: string
  streamId: string
  sourcePartIds: string[]
  reactionMatchIds: string[]
  /** Topic positions use the Stream-global timeline. */
  startMs: number
  endMs: number
  title: string
  summary: string
  keywords: string[]
  entities: string[]
  transcriptSegmentIds: string[]
  salienceScore: number
  confidence: number
  analyzerVersion: string
  topicType: TopicType
}

export interface TranscriptSegment {
  id: string
  streamId: string
  partId: string
  /** Evidence positions stay Part-local. */
  startMs: number
  endMs: number
  rawText: string
  text: string
  source: string
}

export interface Danmaku {
  id: number
  streamId: string
  partId: string
  /** Evidence positions stay Part-local. */
  timestampMs: number
  rawText: string
  text: string
}

export interface TopicEvidenceBundle {
  topic: TopicSegment
  transcripts: TranscriptSegment[]
  danmaku: Danmaku[]
}

/**
 * 下面是旧 Event frontend model。
 *
 * 暂时保留给：
 *
 * Legacy SearchEventRow
 * Highlights legacy page
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

export type ResearchEvidenceKind = 'speech' | 'audience_reaction' | 'archived_interpretation'

export interface ResearchCitation {
  evidenceRef: string
  quote: string
}

export interface ResearchFinding {
  kind: ResearchEvidenceKind
  statement: string
  evidenceRefs: string[]
  citations: ResearchCitation[]
}

export interface ResearchLocation {
  evidenceRef: string
  streamId: string
  sourcePartIds: string[]
  /** Topics may span Parts; never invent a single Part-local range. */
  partId: string | null
  localStartMs: number | null
  localEndMs: number | null
  streamStartMs: number
  streamEndMs: number | null
}

export interface ResearchReport {
  query: string
  vtuberId: string
  searchTerms: string[]
  answer: string
  findings: ResearchFinding[]
  evidenceRefs: string[]
  locations: ResearchLocation[]
  limitations: string[]
}
