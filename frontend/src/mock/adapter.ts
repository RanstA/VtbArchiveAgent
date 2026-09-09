const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T

export async function mockRequest<T>(value: T, delay = 180): Promise<T> {
  await new Promise((resolve) => window.setTimeout(resolve, delay))
  return clone(value)
}
