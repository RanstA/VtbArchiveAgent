import { request } from './client'

export interface Vtuber {
  id: string
  displayName: string
}

export async function getVtubers(): Promise<Vtuber[]> {
  return request<Vtuber[]>('/vtubers')
}