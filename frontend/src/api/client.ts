const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'

export const useMockApi = import.meta.env.VITE_USE_MOCK_API !== 'false'

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`)
  }

  return response.json() as Promise<T>
}
