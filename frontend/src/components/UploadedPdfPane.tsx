import { useEffect, useState } from 'react'
import { loadDocumentPdf } from '../api/structure'
import { MaterialIcon } from './icons'

export type UploadedPdfFile = {
  id: string
  filename: string
  role: string
}

function roleLabel(role: string) {
  const normalized = role.toLowerCase()
  if (normalized === 'contract') return 'Hợp đồng chính'
  if (normalized === 'annex') return 'Phụ lục'
  return 'Tài liệu'
}

export function UploadedPdfPane({
  documentId,
  filename,
  files = [],
  onSelect,
  onClose,
}: {
  documentId: string
  filename: string | null
  files?: UploadedPdfFile[]
  onSelect?: (id: string) => void
  onClose: () => void
}) {
  const [url, setUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    let objectUrl: string | null = null
    setError(null)
    setUrl(null)

    loadDocumentPdf(documentId, controller.signal)
      .then((bytes) => {
        if (controller.signal.aborted) return
        objectUrl = URL.createObjectURL(
          new Blob([bytes.slice()], { type: 'application/pdf' }),
        )
        setUrl(objectUrl)
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return
        setError(
          cause instanceof Error ? cause.message : 'Không tải được file PDF.',
        )
      })

    return () => {
      controller.abort()
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [documentId])

  return (
    <aside className="flex h-full min-h-0 w-1/2 min-w-0 shrink-0 flex-col border-l border-outline-variant/30 bg-white">
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-outline-variant/20 px-4 py-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-slate-900">
            PDF đã tải lên
          </p>
          <p className="truncate text-xs text-slate-500">
            {filename ?? 'File hợp đồng gốc'}
          </p>
        </div>
        <button
          aria-label="Đóng PDF"
          className="flex h-8 w-8 items-center justify-center rounded-full text-slate-500 hover:bg-slate-100"
          type="button"
          onClick={onClose}
        >
          <MaterialIcon name="close" className="text-[18px]" />
        </button>
      </div>
      {files.length > 1 && onSelect ? (
        <div className="flex shrink-0 gap-1 overflow-x-auto border-b border-outline-variant/20 px-3 py-2">
          {files.map((file) => {
            const active = file.id === documentId
            return (
              <button
                key={file.id}
                className={`shrink-0 rounded-full px-3 py-1 text-xs font-medium ${
                  active
                    ? 'bg-slate-900 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
                type="button"
                onClick={() => onSelect(file.id)}
              >
                {roleLabel(file.role)}
              </button>
            )
          })}
        </div>
      ) : null}
      <div className="min-h-0 flex-1 bg-slate-100">
        {error ? (
          <p className="p-4 text-sm text-red-700">{error}</p>
        ) : null}
        {!url && !error ? (
          <p className="p-4 text-sm text-slate-500">Đang mở file PDF…</p>
        ) : null}
        {url ? (
          <iframe
            className="h-full w-full bg-white"
            src={url}
            title={filename ?? 'PDF đã tải lên'}
          />
        ) : null}
      </div>
    </aside>
  )
}
