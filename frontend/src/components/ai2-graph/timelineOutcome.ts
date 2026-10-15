import type { ProcessingTrace } from '../../api/contractGraph'

export function processingTimelineOutcome(trace: ProcessingTrace) {
  if (trace.job_status === 'FAILED') return 'job-failed'
  if (trace.job_status === 'CANCELLED') return 'job-cancelled'
  if (trace.job_status === 'QUEUED' || trace.job_status === 'RUNNING') {
    return 'job-running'
  }
  const hasFailedStage = trace.stages.some((stage) => stage.status === 'FAILED')
  if (trace.job_status === 'SUCCEEDED' && hasFailedStage) {
    return 'job-succeeded-with-stage-failure'
  }
  if (hasFailedStage) return 'stage-failed-job-unknown'
  if (trace.job_status === 'SUCCEEDED') return 'job-succeeded'
  return trace.status
}
