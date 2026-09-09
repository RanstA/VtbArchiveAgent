import { request, useMockApi } from './client'
import { mockRequest } from '@/mock/adapter'
import { mockEvents, mockStreams } from '@/mock/data'
import type { EventSearchParams, EventSearchResult } from '@/types'

export async function searchEvents(params: EventSearchParams): Promise<EventSearchResult[]> {
  if (!useMockApi) {
    const search = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value && value !== 'all') search.set(key, value)
    })
    const suffix = search.size ? `?${search.toString()}` : ''
    return request<EventSearchResult[]>(`/events/search${suffix}`)
  }

  const query = params.query.trim().toLocaleLowerCase()
  const results = mockEvents.flatMap((event) => {
    const stream = mockStreams.find((item) => item.id === event.streamId)
    if (!stream) return []

    const searchable = `${event.title} ${event.summary} ${event.eventType} ${stream.title}`.toLocaleLowerCase()
    const matchesQuery = !query || searchable.includes(query)
    const liveDate = stream.liveTime.slice(0, 10)
    const matchesFrom = !params.from || liveDate >= params.from
    const matchesTo = !params.to || liveDate <= params.to
    const matchesTopic = !params.topic || params.topic === 'all' || searchable.includes(params.topic.toLocaleLowerCase())

    return matchesQuery && matchesFrom && matchesTo && matchesTopic
      ? [{ event, stream, matchedText: event.summary }]
      : []
  })

  return mockRequest(results, 260)
}
