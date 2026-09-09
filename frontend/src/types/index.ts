export interface Stream {
  id: string
  title: string
  liveTime: string
  bvId: string
  hasDanmaku: boolean
  hasEvents: boolean
  durationMs?: number
}

export type EventType = 'talk' | 'gameplay' | 'reaction' | 'announcement' | 'collab'

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

export type EvidenceLevel = 'direct' | 'corroborating' | 'contextual'

export interface Evidence {
  id: string
  eventId: string
  level: EvidenceLevel
  source: string
  content: string
  timestampMs: number
}

export type ReviewStatus = 'pending' | 'approved' | 'rejected'

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

export type AgentTraceStatus = 'done' | 'active' | 'pending'

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
