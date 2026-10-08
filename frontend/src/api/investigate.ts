import { request } from './client'
import type { ResearchReport } from '@/types'

export function investigate(vtuberId: string, query: string, signal?: AbortSignal): Promise<ResearchReport> {
  return request<ResearchReport>('/investigate/research', {
    method: 'POST',
    body: JSON.stringify({ vtuberId, query }),
    signal,
  })
}
