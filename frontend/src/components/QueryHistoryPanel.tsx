import { useEffect, useState } from 'react'
import {
  listDossierQueries,
  QUERY_HISTORY_PAGE,
  type QueryHistoryItem,
} from '../api/queries'
import { structureErrorMessage } from '../api/structure'
import { MaterialIcon } from './icons'

type QueryHistoryPanelProps = {
  dossierId: string
  /** Đổi giá trị này để tải lại (sau mỗi câu hỏi mới). */
  refreshKey: number
  onReuse: (question: string) => void
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
  if (item.errorCode) return `AI chưa trả lời được câu này (mã ${item.errorCode}).`
  return 'Chưa có câu trả lời được lưu.'
}

export function QueryHistoryPanel({
  dossierId,
  refreshKey,
  onReuse,
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
        setError(structureErrorMessage(cause) ?? 'Không tải được lịch sử hỏi đáp.')
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
        {items.map((item) => (
          <li
            key={item.traceId}
            className="rounded-lg bg-surface p-space-md space-y-space-xs"
          >
            <div className="flex flex-wrap items-start justify-between gap-space-sm">
              <p className="font-body-sm text-body-sm text-on-surface font-semibold">
                {item.question}
              </p>
              <button
                className="flex items-center gap-1 font-label-sm text-label-sm text-secondary hover:text-primary"
                type="button"
                onClick={() => onReuse(item.question)}
              >
                <MaterialIcon name="replay" className="text-[16px]" />
                Hỏi lại
              </button>
            </div>
            {item.answer ? (
              <p className="font-body-sm text-body-sm text-on-surface whitespace-pre-wrap">
                {item.answer}
              </p>
            ) : (
              <p className="font-body-sm text-body-sm text-error">
                {failureText(item)}
              </p>
            )}
            {item.citations.some((citation) => citation.quote) ? (
              <ul className="space-y-1">
                {item.citations
                  .filter((citation) => citation.quote)
                  .slice(0, 3)
                  .map((citation, index) => (
                    <li
                      key={index}
                      className="font-label-sm text-label-sm text-on-surface-variant border-l-2 border-outline-variant pl-space-sm"
                    >
                      {citation.pageNo !== null ? `Tr. ${citation.pageNo}: ` : ''}
                      {citation.quote}
                    </li>
                  ))}
              </ul>
            ) : null}
            <p className="font-label-sm text-label-sm text-secondary">
              {formatWhen(item.createdAt)}
              {item.state ? ` · ${item.state}` : ''}
            </p>
          </li>
        ))}
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
