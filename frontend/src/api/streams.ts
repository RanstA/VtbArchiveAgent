import { request, useMockApi } from './client'
import { mockRequest } from '@/mock/adapter'
import { mockStreams } from '@/mock/data'
import type { Stream } from '@/types'

export interface StreamListParams {
  query?: string
  status?: 'all' | 'danmaku' | 'events' | 'pending'
}

export async function getStreams(params: StreamListParams = {}): Promise<Stream[]> {
  if (!useMockApi) {
    const search = new URLSearchParams()
    if (params.query) search.set('query', params.query)
    if (params.status && params.status !== 'all') search.set('status', params.status)
    const suffix = search.size ? `?${search.toString()}` : ''
    return request<Stream[]>(`/streams${suffix}`)
  }

  const query = params.query?.trim().toLocaleLowerCase()
  const result = mockStreams.filter((stream) => {
    const matchesQuery = !query
      || stream.title.toLocaleLowerCase().includes(query)
      || stream.bvIds.some((bv) => bv.toLocaleLowerCase().includes(query))
    const matchesStatus = !params.status || params.status === 'all'
      || (params.status === 'danmaku' && stream.hasDanmaku)
      || (params.status === 'events' && stream.hasEvents)
      || (params.status === 'pending' && !stream.hasEvents)
    return matchesQuery && matchesStatus
  })
  return mockRequest(result)
}

export async function getStream(id: string): Promise<Stream | undefined> {
  if (!useMockApi) return request<Stream>(`/streams/${id}`)
  return mockRequest(mockStreams.find((stream) => stream.id === id))
}
