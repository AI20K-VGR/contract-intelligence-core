import { useEffect, useRef, useState } from 'react'

import type {
  ContractGraphKind,
  ProcessingTrace,
  ProcessingTraceStage,
} from '../../api/contractGraph'
import { MaterialIcon } from '../icons'
import { TechnicalDetail } from '../TechnicalDetail'
import { processingTimelineOutcome, stageReasonText } from './timelineOutcome'

// Cùng bộ nhãn với #125 (merge sau PR này): #125 chỉ cần bỏ bản của nó.
const stageLabels: Record<string, string> = {
  extraction: 'Trích xuất dữ kiện từ điều khoản',
  semantic: 'Phân tích ngữ nghĩa điều khoản',
  contract_graph_operation: 'Nối điều khoản sửa đổi với điều khoản gốc',
  contract_graph_pairs: 'Phân tích quan hệ giữa các điều khoản',
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

type TimelineInput = {
  trace: ProcessingTrace
  /**
   * Có thì chỉ hiện bước của loại sơ đồ này. Bước lạ vẫn hiện; bước trích
   * xuất và ngữ nghĩa thì không.
   */
  graphKind?: ContractGraphKind
}

function summarizeTrace({ trace, graphKind }: TimelineInput) {
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
  const notes = [
    ...new Set(
      stages
        .map((stage) => stageReasonText(stage.reason_code))
        .filter((note): note is string => Boolean(note)),
    ),
  ]
  return { stages, unavailable, outcome, notes }
}

const toneIcons: Record<Tone, string> = {
  done: 'check_circle',
  warn: 'warning',
  error: 'error',
  running: 'progress_activity',
  neutral: 'info',
}

/**
 * Kết quả phân tích gọn trong một chip; bấm vào mới mở danh sách các bước.
 * Người dùng chỉ cần biết phân tích xong hay có vấn đề, không cần đọc từng bước.
 */
export function AnalysisStatus(props: TimelineInput) {
  const { stages, unavailable, outcome } = summarizeTrace(props)
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const close = (event: Event) => {
      if (
        event instanceof KeyboardEvent
          ? event.key === 'Escape'
          : !root.current?.contains(event.target as Node)
      )
        setOpen(false)
    }
    document.addEventListener('mousedown', close)
    document.addEventListener('keydown', close)
    return () => {
      document.removeEventListener('mousedown', close)
      document.removeEventListener('keydown', close)
    }
  }, [open])
  return (
    <div ref={root} className="relative">
      <button
        aria-controls="ai2-processing-steps"
        aria-expanded={open}
        className={`inline-flex h-8 items-center gap-space-xs rounded-full px-space-sm font-label-sm text-label-sm font-semibold transition-colors hover:brightness-95 focus-visible:outline focus-visible:outline-2 ${toneClasses[outcome.tone]}`}
        onClick={() => setOpen((value) => !value)}
        title="Xem các bước phân tích"
        type="button"
      >
        <MaterialIcon
          name={toneIcons[outcome.tone]}
          className={`text-[16px] ${outcome.tone === 'running' ? 'animate-spin' : ''}`}
        />
        <span role="status">{outcome.label}</span>
        <MaterialIcon
          name="expand_more"
          className={`text-[16px] transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </button>
      <section
        id="ai2-processing-steps"
        aria-labelledby="ai2-processing-title"
        className="absolute right-0 z-30 mt-space-xs w-[min(22rem,calc(100vw-2rem))] rounded-lg bg-surface-container-lowest p-space-md shadow-lg ring-1 ring-outline-variant/40"
        hidden={!open}
      >
        <h3
          id="ai2-processing-title"
          className="font-label-md text-label-md font-semibold text-on-surface"
        >
          Các bước phân tích
        </h3>
        {unavailable ? (
          <p className="mt-space-sm font-body-sm text-body-sm text-on-surface-variant">
            Chưa xem được các bước đã chạy của lần phân tích này.
          </p>
        ) : stages.length === 0 ? (
          <p className="mt-space-sm font-body-sm text-body-sm text-on-surface-variant">
            Chưa có bước nào được ghi nhận.
          </p>
        ) : (
          <ol className="mt-space-sm flex min-w-0 flex-col gap-space-sm">
            {stages.map((stage, index) => {
              // Thời gian chạy của bước (duration_ms) là số kỹ thuật, không hiện.
              const meta = [
                stageResultText(stage),
                stage.started_ms === null
                  ? null
                  : new Date(stage.started_ms).toLocaleTimeString('vi-VN'),
              ].filter(Boolean)
              return (
                <li
                  key={`${stage.stage_id}-${index}`}
                  className="flex min-w-0 gap-space-sm"
                >
                  <StageIcon status={stage.status} />
                  <div className="flex min-w-0 flex-1 flex-col">
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
    </div>
  )
}

/** Lời giải thích của các bước (vì sao kết quả thiếu, bước nào lỗi). Không có thì không hiện gì. */
export function AnalysisNotices(props: TimelineInput) {
  const { notes } = summarizeTrace(props)
  if (notes.length === 0) return null
  return (
    <div className="flex min-w-0 flex-col gap-space-xs">
      {notes.map((note) => (
        <p
          key={note}
          className="flex items-start gap-space-xs rounded-lg bg-amber-50 px-space-md py-space-sm font-body-sm text-body-sm text-amber-950"
        >
          <MaterialIcon
            name="info"
            className="mt-0.5 shrink-0 text-[16px] text-amber-700"
          />
          <span className="min-w-0">{note}</span>
        </p>
      ))}
    </div>
  )
}

/** Chip kết quả và lời giải thích đứng chung, cho trang mẫu và kiểm thử. */
export function ProcessingTimeline(props: TimelineInput) {
  return (
    <div className="flex min-w-0 flex-col gap-space-sm">
      <div className="flex justify-end">
        <AnalysisStatus {...props} />
      </div>
      <AnalysisNotices {...props} />
    </div>
  )
}

function StageIcon({ status }: { status: ProcessingTraceStage['status'] }) {
  if (status === 'COMPLETED') {
    return (
      <MaterialIcon
        name="check_circle"
        className="text-[18px] text-emerald-600"
      />
    )
  }
  if (status === 'FAILED') {
    return <MaterialIcon name="error" className="text-[18px] text-error" />
  }
  if (status === 'RUNNING') {
    return (
      <MaterialIcon
        name="progress_activity"
        className="animate-spin text-[18px] text-primary"
      />
    )
  }
  if (status === 'SKIPPED') {
    return (
      <MaterialIcon
        name="do_not_disturb_on"
        className="text-[18px] text-outline"
      />
    )
  }
  return <MaterialIcon name="help" className="text-[18px] text-outline" />
}
