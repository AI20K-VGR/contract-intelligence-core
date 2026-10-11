import type { ProcessingTrace } from '../../api/contractGraph'

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
  COMPLETE: 'Hoàn tất xử lý AI2',
  IN_PROGRESS: 'AI2 đang xử lý',
  INTERRUPTED_UNKNOWN: 'Xử lý AI2 bị gián đoạn, chưa rõ kết quả',
  INCOMPLETE_UNKNOWN: 'Luồng AI2 chưa đầy đủ, chưa rõ kết quả',
  TRACE_UNAVAILABLE: 'Chưa có dấu vết xử lý AI2',
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
        Luồng xử lý AI2
      </h2>
      <p className="mt-1 font-body-md" role="status">
        {traceStatusLabels[trace.status]}
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
                  {stageLabels[stage.stage_id] ?? 'Bước xử lý AI2'}
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
              {stage.reason_code ? (
                <p className="mt-1 break-all text-sm">
                  Mã trạng thái: {stage.reason_code}
                </p>
              ) : null}
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
