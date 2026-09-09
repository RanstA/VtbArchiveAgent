import { request, useMockApi } from './client'
import { mockRequest } from '@/mock/adapter'
import { mockEvents, mockEvidence, mockStreams } from '@/mock/data'
import type { InvestigationResult } from '@/types'

export async function investigate(query: string): Promise<InvestigationResult> {
  if (!useMockApi) {
    return request<InvestigationResult>('/investigate', {
      method: 'POST',
      body: JSON.stringify({ query }),
    })
  }

  const selectedEvents = [mockEvents[0], mockEvents[2]]
  const candidates = selectedEvents.map((event) => ({
    event,
    stream: mockStreams.find((stream) => stream.id === event.streamId)!,
    evidence: mockEvidence.filter((item) => item.eventId === event.id),
    confidence: event.confidence,
  }))

  return mockRequest({
    query,
    trace: [
      { id: 'trace-1', label: '正在搜索相关直播', detail: '标题、时间范围与档案元数据', status: 'done' },
      { id: 'trace-2', label: '找到 5 个候选事件', detail: '按关键词与话题相关度排序', status: 'done' },
      { id: 'trace-3', label: '正在展开上下文', detail: '检查候选前后 3 分钟窗口', status: 'done' },
      { id: 'trace-4', label: '整理证据层级', detail: '保留 2 个具备可解释证据的事件', status: 'done' },
    ],
    candidates,
  }, 900)
}
