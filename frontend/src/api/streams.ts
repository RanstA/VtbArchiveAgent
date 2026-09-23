import {
  request,
  useMockApi,
} from './client'

import {
  mockRequest,
} from '@/mock/adapter'

import {
  mockStreams,
} from '@/mock/data'

import type {
  DetectedHighlight,
  Stream,
  StreamDetail,
} from '@/types'


export interface StreamListParams {
  vtuberId: string

  query?: string

  status?:
    | 'all'
    | 'danmaku'
    | 'highlights'
    | 'pending'
}


function normalizeMockStream(
  stream: Stream,
): Stream {
  const hasHighlights =
    stream.hasHighlights
    ?? stream.hasEvents
    ?? false

  return {
    ...stream,

    hasHighlights,

    highlightCount:
      stream.highlightCount
      ?? (
        hasHighlights
          ? 1
          : 0
      ),
  }
}


export async function getStreams(
  params: StreamListParams,
): Promise<Stream[]> {
  if (!useMockApi) {
    const search =
      new URLSearchParams()

    search.set(
      'vtuber_id',
      params.vtuberId,
    )

    if (params.query) {
      search.set(
        'query',
        params.query,
      )
    }

    if (
      params.status
      && params.status !== 'all'
    ) {
      search.set(
        'status',
        params.status,
      )
    }

    return request<Stream[]>(
      `/streams?${search.toString()}`,
    )
  }

  const query =
    params.query
      ?.trim()
      .toLocaleLowerCase()

  const normalized =
    mockStreams.map(
      normalizeMockStream,
    )

  const result =
    normalized.filter(
      (stream) => {
        const matchesVtuber =
          stream.vtuberId
          === params.vtuberId

        const matchesQuery =
          !query
          || stream.title
            .toLocaleLowerCase()
            .includes(query)
          || stream.bvIds.some(
            (bv) =>
              bv
                .toLocaleLowerCase()
                .includes(query),
          )

        const hasHighlights =
          stream.hasHighlights
          ?? false

        const matchesStatus =
          !params.status
          || params.status
            === 'all'
          || (
            params.status
              === 'danmaku'
            && stream.hasDanmaku
          )
          || (
            params.status
              === 'highlights'
            && hasHighlights
          )
          || (
            params.status
              === 'pending'
            && !hasHighlights
          )

        return (
          matchesVtuber
          && matchesQuery
          && matchesStatus
        )
      },
    )

  return mockRequest(
    result,
  )
}


export async function getStream(
  id: string,
): Promise<
  StreamDetail | undefined
> {
  if (!useMockApi) {
    return request<StreamDetail>(
      `/streams/${id}`,
    )
  }

  const stream =
    mockStreams.find(
      (item) =>
        item.id === id,
    )

  if (!stream) {
    return mockRequest(
      undefined,
    )
  }

  return mockRequest({
    ...normalizeMockStream(
      stream,
    ),

    partCount: 1,
  })
}


export async function getStreamHighlights(
  id: string,
): Promise<
  DetectedHighlight[]
> {
  if (!useMockApi) {
    return request<
      DetectedHighlight[]
    >(
      `/streams/${id}/highlights`,
    )
  }

  /**
   * 当前 mockHighlights 还是旧
   * Event-based HighlightCandidate。
   *
   * 不强行把两个模型混在一起。
   * 真实 Highlight Timeline
   * 只在 real API 模式工作。
   */
  return mockRequest(
    [],
  )
}