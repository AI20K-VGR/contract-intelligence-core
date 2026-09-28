import { useEffect, useState } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import {
  listDossiers,
  listDossiersErrorMessage,
  type DossierSummary,
} from '../api/dossiers'
import type { StructuredEvidence } from '../api/analysis'
import { DossierAnalysisPanel } from '../components/DossierAnalysisPanel'
import { MaterialIcon } from '../components/icons'
import { usePageTitle } from '../hooks/usePageTitle'

export function AnalysisCenterPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams, setSearchParams] = useSearchParams()
  const [dossiers, setDossiers] = useState<DossierSummary[]>([])
  const [selectedId, setSelectedId] = useState(
    searchParams.get('dossierId') ?? '',
  )
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  usePageTitle('Trung tâm Phân tích')

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    void listDossiers({ signal: controller.signal })
      .then(({ items }) => {
        if (controller.signal.aborted) return
        setDossiers(items)
        const requested = searchParams.get('dossierId')
        const nextId = items.some((item) => item.id === requested)
          ? requested
          : selectedId && items.some((item) => item.id === selectedId)
            ? selectedId
            : (items[0]?.id ?? '')
        setSelectedId(nextId)
        if (nextId && nextId !== requested) {
          setSearchParams({ dossierId: nextId }, { replace: true })
        }
      })
      .catch((cause: unknown) => {
        if (controller.signal.aborted) return
        setError(listDossiersErrorMessage(cause))
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
    // The query is intentionally read once per load; selection changes are handled below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.key])

  function selectDossier(dossierId: string) {
    setSelectedId(dossierId)
    if (dossierId) setSearchParams({ dossierId }, { replace: true })
    else setSearchParams({}, { replace: true })
  }

  function openEvidence(evidence: StructuredEvidence, fallbackText: string) {
    if (!selectedId || evidence.status !== 'LOCATABLE' || !evidence.pageNo) {
      return
    }
    const dossier = dossiers.find((item) => item.id === selectedId)
    navigate(`/cau-truc/${encodeURIComponent(selectedId)}`, {
      state: {
        dossierId: selectedId,
        name: dossier?.name,
        focusCitation: {
          text: evidence.quote || fallbackText,
          pageNo: evidence.pageNo,
          sourceFileId: evidence.sourceFileId,
          lineId: evidence.lineId,
          bbox: evidence.bbox,
        },
      },
    })
  }

  const selected = dossiers.find((item) => item.id === selectedId) ?? null

  return (
    <div className="flex w-full flex-col gap-space-lg pb-space-lg">
      <div className="flex flex-col gap-space-xs">
        <div className="flex items-center gap-space-xs font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant">
          <MaterialIcon name="analytics" className="text-[18px]" />
          <span>AI2 · Facts & Findings</span>
        </div>
        <h1 className="font-headline-lg text-headline-lg tracking-tight text-primary">
          Trung tâm Phân tích
        </h1>
        <p className="max-w-3xl font-body-md text-body-md text-secondary">
          Chọn một hồ sơ để xem dữ liệu AI2 đã trích xuất, các điểm rủi ro và
          citation có thể mở ngược về tài liệu gốc.
        </p>
      </div>

      <section className="flex flex-col gap-space-sm rounded-xl bg-surface-container-lowest p-space-md shadow-sm md:flex-row md:items-end">
        <label className="flex min-w-0 flex-1 flex-col gap-space-xs font-label-md text-label-md text-on-surface">
          Hồ sơ phân tích
          <select
            aria-label="Chọn hồ sơ phân tích"
            className="h-10 rounded border border-outline-variant/40 bg-surface-container-lowest px-space-sm font-body-md text-body-md text-on-surface focus:outline-none focus:ring-1 focus:ring-primary"
            value={selectedId}
            onChange={(event) => selectDossier(event.target.value)}
            disabled={loading || dossiers.length === 0}
          >
            {dossiers.length === 0 ? (
              <option value="">Chưa có hồ sơ</option>
            ) : null}
            {dossiers.map((dossier) => (
              <option key={dossier.id} value={dossier.id}>
                {dossier.name} · {dossier.id}
              </option>
            ))}
          </select>
        </label>
        <button
          className="inline-flex h-10 items-center justify-center gap-space-xs rounded bg-surface-container px-space-md font-label-md text-label-md text-on-surface hover:bg-surface-container-high disabled:cursor-not-allowed disabled:opacity-50"
          type="button"
          onClick={() => setSearchParams({}, { replace: true })}
          disabled={loading}
        >
          <MaterialIcon name="refresh" className="text-[18px]" />
          Tải lại danh sách
        </button>
      </section>

      {loading ? (
        <section className="rounded-xl bg-surface-container-lowest p-space-lg shadow-sm">
          <p className="font-body-md text-body-md text-secondary">
            Đang tải danh sách hồ sơ...
          </p>
        </section>
      ) : null}
      {error ? (
        <section
          className="rounded-xl bg-error-container p-space-lg text-on-error-container"
          role="alert"
        >
          {error}
        </section>
      ) : null}

      {!loading && !error && selected ? (
        <div className="space-y-space-sm">
          <div className="flex flex-wrap items-center justify-between gap-space-sm rounded-xl border border-outline-variant/30 bg-surface-container-low px-space-md py-space-sm">
            <div className="min-w-0">
              <p className="truncate font-title-sm text-title-sm font-semibold text-on-surface">
                {selected.name}
              </p>
              <p className="font-code-sm text-code-sm text-secondary">
                {selected.id} · trạng thái xử lý:{' '}
                {selected.latest_job_status ?? 'chưa xác định'}
              </p>
            </div>
            <button
              className="text-primary underline"
              type="button"
              onClick={() =>
                navigate(`/cau-truc/${encodeURIComponent(selected.id)}`, {
                  state: { dossierId: selected.id, name: selected.name },
                })
              }
            >
              Mở cấu trúc hồ sơ
            </button>
          </div>
          <DossierAnalysisPanel
            dossierId={selected.id}
            onOpenEvidence={openEvidence}
          />
        </div>
      ) : null}

      {!loading && !error && !selected ? (
        <section className="rounded-xl bg-surface-container-lowest p-space-lg shadow-sm">
          <p className="font-body-md text-body-md text-secondary">
            Chưa có hồ sơ để phân tích.
          </p>
        </section>
      ) : null}
    </div>
  )
}
