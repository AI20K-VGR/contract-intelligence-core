import {
  getContractGraphPage,
  getProcessingTrace,
  type ContractGraphKind,
  type ContractGraphPage,
  type ProcessingTrace,
} from '../../api/contractGraph'

type GraphReadInput = {
  enabled: boolean
  visible: boolean
  dossierId: string
  jobId: string
  snapshotDigest: string
  graphKind: ContractGraphKind
  signal?: AbortSignal
}

export function createLatestRequestGuard() {
  let currentRequest = 0
  return {
    start: () => ++currentRequest,
    isCurrent: (requestId: number) => requestId === currentRequest,
    invalidate: () => {
      currentRequest += 1
    },
  }
}

export function citationFallbackMatchesDocument(
  sourceDocumentId: string | null | undefined,
  selectedDocumentId: string | null | undefined,
): boolean {
  return Boolean(
    sourceDocumentId &&
    selectedDocumentId &&
    sourceDocumentId === selectedDocumentId,
  )
}

export function isLegacyCitationFallbackAllowed(
  citationRef: string,
  responseStatus: number | null,
  sourceDocumentId: string | null | undefined,
  selectedDocumentId: string | null | undefined,
): boolean {
  return (
    citationRef.startsWith('cite:') &&
    responseStatus === 404 &&
    citationFallbackMatchesDocument(sourceDocumentId, selectedDocumentId)
  )
}

export async function loadAi2GraphDataIfVisible(
  input: GraphReadInput,
): Promise<{
  page: ContractGraphPage | null
  trace: ProcessingTrace
  graphError: boolean
} | null> {
  if (!input.enabled || !input.visible) return null
  if (!input.dossierId || !input.jobId || !input.snapshotDigest) return null
  const [pageResult, traceResult] = await Promise.allSettled([
    getContractGraphPage({
      dossierId: input.dossierId,
      jobId: input.jobId,
      snapshotDigest: input.snapshotDigest,
      graphKind: input.graphKind,
      signal: input.signal,
    }),
    getProcessingTrace({
      dossierId: input.dossierId,
      jobId: input.jobId,
      snapshotDigest: input.snapshotDigest,
      signal: input.signal,
    }),
  ])
  const page = pageResult.status === 'fulfilled' ? pageResult.value : null
  const trace: ProcessingTrace =
    traceResult.status === 'fulfilled'
      ? traceResult.value
      : {
          job_id: input.jobId,
          snapshot_digest: input.snapshotDigest,
          status: 'TRACE_UNAVAILABLE',
          trace_status: 'UNAVAILABLE',
          stages: [],
        }
  return { page, trace, graphError: page === null }
}

export const AI2_GRAPH_UI_ENABLED = true
