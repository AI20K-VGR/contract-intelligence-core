/**
 * HTTP client stub. Point at the backend in a later ticket.
 * ST-006 does not call APIs or render HITL screens.
 */
export const apiBaseUrl =
  import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8080'

export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`)
  if (!response.ok) {
    throw new Error(`API ${response.status} ${path}`)
  }
  return response.json() as Promise<T>
}
