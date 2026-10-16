import type { ProcessingTrace } from '../../api/contractGraph'
import { TechnicalDetail } from '../TechnicalDetail'
import { processingTimelineOutcome, stageReasonText } from './timelineOutcome'

const stageLabels: Record<string, string> = {
  contract_graph_operation: 'Tìm quan hệ điều khoản sửa đổi',
  contract_graph_pairs: 'Tìm quan hệ giữa các điều khoản',
}

const stageStatusLabels: Record<string, string> = {
  RUNNING: 'Đang chạy',
  COMPLETED: 'Đã hoàn tất',
  FAILED: 'Thất bại',
  SKIPPED: 'Đã bỏ qua',
  INTERRUPTED_UNKNOWN: 'Bị gián đoạn, chưa rõ kết quả',
  INCOMPLETE_UNKNOWN: 'Chưa rõ kết quả bước xử lý',
}

const traceStatusLabels: Record<ProcessingTrace['status'], string> = {
  COMPLETE: 'Các bước xử lý đã kết thúc',
  IN_PROGRESS: 'Đang phân tích',
  INTERRUPTED_UNKNOWN: 'Phân tích bị gián đoạn, chưa rõ kết quả',
  INCOMPLETE_UNKNOWN: 'Phân tích chưa đầy đủ, chưa rõ kết quả',
  TRACE_UNAVAILABLE: 'Chưa có thông tin các bước phân tích',
}

const outcomeLabels: Record<string, string> = {
  'job-failed': 'Phân tích thất bại',
  'job-cancelled': 'Đã hủy phân tích',
  'job-running': 'Đang phân tích',
  'job-succeeded-with-stage-failure': 'Phân tích xong nhưng có bước bị lỗi',
  'stage-failed-job-unknown': 'Có bước phân tích bị lỗi, chưa rõ kết quả chung',
  'job-succeeded': 'Phân tích hoàn tất',
}

export function ProcessingTimeline({ trace }: { trace: ProcessingTrace }) {
  const unavailable =
    trace.trace_status === 'UNAVAILABLE' || trace.status === 'TRACE_UNAVAILABLE'
  return (
    <section
      aria-labelledby="ai2-processing-title"
      className="min-w-0 rounded-lg border border-outline-variant p-3"
    >
      <h2 id="ai2-processing-title" className="font-title-md font-semibold">
        Các bước phân tích
      </h2>
      <p className="mt-1 font-body-md" role="status">
        {outcomeLabels[processingTimelineOutcome(trace)] ??
          traceStatusLabels[trace.status]}
      </p>
      {unavailable ? (
        <p className="mt-2 break-words text-on-surface-variant">
          Dấu vết xử lý không khả dụng; không thể xác nhận các bước đã chạy.
        </p>
      ) : trace.stages.length === 0 ? (
        <p className="mt-2 text-on-surface-variant">
          Chưa có mốc bước xử lý được ghi nhận.
        </p>
      ) : (
        <ol className="mt-3 flex min-w-0 flex-col gap-2">
          {trace.stages.map((stage, index) => (
            <li
              key={`${stage.stage_id}-${index}`}
              className="min-w-0 rounded-md bg-surface-container-low p-3"
            >
              <div className="flex min-w-0 flex-wrap items-start justify-between gap-x-3 gap-y-1">
                <h3 className="min-w-0 break-words font-semibold">
                  {stageLabels[stage.stage_id] ?? 'Bước phân tích'}
                </h3>
                <span className="shrink-0 rounded bg-surface-container px-2 py-1 text-sm">
                  {stageStatusLabels[stage.status]}
                </span>
              </div>
              <p className="mt-1 text-sm text-on-surface-variant">
                {stage.item_count === null
                  ? 'Chưa có số lượng kết quả'
                  : `${stage.item_count} mục`}
                {stage.started_ms === null
                  ? ' · Thời điểm không rõ'
                  : ` · ${new Date(stage.started_ms).toLocaleString()}`}
                {stage.duration_ms === null ? '' : ` · ${stage.duration_ms} ms`}
              </p>
              {stageReasonText(stage.reason_code) ? (
                <p className="mt-1 break-words text-sm">
                  {stageReasonText(stage.reason_code)}
                </p>
              ) : null}
              <TechnicalDetail
                text={
                  stage.reason_code && `${stage.stage_id}: ${stage.reason_code}`
                }
              />
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
