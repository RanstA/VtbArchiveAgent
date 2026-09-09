import { request, useMockApi } from './client'
import { mockRequest } from '@/mock/adapter'
import { mockEvents, mockEvidence } from '@/mock/data'
import type { Event, Evidence } from '@/types'

export async function getStreamEvents(streamId: string): Promise<Event[]> {
  if (!useMockApi) return request<Event[]>(`/streams/${streamId}/events`)
  return mockRequest(mockEvents.filter((event) => event.streamId === streamId))
}

export async function getEventEvidence(eventId: string): Promise<Evidence[]> {
  if (!useMockApi) return request<Evidence[]>(`/events/${eventId}/evidence`)
  return mockRequest(mockEvidence.filter((item) => item.eventId === eventId), 100)
}
