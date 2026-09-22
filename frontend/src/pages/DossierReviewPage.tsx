import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { ContractMindmap } from '../components/ContractMindmap'
import { DossierAuditLog } from '../components/DossierAuditLog'
import { DossierSearchResults } from '../components/DossierSearchResults'
import { MaterialIcon } from '../components/icons'
import { auditTotalCount, exportAuditCsv } from '../data/auditLog'
import { sampleSearchQuery } from '../data/dossierSearch'
import { usePageTitle } from '../hooks/usePageTitle'

type ReviewTab = 'search' | 'activity' | 'clauses' | 'risk'
type ExportState = 'idle' | 'saving' | 'done'

const tabs: Array<{
  id: ReviewTab
  icon: string
  label: string
  badge?: string
}> = [
  { id: 'search', icon: 'document_scanner', label: 'Tìm kiếm & Rà soát' },
  {
    id: 'activity',
    icon: 'history_edu',
    label: 'Nhật ký hoạt động',
    badge: `${auditTotalCount} sự kiện`,
  },
  { id: 'clauses', icon: 'gavel', label: 'Đối chiếu Điều khoản Mẫu' },
  { id: 'risk', icon: 'shield_with_heart', label: 'Đánh giá Rủi ro Pháp lý' },
]

export function DossierReviewPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const state = location.state as {
    showSearch?: boolean
    tab?: ReviewTab
  } | null
  const [tab, setTab] = useState<ReviewTab>(
    location.pathname === '/nhat-ky-phap-ly'
      ? 'activity'
      : (state?.tab ?? 'search'),
  )
  const [query, setQuery] = useState('')
  const [showResults, setShowResults] = useState(false)
  const [exportState, setExportState] = useState<ExportState>('idle')
  const searchRef = useRef<HTMLInputElement>(null)

  usePageTitle(tab === 'activity' ? 'Nhật ký kiểm soát' : 'Hồ sơ Hợp đồng')

  useEffect(() => {
    if (location.pathname === '/nhat-ky-phap-ly') {
      setTab('activity')
    }
    if (state?.tab) {
      setTab(state.tab)
    }
    if (state?.showSearch) {
      setQuery(sampleSearchQuery)
      setShowResults(true)
      if (!state.tab) {
        setTab('search')
      }
    }
  }, [location.pathname, state])

  useEffect(() => {
    function handleShortcut(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setTab('search')
        searchRef.current?.focus()
      }
    }

    window.addEventListener('keydown', handleShortcut)
    return () => window.removeEventListener('keydown', handleShortcut)
  }, [])

  function handleSearch(event: FormEvent) {
    event.preventDefault()
    setShowResults(query.trim().length > 0)
  }

  function runSampleSearch() {
    setQuery(sampleSearchQuery)
    setShowResults(true)
  }

  function handleExport() {
    if (exportState !== 'idle') return
    setExportState('saving')
    exportAuditCsv()
    window.setTimeout(() => {
      setExportState('done')
      window.setTimeout(() => setExportState('idle'), 1400)
    }, 400)
  }

  return (
    <div className="flex flex-col w-full space-y-space-md">
      <div className="bg-surface-container-lowest p-space-lg rounded-xl shadow-sm flex flex-col gap-space-md">
        <div className="flex flex-wrap items-center justify-between gap-space-md">
          <div className="flex items-center gap-space-sm flex-wrap">
            <span className="font-label-sm text-label-sm uppercase tracking-wider text-secondary">
              Hồ sơ Hợp đồng
            </span>
            <span className="text-outline-variant font-code-sm text-code-sm">
              /
            </span>
            <div className="flex items-center gap-space-xs flex-wrap">
              <span className="font-headline-md text-headline-md text-on-surface">
                #DOS-2024-884
              </span>
              <span className="bg-surface-container-high text-primary-container px-space-xs py-0.5 rounded font-code-sm text-code-sm font-semibold">
                v3.2
              </span>
              <span className="bg-surface-container-low text-on-surface-variant px-space-xs py-0.5 rounded font-label-sm text-label-sm">
                Hợp đồng Cung cấp Dịch vụ Viễn thông & Hạ tầng Đám mây
              </span>
            </div>
          </div>
          <div className="flex items-center gap-space-sm">
            <button
              className="flex items-center gap-space-xs bg-surface-container hover:bg-surface-container-high text-on-surface px-space-md py-1.5 rounded font-label-md text-label-md transition-colors shadow-sm disabled:opacity-80"
              disabled={exportState !== 'idle'}
              type="button"
              onClick={handleExport}
            >
              {exportState === 'idle' ? (
                <>
                  <MaterialIcon name="file_download" className="text-[16px]" />
                  <span>Xuất file Audit Log (CSV/PDF)</span>
                </>
              ) : null}
              {exportState === 'saving' ? (
                <>
                  <MaterialIcon
                    name="refresh"
                    className="text-[16px] animate-spin"
                  />
                  <span>Đang xuất...</span>
                </>
              ) : null}
              {exportState === 'done' ? (
                <>
                  <MaterialIcon name="check" className="text-[16px]" />
                  <span>Đã xuất CSV</span>
                </>
              ) : null}
            </button>
            <button
              className="flex items-center gap-space-xs bg-surface-container-lowest hover:bg-surface-container text-on-surface-variant px-space-md py-1.5 rounded font-label-md text-label-md transition-colors"
              type="button"
            >
              <MaterialIcon name="tune" className="text-[16px]" />
              <span>Cài đặt lưu vết</span>
            </button>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-space-sm py-space-xs bg-surface-container-low px-space-md rounded">
          <div className="flex items-center gap-space-md text-secondary font-label-sm text-label-sm flex-wrap">
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-[9999px] bg-primary-container" />
              Bên A:{' '}
              <strong className="text-on-surface font-semibold">
                Tập đoàn VNPT
              </strong>
            </span>
            <span className="text-outline-variant">•</span>
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-[9999px] bg-secondary" />
              Bên B:{' '}
              <strong className="text-on-surface font-semibold">
                ApexCorp Vietnam JSC
              </strong>
            </span>
            <span className="text-outline-variant">•</span>
            <span>
              Cập nhật:{' '}
              <span className="font-code-sm text-code-sm text-on-surface font-medium">
                14:28 - 24/10/2024
              </span>
            </span>
          </div>
          <div className="flex items-center gap-space-sm font-code-sm text-code-sm text-on-surface-variant">
            <MaterialIcon
              name="verified"
              className="text-[14px] text-on-tertiary-container"
            />
            <span>Cơ chế đồng thuận: SOC-2 TYPE II IMMUTABLE</span>
          </div>
        </div>

        <div className="flex items-center gap-space-xl pt-space-xs flex-wrap">
          {tabs.map((item) => {
            const active = tab === item.id
            return (
              <button
                key={item.id}
                className={`relative pb-space-sm font-title-sm text-title-sm flex items-center gap-space-xs transition-colors ${
                  active
                    ? 'text-on-surface font-bold'
                    : 'text-secondary hover:text-on-surface'
                }`}
                type="button"
                onClick={() => {
                  if (item.id === 'clauses') {
                    navigate('/doi-soat-xung-dot')
                    return
                  }
                  setTab(item.id)
                }}
              >
                <MaterialIcon
                  name={item.icon}
                  className={`text-[18px] ${active && item.id === 'activity' ? 'text-primary-container' : ''}`}
                />
                <span>{item.label}</span>
                {item.badge ? (
                  <span className="bg-primary-container text-on-primary px-space-xs py-0.5 rounded font-code-sm text-code-sm font-semibold">
                    {item.badge}
                  </span>
                ) : null}
                {active ? (
                  <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary-container" />
                ) : null}
              </button>
            )
          })}
        </div>
      </div>

      {tab === 'search' ? (
        <>
          <div className="w-full flex flex-col items-center justify-center py-1 gap-2">
            <form
              className="w-full max-w-3xl relative flex items-center bg-surface-container-lowest border border-outline-variant/40 shadow-md hover:shadow-lg transition-all px-4 py-2 group focus-within:border-primary focus-within:shadow-lg"
              style={{ borderRadius: '9999px' }}
              onSubmit={handleSearch}
            >
              <MaterialIcon
                name="search"
                className="text-[22px] text-secondary group-focus-within:text-primary transition-colors mr-3 flex-shrink-0"
              />
              <input
                ref={searchRef}
                className="w-full bg-transparent text-on-surface font-body-md text-body-md placeholder:text-secondary focus:outline-none border-none py-1"
                placeholder="Đặt câu hỏi hoặc tìm kiếm trong hồ sơ này..."
                type="search"
                value={query}
                onChange={(event) => {
                  setQuery(event.target.value)
                  if (event.target.value.trim().length === 0) {
                    setShowResults(false)
                  }
                }}
              />
              <div className="flex items-center gap-2 ml-3 flex-shrink-0">
                <button
                  className="w-8 h-8 flex items-center justify-center text-secondary hover:text-primary hover:bg-surface-container transition-colors"
                  style={{ borderRadius: '9999px' }}
                  title="Nhập bằng giọng nói"
                  type="button"
                >
                  <MaterialIcon name="mic" className="text-[18px]" />
                </button>
                <div className="h-4 w-px bg-outline-variant/30" />
                <span
                  className="font-code-sm text-[11px] text-secondary bg-surface-container-low px-2 py-0.5 border border-outline-variant/20 tracking-wide font-medium"
                  style={{ borderRadius: '9999px' }}
                >
                  Ctrl K
                </span>
              </div>
            </form>

            {showResults ? (
              <div className="flex items-center gap-space-md font-label-sm text-label-sm text-secondary pt-1">
                <span className="flex items-center gap-1 text-[#059669] font-medium">
                  <MaterialIcon name="check_circle" className="text-[16px]" />
                  Tìm thấy 4 đoạn trích dẫn có liên quan
                </span>
                <span>•</span>
                <span>
                  Độ tin cậy: <strong className="text-on-surface">98.4%</strong>
                </span>
                <span>•</span>
                <span>Quét qua 48 trang hồ sơ (0.34s)</span>
              </div>
            ) : (
              <button
                className="font-label-sm text-label-sm text-secondary hover:text-primary transition-colors pt-1"
                type="button"
                onClick={runSampleSearch}
              >
                Thử câu hỏi: mức trần bồi thường thiệt hại & phạt vi phạm SLA
              </button>
            )}
          </div>

          {showResults ? <DossierSearchResults /> : <ContractMindmap />}
        </>
      ) : null}

      {tab === 'activity' ? <DossierAuditLog /> : null}

      {tab === 'clauses' || tab === 'risk' ? (
        <div className="bg-surface-container-lowest p-space-lg rounded-xl shadow-sm">
          <h2 className="font-headline-md text-headline-md text-on-surface">
            {tab === 'clauses'
              ? 'Đối chiếu Điều khoản Mẫu'
              : 'Đánh giá Rủi ro Pháp lý'}
          </h2>
          <p className="font-body-sm text-body-sm text-secondary mt-space-xs">
            Giao diện Stitch cho mục này sẽ được ghép khi bạn gửi code.
          </p>
        </div>
      ) : null}
    </div>
  )
}
