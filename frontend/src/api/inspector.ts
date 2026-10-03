import { requestJson } from './client'

export type InspectorKind = 'fact' | 'citation' | 'finding'

const PATHS: Record<InspectorKind, string> = {
  fact: 'facts',
  citation: 'citations',
  finding: 'findings',
}

/** GET /facts/{id}, /citations/{id}, /findings/{id}: chi tiết một bản ghi. */
export async function getInspectorRecord(
  kind: InspectorKind,
  id: string,
  signal?: AbortSignal,
): Promise<Record<string, unknown>> {
  const { data } = await requestJson<unknown>(
    `/api/v1/${PATHS[kind]}/${encodeURIComponent(id)}`,
    { signal },
  )
  return data && typeof data === 'object' && !Array.isArray(data)
    ? (data as Record<string, unknown>)
    : {}
}
