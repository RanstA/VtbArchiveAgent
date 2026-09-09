import { request } from './client'

export interface HealthResponse {
  status: string
}

export const getBackendHealth = () => request<HealthResponse>('/health')
