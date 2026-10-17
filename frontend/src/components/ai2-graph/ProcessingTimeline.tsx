import type {
  ContractGraphKind,
  ProcessingTrace,
  ProcessingTraceStage,
} from '../../api/contractGraph'
import { MaterialIcon } from '../icons'
import { TechnicalDetail } from '../TechnicalDetail'
import { processingTimelineOutcome, stageReasonText } from './timelineOutcome'

const stageLabels: Record<string, string> = {
  contract_graph_operation: 'Tìm quan hệ điều khoản sửa đổi',
  contract_graph_pairs: 'Tìm quan hệ giữa các điều khoản',
  extraction: 'Trích xuất dữ kiện',
  semantic: 'Phân tích ngữ nghĩa',
}

// Đơn vị kết quả của từng bước, để "0 mục" thành "Không tìm thấy quan hệ nào".
const stageUnits: Record<string, string> = {
  contract_graph_operation: 'sửa đổi',
  contract_graph_pairs: 'quan hệ',
  extraction: 'dữ kiện',
}

// Bước nào thuộc tab nào: mỗi tab chỉ hiện bước tạo ra dữ liệu của nó. null là
// bước không tạo dữ liệu cho đồ thị (trích xuất, ngữ nghĩa): không hiện ở tab
// đồ thị nào, chỉ hiện khi xem toàn bộ các bước.
const stageKinds: Record<string, ContractGraphKind | null> = {
  contract_graph_operation: 'operation',
  contract_graph_pairs: 'pair',
  extraction: null,
  semantic: null,
}

function stageKind(stageId: string, fallback: ContractGraphKind) {
  return Object.hasOwn(stageKinds, stageId) ? stageKinds[stageId] : fallback
}

const stageStatusLabels: Record<ProcessingTraceStage['status'], string> = {
  RUNNING: 'Đang chạy',
  COMPLETED: 'Xong',
  FAILED: 'Lỗi',
  SKIPPED: 'Bỏ qua',
  INTERRUPTED_UNKNOWN: 'Bị gián đoạn',
  INCOMPLETE_UNKNOWN: 'Chưa rõ kết quả',
}

const traceStatusLabels: Record<ProcessingTrace['status'], string> = {
  COMPLETE: 'Các bước xử lý đã kết thúc',
  IN_PROGRESS: 'Đang phân tích',
  INTERRUPTED_UNKNOWN: 'Phân tích bị gián đoạn',
  INCOMPLETE_UNKNOWN: 'Phân tích chưa đầy đủ',
  TRACE_UNAVAILABLE: 'Chưa có thông tin các bước',
}

type Tone = 'done' | 'warn' | 'error' | 'running' | 'neutral'

const outcomes: Record<string, { label: string; tone: Tone }> = {
  'job-failed': { label: 'Phân tích thất bại', tone: 'error' },
  'job-cancelled': { label: 'Đã hủy phân tích', tone: 'neutral' },
  'job-running': { label: 'Đang phân tích', tone: 'running' },
  'job-succeeded-with-stage-failure': {
    label: 'Xong, có bước bị lỗi',
    tone: 'warn',
  },
  'stage-failed-job-unknown': { label: 'Có bước bị lỗi', tone: 'warn' },
  'job-succeeded-limited': {
    label: 'Xong, kết quả chưa đầy đủ',
    tone: 'warn',
  },
  'job-succeeded': { label: 'Phân tích hoàn tất', tone: 'done' },
}

const toneClasses: Record<Tone, string> = {
  done: 'bg-emerald-50 text-emerald-800',
  warn: 'bg-amber-50 text-amber-900',
  error: 'bg-error-container text-on-error-container',
  running: 'bg-brand-50 text-brand-700',
  neutral: 'bg-surface-container text-on-surface-variant',
}

function stageResultText(stage: ProcessingTraceStage) {
  if (stage.item_count === null) return null
  const unit = stageUnits[stage.stage_id] ?? 'mục'
  return stage.item_count === 0
    ? `Không tìm thấy ${unit} nào`
    : `Tìm thấy ${stage.item_count} ${unit}`
}

