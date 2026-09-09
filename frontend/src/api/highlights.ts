import { request, useMockApi } from './client'
import { mockRequest } from '@/mock/adapter'
import { mockHighlights } from '@/mock/data'
import type { HighlightCandidate } from '@/types'

export async function getHighlightCandidates(): Promise<HighlightCandidate[]> {
  if (!useMockApi) return request<HighlightCandidate[]>('/highlights')
  return mockRequest(mockHighlights, 240)
}
