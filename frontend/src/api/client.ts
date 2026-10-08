const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api'

// Real FastAPI is the default; legacy demos must explicitly opt into Mock.
export const useMockApi = import.meta.env.VITE_USE_MOCK_API === 'true'

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })

  if (!response.ok) {
    let message = `API request failed: ${response.status}`
    try {
      const body: unknown = await response.json()
      if (body && typeof body === 'object' && 'detail' in body) {
        const detail = body.detail
        if (typeof detail === 'string') message = detail
        else if (detail && typeof detail === 'object' && 'message' in detail && typeof detail.message === 'string') {
          message = detail.message
        } else if (Array.isArray(detail)) {
          message = '请求参数无效，请检查主播和问题内容。'
        }
      }
    } catch {
      // A proxy may return HTML/empty errors; preserve the HTTP failure.
    }
    throw new Error(message)
  }

  return response.json() as Promise<T>
}
