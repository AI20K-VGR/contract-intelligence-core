import { useEffect, useState } from 'react'
import {
  listDossierQueries,
  QUERY_HISTORY_PAGE,
  type QueryHistoryCitation,
  type QueryHistoryItem,
} from '../api/queries'
import { structureErrorMessage } from '../api/structure'
import { MaterialIcon } from './icons'
import {
  answerBlocks,
  citesByBlock,
  norm,
  type NumberedCitation,
} from './queryAnswer'

type QueryHistoryPanelProps = {
  dossierId: string
  /** Đổi giá trị này để tải lại (sau mỗi câu hỏi mới). */
  refreshKey: number
  onReuse: (question: string) => void
  /** Bấm số trích dẫn trong câu trả lời: mở vùng trích trên hợp đồng. */
  onCite?: (citation: QueryHistoryCitation, citeNo: number) => void
}

const whenFormat = new Intl.DateTimeFormat('vi-VN', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

function formatWhen(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '' : whenFormat.format(date)
}

function failureText(item: QueryHistoryItem) {
  if (item.errorCode)
    return `AI chưa trả lời được câu này (mã ${item.errorCode}).`
  return 'Chưa có câu trả lời được lưu.'
}

const STATE_LABELS: Record<string, string> = {
  ANSWERED: 'Đã trả lời',
  PARTIAL: 'Trả lời một phần',
  NOT_FOUND: 'Không tìm thấy',
  BLOCKED: 'Bị chặn',
}

/** Câu trả lời dài chỉ hiện vài mục đầu, bấm để xem hết. */
const PREVIEW_BLOCKS = 4

export function AnswerView({
  answer,
  citations,
  onCite,
}: {
  answer: string
  citations: QueryHistoryCitation[]
  onCite?: (citation: QueryHistoryCitation, citeNo: number) => void
}) {
  const [open, setOpen] = useState(false)
  const [activeNo, setActiveNo] = useState<number | null>(null)
  const blocks = answerBlocks(answer)
  const { placed, unplaced } = citesByBlock(blocks, citations)
  const shown = open ? blocks : blocks.slice(0, PREVIEW_BLOCKS)
  const citeButtons = (entries: NumberedCitation[]) =>
    entries.map(({ citation, n }) => (
      <button
        key={n}
        className={`ml-1 inline-flex h-4 min-w-4 items-center justify-center rounded-full border px-1 align-super text-[10px] font-semibold leading-none ${
          activeNo === n
            ? 'border-brand-600 bg-brand-600 text-white'
            : 'border-brand-300 bg-white text-brand-700 hover:bg-brand-50'
        }`}
        disabled={!onCite}
        title={`Trích dẫn ${n}${citation.pageNo ? ` · trang ${citation.pageNo}` : ''}`}
        type="button"
        onClick={() => {
          setActiveNo(n)
          onCite?.(citation, n)
        }}
      >
        {n}
      </button>
    ))
  return (
    <div className="space-y-1.5 rounded-lg border-l-2 border-brand-300 bg-tone-50 px-space-md py-space-sm">
      {shown.map((block, index) =>
        block.kind === 'heading' ? (
          <p
            key={index}
            className="font-body-sm text-body-sm font-semibold text-brand-700"
          >
            {block.text}
            {citeButtons(placed.get(index) ?? [])}
          </p>
        ) : block.kind === 'item' ? (
          <p
            key={index}
            className="flex gap-space-sm font-body-sm text-body-sm leading-relaxed text-on-surface"
          >
            <span className="shrink-0 font-semibold text-brand-700 tabular-nums">
              {block.no}
            </span>
            <span>
              {block.text}
              {citeButtons(placed.get(index) ?? [])}
            </span>
          </p>
        ) : (
          <p
            key={index}
            className="font-body-sm text-body-sm leading-relaxed text-on-surface"
          >
            {block.text}
            {citeButtons(placed.get(index) ?? [])}
          </p>
        ),
      )}
      {blocks.length > PREVIEW_BLOCKS ? (
        <button
          className="font-label-sm text-label-sm font-semibold text-brand-700 hover:underline"
          type="button"
          onClick={() => setOpen((current) => !current)}
        >
          {open ? 'Thu gọn' : `Xem thêm ${blocks.length - PREVIEW_BLOCKS} mục`}
        </button>
      ) : null}
      {unplaced.length > 0 ? (
        <p className="font-label-sm text-label-sm text-secondary">
          Trích dẫn khác (chưa xác định đoạn liên quan):
          {citeButtons(unplaced)}
        </p>
      ) : null}
    </div>
  )
}

/** Cùng một câu hỏi (không kể hoa/thường, khoảng trắng) gom làm một mục. */
function groupByQuestion(items: QueryHistoryItem[]) {
  const groups = new Map<string, QueryHistoryItem[]>()
  for (const item of items) {
    const key = norm(item.question)
    groups.set(key, [...(groups.get(key) ?? []), item])
  }
  // API trả mới nhất trước: phần tử đầu mỗi nhóm là lần hỏi gần nhất.
  return [...groups.values()]
}

export function QueryHistoryPanel({
  dossierId,
  refreshKey,
  onReuse,
  onCite,
}: QueryHistoryPanelProps) {
  const [items, setItems] = useState<QueryHistoryItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError(null)
    listDossierQueries(dossierId, {
      // Chỉ câu hỏi của chính người dùng; không xem được của người khác.
      scope: 'mine',
      limit: QUERY_HISTORY_PAGE,
      offset: 0,
      signal: controller.signal,
    })
      .then((page) => {
        if (controller.signal.aborted) return
        setItems(page.items)
        setTotal(page.total)
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return
        setError(
          structureErrorMessage(cause) ?? 'Không tải được lịch sử hỏi đáp.',
        )
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [dossierId, refreshKey])

  async function loadMore() {
    if (loading) return
    setLoading(true)
    try {
      const page = await listDossierQueries(dossierId, {
        scope: 'mine',
        limit: QUERY_HISTORY_PAGE,
        offset: items.length,
      })
      setItems((current) => [...current, ...page.items])
      setTotal(page.total)
    } catch (cause) {
      setError(structureErrorMessage(cause) ?? 'Không tải thêm được.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <section
      aria-label="Lịch sử hỏi đáp"
      className="bg-surface-container-lowest p-space-lg rounded-xl shadow-sm space-y-space-md"
    >
      <h2 className="font-title-sm text-title-sm text-primary uppercase tracking-wider">
        Lịch sử hỏi đáp
      </h2>

      {error ? (
        <p className="font-label-sm text-label-sm text-error" role="alert">
          {error}
        </p>
      ) : null}

      {items.length === 0 && !loading && !error ? (
        <p className="font-body-sm text-body-sm text-on-surface-variant">
          Chưa có câu hỏi nào trên hồ sơ này.
        </p>
      ) : null}

      <ul className="space-y-space-sm">
        {groupByQuestion(items).map((group) => {
          const item = group[0]!
          // Câu trả lời của lần hỏi gần nhất có trả lời.
          const answered = group.find((entry) => entry.answer) ?? item
          return (
            <li
              key={item.traceId}
              className="space-y-space-sm rounded-xl border border-outline-variant p-space-md"
            >
              <div className="flex items-start justify-between gap-space-sm">
                <p className="flex min-w-0 items-start gap-space-sm font-body-md text-body-md font-semibold text-on-surface">
                  <MaterialIcon
                    name="chat_bubble"
                    className="mt-0.5 shrink-0 text-[18px] text-brand-600"
                  />
                  <span className="min-w-0 break-words">{item.question}</span>
                </p>
                <button
                  className="flex shrink-0 items-center gap-1 rounded-full px-2 py-1 font-label-sm text-label-sm text-secondary hover:bg-surface-container hover:text-primary"
                  type="button"
                  onClick={() => onReuse(item.question)}
                >
                  <MaterialIcon name="replay" className="text-[16px]" />
                  Hỏi lại
                </button>
              </div>
              {answered.answer ? (
                <AnswerView
                  answer={answered.answer}
                  citations={answered.citations}
                  onCite={onCite}
                />
              ) : (
                <p className="font-body-sm text-body-sm text-error">
                  {failureText(answered)}
                </p>
              )}
              <div className="flex flex-wrap items-center gap-space-xs font-label-sm text-label-sm text-secondary">
                {group.length > 1 ? (
                  <span className="font-semibold text-on-surface-variant">
                    Đã hỏi {group.length} lần:
                  </span>
                ) : null}
                {group.map((entry) => (
                  <span
                    key={entry.traceId}
                    className="rounded-full bg-surface-container px-2 py-0.5 tabular-nums"
                  >
                    {formatWhen(entry.createdAt)}
                  </span>
                ))}
                {answered.state ? (
                  <span
                    className={`rounded-full px-2 py-0.5 font-semibold ${
                      answered.state === 'ANSWERED'
                        ? 'bg-emerald-50 text-emerald-700'
                        : 'bg-surface-container text-on-surface-variant'
                    }`}
                  >
                    {STATE_LABELS[answered.state] ?? answered.state}
                  </span>
                ) : null}
              </div>
            </li>
          )
        })}
      </ul>

      {loading ? (
        <p className="font-label-sm text-label-sm text-secondary">Đang tải…</p>
      ) : items.length < total ? (
        <button
          className="h-9 px-space-lg bg-surface-container text-on-surface hover:bg-surface-container-high font-body-sm text-body-sm rounded-lg"
          type="button"
          onClick={() => {
            void loadMore()
          }}
        >
          Tải thêm ({total - items.length})
        </button>
      ) : null}
    </section>
  )
}
