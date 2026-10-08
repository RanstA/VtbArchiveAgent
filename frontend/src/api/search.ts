import { request } from './client'
import type { SearchHit, TopicEvidenceBundle, TopicSearchParams } from '@/types'

export async function searchTopics(
  params: TopicSearchParams,
  signal?: AbortSignal,
): Promise<SearchHit[]> {
  const query = params.query.trim()
  if (!query) return []

  const search = new URLSearchParams({ q: query, limit: String(params.limit ?? 5) })
  if (params.vtuberId) search.set('vtuber_id', params.vtuberId)

  return request<SearchHit[]>(`/search/topics?${search.toString()}`, { signal })
}

export async function getTopicEvidence(
  topicSegmentId: string,
  signal?: AbortSignal,
): Promise<TopicEvidenceBundle> {
  return request<TopicEvidenceBundle>(
    `/search/topics/${encodeURIComponent(topicSegmentId)}/evidence`,
    { signal },
  )
}