export function ProcessingTimeline({
  trace,
  graphKind,
}: {
  trace: ProcessingTrace
  /**
   * Có thì chỉ hiện bước của loại sơ đồ này. Bước lạ vẫn hiện; bước trích
   * xuất và ngữ nghĩa thì không.
   */
  graphKind?: ContractGraphKind
}) {
  const stages = graphKind
    ? trace.stages.filter(
        (stage) => stageKind(stage.stage_id, graphKind) === graphKind,
      )
    : trace.stages
  const unavailable =
    trace.trace_status === 'UNAVAILABLE' || trace.status === 'TRACE_UNAVAILABLE'
  // Nhãn kết quả tính theo bước của tab đang xem: tab kia lỗi hay thiếu AI
  // không làm nhãn của tab này đổi màu.
  const outcome = outcomes[processingTimelineOutcome({ ...trace, stages })] ?? {
    label: traceStatusLabels[trace.status],
    tone: 'neutral' as const,
  }
  return (
    <section
      aria-labelledby="ai2-processing-title"
      className="min-w-0 rounded-lg bg-surface-container-lowest p-space-lg shadow-sm"
    >
      <div className="flex flex-wrap items-center justify-between gap-space-sm">
        <div className="flex items-center gap-space-sm">
          <MaterialIcon
            name="checklist"
            className="text-[20px] text-on-tertiary-container"
          />
          <h2
            id="ai2-processing-title"
            className="font-title-sm text-title-sm font-semibold text-on-surface"
          >
            Các bước phân tích
          </h2>
        </div>
        <span
          className={`rounded-full px-space-sm py-0.5 font-label-sm text-label-sm font-semibold ${toneClasses[outcome.tone]}`}
          role="status"
        >
          {outcome.label}
        </span>
      </div>
      {unavailable ? (
        <p className="mt-space-sm font-body-sm text-body-sm text-on-surface-variant">
          Chưa xem được các bước đã chạy của lần phân tích này.
        </p>
      ) : stages.length === 0 ? (
        <p className="mt-space-sm font-body-sm text-body-sm text-on-surface-variant">
          Chưa có bước nào được ghi nhận.
        </p>
      ) : (
        <ol className="mt-space-md flex min-w-0 flex-col">
          {stages.map((stage, index) => {
            const note = stageReasonText(stage.reason_code)
            // Thời gian chạy của bước (duration_ms) là số kỹ thuật, không hiện.
            const meta = [
              stageResultText(stage),
              stage.started_ms === null
                ? null
                : new Date(stage.started_ms).toLocaleTimeString('vi-VN'),
            ].filter(Boolean)
            const last = index === stages.length - 1
            return (
              <li
                key={`${stage.stage_id}-${index}`}
                className="flex min-w-0 gap-space-md"
              >
                <div className="flex flex-col items-center">
                  <StageIcon status={stage.status} />
                  {last ? null : (
                    <div
                      className={`min-h-4 w-px flex-1 ${
                        stage.status === 'COMPLETED'
                          ? 'bg-emerald-300'
                          : 'bg-outline-variant'
                      }`}
                    />
                  )}
                </div>
                <div className="flex min-w-0 flex-1 flex-col gap-0.5 pb-space-md">
                  <div className="flex min-w-0 flex-wrap items-start justify-between gap-x-space-sm">
                    <span className="min-w-0 break-words font-body-sm text-body-sm font-semibold text-on-surface">
                      {stageLabels[stage.stage_id] ?? 'Bước phân tích'}
                    </span>
                    <span
                      className={`shrink-0 font-label-sm text-label-sm font-semibold ${
                        stage.status === 'COMPLETED'
                          ? 'text-emerald-700'
                          : stage.status === 'FAILED'
                            ? 'text-error'
                            : stage.status === 'RUNNING'
                              ? 'text-on-tertiary-container'
                              : 'text-on-surface-variant'
                      }`}
                    >
                      {stageStatusLabels[stage.status]}
                    </span>
                  </div>
                  {meta.length > 0 ? (
                    <span className="font-label-sm text-label-sm text-on-surface-variant">
                      {meta.join(' · ')}
                    </span>
                  ) : null}
                  {note ? (
                    <p className="mt-space-xs flex items-start gap-space-xs rounded-md bg-amber-50 px-space-sm py-space-xs font-body-sm text-body-sm text-amber-950">
                      <MaterialIcon
                        name="info"
                        className="mt-0.5 shrink-0 text-[16px] text-amber-700"
                      />
                      <span className="min-w-0">{note}</span>
                    </p>
                  ) : null}
                  <TechnicalDetail
                    text={
                      stage.reason_code &&
                      `${stage.stage_id}: ${stage.reason_code}`
                    }
                  />
                </div>
              </li>
            )
          })}
        </ol>
      )}
    </section>
  )
}

function StageIcon({ status }: { status: ProcessingTraceStage['status'] }) {
  if (status === 'COMPLETED') {
    return (
      <MaterialIcon
        name="check_circle"
        className="text-[22px] text-emerald-600"
      />
    )
  }
  if (status === 'FAILED') {
    return <MaterialIcon name="error" className="text-[22px] text-error" />
  }
  if (status === 'RUNNING') {
    return (
      <MaterialIcon
        name="progress_activity"
        className="animate-spin text-[22px] text-primary"
      />
    )
  }
  if (status === 'SKIPPED') {
    return (
      <MaterialIcon
        name="do_not_disturb_on"
        className="text-[22px] text-outline"
      />
    )
  }
  return <MaterialIcon name="help" className="text-[22px] text-outline" />
}
