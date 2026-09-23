import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { MaterialIcon } from '../components/icons'
import {
  splitCitations,
  splitSearchQuery,
  totalPdfPages,
  type SplitCitation,
  type SplitVerdict,
} from '../data/citationSplitView'
import { usePageTitle } from '../hooks/usePageTitle'

type ReviewTab = 'search' | 'activity'

const backState = { showSearch: true }

function citationByPage(page: number) {
  return splitCitations.find((item) => item.page === page)
}

function verdictButtonClass(active: boolean, kind: SplitVerdict) {
  if (active) {
    return 'h-7 px-2 bg-primary-container hover:bg-tertiary-container text-on-primary rounded font-label-sm text-label-sm flex items-center justify-center gap-1 transition-colors'
  }
  if (kind === 'deviation') {
    return 'h-7 px-2 bg-surface-container-lowest hover:bg-surface-container border border-outline-variant text-on-surface rounded font-label-sm text-label-sm flex items-center justify-center gap-1 transition-colors'
  }
  return 'h-7 px-2 bg-surface-container-lowest hover:bg-surface-container border border-outline-variant/70 text-on-surface rounded font-label-sm text-label-sm flex items-center justify-center gap-1 transition-colors'
}

function CitationCard({
  citation,
  active,
  verdict,
  note,
  onActivate,
  onVerdict,
  onNote,
  onEdit,
}: {
  citation: SplitCitation
  active: boolean
  verdict: SplitVerdict
  note: string
  onActivate: () => void
  onVerdict: (verdict: SplitVerdict) => void
  onNote: (value: string) => void
  onEdit: () => void
}) {
  return (
    <div
      className={
        active
          ? 'p-space-md bg-blue-50/50 rounded border-l-4 border-l-primary-container border-y border-r border-outline-variant/50 shadow-sm relative'
          : 'p-space-md bg-surface-container-lowest rounded border border-outline-variant/50 hover:border-outline transition-colors'
      }
    >
      <div className="flex items-start justify-between gap-space-sm mb-space-xs">
        <button
          className="flex items-center gap-space-sm text-left min-w-0"
          type="button"
          onClick={onActivate}
        >
          <span
            className={`w-5 h-5 rounded-[9999px] flex items-center justify-center font-code-sm text-code-sm font-bold shrink-0 ${
              active
                ? 'bg-primary-container text-on-primary shadow-sm'
                : 'bg-secondary text-on-secondary'
            }`}
          >
            {citation.id}
          </span>
          <span
            className={`font-label-md text-label-md font-semibold ${
              active ? 'text-primary-container' : 'text-on-surface'
            }`}
          >
            {citation.title}
          </span>
        </button>
        {active ? (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-primary-container text-on-primary font-label-sm text-[10px] rounded uppercase font-semibold shrink-0">
            <MaterialIcon name="visibility" className="text-[12px]" /> Đang xem
            trên PDF
          </span>
        ) : (
          <button
            className="text-secondary hover:text-primary-container font-label-sm text-label-sm flex items-center gap-0.5 shrink-0"
            type="button"
            onClick={onActivate}
          >
            <span>Đến trang {citation.page}</span>
            <MaterialIcon name="arrow_forward" className="text-[14px]" />
          </button>
        )}
      </div>
      <p
        className={`font-body-sm text-body-sm mb-space-sm p-2 rounded leading-normal ${
          active
            ? 'text-on-surface font-medium bg-white/80 border border-outline-variant/30'
            : 'text-on-surface-variant bg-surface-container-low/60 border border-outline-variant/20'
        }`}
      >
        {citation.quote}
      </p>
      <div className="flex flex-wrap items-center justify-between gap-space-xs text-secondary font-label-sm text-label-sm pt-space-xs border-t border-outline-variant/30 mb-space-sm">
        <span
          className={`font-code-sm text-code-sm text-on-surface-variant ${active ? 'font-medium' : ''}`}
        >
          Căn cứ: {citation.source}
        </span>
        <span
          className={`font-code-sm text-code-sm ${
            active ? 'text-tertiary-container font-semibold' : 'text-secondary'
          }`}
        >
          Độ tin cậy: {citation.confidence}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-1.5">
        <button
          className={verdictButtonClass(verdict === 'correct', 'correct')}
          type="button"
          onClick={() => onVerdict('correct')}
        >
          <MaterialIcon
            name="check"
            className={`text-[14px] ${verdict === 'correct' ? '' : 'text-tertiary-container'}`}
          />
          <span>Chính xác</span>
        </button>
        <button
          className={verdictButtonClass(verdict === 'deviation', 'deviation')}
          type="button"
          onClick={() => onVerdict('deviation')}
        >
          <MaterialIcon
            name="close"
            className={`text-[14px] ${verdict === 'deviation' ? '' : active ? 'text-error' : 'text-secondary'}`}
          />
          <span>Sai lệch</span>
        </button>
        <button
          className={verdictButtonClass(verdict === 'edit', 'edit')}
          type="button"
          onClick={onEdit}
        >
          <MaterialIcon
            name="edit"
            className={`text-[14px] ${verdict === 'edit' ? '' : 'text-secondary'}`}
          />
          <span>{active ? 'Sửa nhận định' : 'Sửa'}</span>
        </button>
      </div>
      {verdict === 'edit' ? (
        <textarea
          className="mt-space-sm w-full p-space-xs bg-surface-container-low text-on-surface font-body-sm text-body-sm rounded outline-none focus:bg-surface-container-lowest focus:ring-1 focus:ring-outline-variant transition-all resize-none placeholder:text-outline"
          placeholder="Nhập nhận định chỉnh sửa..."
          rows={3}
          value={note}
          onChange={(event) => onNote(event.target.value)}
        />
      ) : null}
    </div>
  )
}

export function CitationSplitViewPage() {
  usePageTitle('Nhận xét chỉnh sửa')
  const navigate = useNavigate()
  const [tab, setTab] = useState<ReviewTab>('search')
  const [activeId, setActiveId] = useState(1)
  const [page, setPage] = useState(3)
  const [zoom, setZoom] = useState(100)
  const [rotation, setRotation] = useState(0)
  const [verdicts, setVerdicts] = useState<Record<number, SplitVerdict>>({
    1: 'correct',
    2: 'none',
    3: 'none',
    4: 'none',
  })
  const [notes, setNotes] = useState<Record<number, string>>({
    1: '',
    2: '',
    3: '',
    4: '',
  })

  const reviewedCount = Object.values(verdicts).filter(
    (item) => item !== 'none',
  ).length
  const document = citationByPage(page)

  function selectCitation(citation: SplitCitation) {
    setActiveId(citation.id)
    setPage(citation.page)
  }

  function changePage(delta: number) {
    setPage((current) => {
      const next = Math.min(totalPdfPages, Math.max(1, current + delta))
      const match = splitCitations.find((item) => item.page === next)
      if (match) {
        setActiveId(match.id)
      }
      return next
    })
  }

  return (
    <div className="flex flex-col w-full">
      <section className="w-full bg-surface-container-lowest border-b border-outline-variant/40 px-space-md py-space-sm mb-space-sm">
        <div className="flex flex-wrap items-center justify-between gap-space-sm">
          <div className="flex flex-wrap items-center gap-space-md">
            <div className="flex items-center gap-space-xs font-label-md text-label-md text-secondary">
              <span>Hồ sơ Hợp đồng</span>
              <span className="text-outline-variant">/</span>
              <span className="text-on-surface font-semibold">
                #DOS-2024-884
              </span>
              <span className="bg-primary-container text-on-primary font-code-sm text-code-sm px-space-xs py-0.5 rounded ml-1">
                v3.2
              </span>
            </div>
            <div className="h-4 w-px bg-outline-variant/60" />
            <nav className="flex items-center gap-1 bg-surface-container-low p-0.5 rounded">
              <button
                className={`px-space-md py-1 rounded font-label-md text-label-md flex items-center gap-1 transition-colors ${
                  tab === 'search'
                    ? 'bg-surface-container-lowest text-primary shadow-sm font-semibold'
                    : 'text-secondary hover:text-on-surface'
                }`}
                type="button"
                onClick={() => setTab('search')}
              >
                <MaterialIcon
                  name="find_in_page"
                  className={`text-[16px] ${tab === 'search' ? 'text-primary' : ''}`}
                />
                <span>Tìm kiếm & Rà soát</span>
              </button>
              <button
                className={`px-space-md py-1 rounded font-label-md text-label-md flex items-center gap-1 transition-colors ${
                  tab === 'activity'
                    ? 'bg-surface-container-lowest text-primary shadow-sm font-semibold'
                    : 'text-secondary hover:text-on-surface'
                }`}
                type="button"
                onClick={() =>
                  navigate('/ho-so-hop-dong', { state: { tab: 'activity' } })
                }
              >
                <MaterialIcon name="history_edu" className="text-[16px]" />
                <span>Nhật ký hoạt động</span>
              </button>
            </nav>
            <div className="hidden lg:flex items-center gap-space-sm text-secondary font-label-sm text-label-sm">
              <span>
                Bên A:{' '}
                <strong className="text-on-surface font-medium">
                  Tập đoàn VNPT
                </strong>
              </span>
              <span className="text-outline-variant">•</span>
              <span>
                Bên B:{' '}
                <strong className="text-on-surface font-medium">
                  ApexCorp Vietnam JSC
                </strong>
              </span>
              <span className="text-outline-variant">•</span>
              <span className="font-code-sm text-code-sm text-on-surface-variant">
                Cập nhật: 14:28 - 24/10/2024
              </span>
            </div>
          </div>
          <div className="flex items-center gap-space-sm">
            <div className="hidden sm:flex items-center gap-1 bg-surface-container px-2 py-1 rounded font-code-sm text-code-sm text-on-surface-variant">
              <MaterialIcon
                name="verified"
                className="text-[14px] text-tertiary-container"
              />
              <span>SOC2 Type II Verified</span>
            </div>
            <button
              className="px-space-md py-1.5 rounded bg-surface-container hover:bg-surface-container-high text-on-surface font-label-md text-label-md flex items-center gap-1.5 transition-colors"
              type="button"
            >
              <MaterialIcon name="share" className="text-[16px]" />
              <span>Chia sẻ</span>
            </button>
            <Link
              className="px-space-md py-1.5 rounded bg-primary-container text-on-primary font-label-md text-label-md flex items-center gap-1.5 hover:bg-tertiary-container transition-colors"
              to="/ho-so-hop-dong"
              state={backState}
            >
              <MaterialIcon name="vertical_split" className="text-[16px]" />
              <span>Thoát Split-view</span>
            </Link>
          </div>
        </div>
      </section>

      <div
        className="grid grid-cols-1 xl:grid-cols-12 gap-0 w-full bg-surface-container-low border border-outline-variant/50 rounded shadow-sm overflow-hidden"
        style={{ minHeight: 'calc(100vh - 150px)' }}
      >
        <div className="xl:col-span-7 flex flex-col bg-slate-200/70 border-r border-outline-variant/60">
          <div className="h-11 bg-surface-container-lowest border-b border-outline-variant/40 px-space-md flex items-center justify-between gap-space-sm">
            <div className="flex items-center gap-space-sm min-w-0">
              <Link
                className="flex items-center gap-1 text-secondary hover:text-on-surface font-label-sm text-label-sm pr-space-xs"
                to="/ho-so-hop-dong"
                state={backState}
              >
                <MaterialIcon name="arrow_back" className="text-[16px]" />
                <span className="hidden md:inline">Danh sách</span>
              </Link>
              <div className="h-4 w-px bg-outline-variant/50" />
              <div className="flex items-center gap-1.5 min-w-0">
                <MaterialIcon
                  name="picture_as_pdf"
                  className="text-[18px] text-error"
                />
                <span
                  className="font-body-sm text-body-sm font-semibold text-on-surface truncate max-w-[210px]"
                  title="HopDong_DichVu_CNTT_VNPT_v3.2.pdf"
                >
                  HopDong_DichVu_CNTT_VNPT_v3.2.pdf
                </span>
                <span className="hidden 2xl:inline-block px-1.5 py-0.5 bg-surface-container-high text-on-secondary-container font-label-sm text-label-sm rounded whitespace-nowrap">
                  Chữ ký số CA • Mật cấp 2
                </span>
              </div>
            </div>
            <div className="flex items-center gap-space-xs">
              <div className="flex items-center bg-surface-container-low rounded px-1 py-0.5 font-label-sm text-label-sm">
                <button
                  className="w-6 h-6 flex items-center justify-center hover:bg-surface-container-highest rounded text-on-surface"
                  type="button"
                  onClick={() => changePage(-1)}
                >
                  <MaterialIcon name="chevron_left" className="text-[14px]" />
                </button>
                <span className="px-1.5 font-code-sm text-code-sm font-medium">
                  {page} / {totalPdfPages}
                </span>
                <button
                  className="w-6 h-6 flex items-center justify-center hover:bg-surface-container-highest rounded text-on-surface"
                  type="button"
                  onClick={() => changePage(1)}
                >
                  <MaterialIcon name="chevron_right" className="text-[14px]" />
                </button>
              </div>
              <div className="hidden sm:flex items-center bg-surface-container-low rounded px-1 py-0.5 font-label-sm text-label-sm">
                <button
                  className="w-6 h-6 flex items-center justify-center hover:bg-surface-container-highest rounded text-on-surface"
                  type="button"
                  onClick={() =>
                    setZoom((current) => Math.max(80, current - 5))
                  }
                >
                  <MaterialIcon name="remove" className="text-[14px]" />
                </button>
                <span className="px-1 font-code-sm text-code-sm">{zoom}%</span>
                <button
                  className="w-6 h-6 flex items-center justify-center hover:bg-surface-container-highest rounded text-on-surface"
                  type="button"
                  onClick={() =>
                    setZoom((current) => Math.min(140, current + 5))
                  }
                >
                  <MaterialIcon name="add" className="text-[14px]" />
                </button>
              </div>
              <button
                className="w-7 h-7 flex items-center justify-center text-secondary hover:text-on-surface hover:bg-surface-container rounded"
                title="Xoay trang"
                type="button"
                onClick={() => setRotation((current) => (current + 90) % 360)}
              >
                <MaterialIcon name="rotate_right" className="text-[16px]" />
              </button>
              <button
                className="w-7 h-7 flex items-center justify-center text-secondary hover:text-on-surface hover:bg-surface-container rounded"
                title="Tìm trong PDF"
                type="button"
              >
                <MaterialIcon name="search" className="text-[16px]" />
              </button>
              <button
                className="w-7 h-7 flex items-center justify-center text-secondary hover:text-on-surface hover:bg-surface-container rounded"
                title="Tải văn bản"
                type="button"
              >
                <MaterialIcon name="download" className="text-[16px]" />
              </button>
            </div>
          </div>

          <div className="flex-1 p-space-md lg:p-space-lg overflow-y-auto flex justify-center bg-slate-200/70">
            <article
              className="w-full max-w-[690px] bg-white text-slate-900 shadow-[0_2px_12px_rgba(0,0,0,0.12)] p-space-lg md:p-12 relative flex flex-col font-serif leading-relaxed text-[13px] border border-slate-300 origin-top transition-transform duration-150"
              style={{
                transform: `rotate(${rotation}deg) scale(${zoom / 100})`,
              }}
            >
              <div className="text-center pb-6 border-b border-slate-300 mb-6 font-sans">
                <p className="font-bold text-[12px] tracking-widest uppercase text-slate-900">
                  CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
                </p>
                <p className="font-semibold text-[11px] text-slate-800">
                  Độc lập - Tự do - Hạnh phúc
                </p>
                <div className="w-24 h-px bg-slate-400 mx-auto my-1.5" />
                <div className="flex justify-between items-center text-[10px] text-slate-600 mt-2 font-mono">
                  <span>Số: 884/2024/HĐDV-VNPT-FINTECH</span>
                  <span>Hà Nội, ngày 18 tháng 10 năm 2024</span>
                </div>
              </div>
              <div className="space-y-4 text-slate-800 text-justify">
                {document ? (
                  <>
                    <h4 className="font-sans font-bold text-[13px] tracking-tight uppercase text-center text-primary-container mb-3">
                      {document.articleTitle}
                    </h4>
                    {document.clauses.map((clause) =>
                      clause.highlight ? (
                        <div
                          key={clause.heading}
                          className="relative pl-3 my-2 font-sans"
                        >
                          <div className="absolute -left-3.5 top-0 bottom-0 w-1.5 bg-primary-container rounded-sm" />
                          <div className="absolute -left-24 top-0 hidden lg:flex items-center gap-1 bg-primary-container text-on-primary px-1.5 py-0.5 rounded shadow-sm text-[10px] font-mono">
                            <MaterialIcon
                              name="verified"
                              className="text-[12px]"
                            />
                            <span>[{document.id}] Đang rà soát</span>
                          </div>
                          <p className="leading-relaxed bg-amber-100/90 text-amber-950 p-2.5 rounded border border-amber-300 shadow-sm font-medium">
                            <strong>{clause.heading}</strong> {clause.body}
                          </p>
                        </div>
                      ) : (
                        <p
                          key={clause.heading}
                          className={`font-sans leading-normal ${clause.heading.startsWith('Khoản 5.4') ? 'text-slate-600' : ''}`}
                        >
                          <strong>{clause.heading}</strong> {clause.body}
                        </p>
                      ),
                    )}
                  </>
                ) : (
                  <p className="font-sans leading-normal text-slate-600 text-center py-12">
                    Trang {page} không nằm trong các điểm trích dẫn đang rà
                    soát.
                  </p>
                )}
              </div>
              <div className="mt-12 pt-4 border-t border-slate-200 flex justify-between items-center text-[10px] text-slate-500 font-mono">
                <span>Mã bảo mật SHA-256: {document?.hash ?? '—'}</span>
                <span>
                  {document?.footerNote ?? `Trang ${page} / ${totalPdfPages}`}
                </span>
              </div>
            </article>
          </div>
        </div>

        <div className="xl:col-span-5 flex flex-col bg-surface-container-lowest">
          <div className="p-space-md border-b border-outline-variant/40 bg-surface-bright space-y-space-sm">
            <div className="relative">
              <MaterialIcon
                name="search"
                className="absolute left-2.5 top-2.5 text-[18px] text-secondary"
              />
              <input
                className="w-full h-9 pl-9 pr-14 bg-surface-container-low border border-outline-variant/60 rounded text-body-sm font-body-sm text-on-surface focus:outline-none focus:border-primary-container focus:ring-1 focus:ring-primary-container"
                readOnly
                type="text"
                value={splitSearchQuery}
              />
              <span className="absolute right-2 top-2 bg-surface-container px-1.5 py-0.5 rounded font-code-sm text-code-sm text-secondary">
                Ctrl+K
              </span>
            </div>
            <div className="flex items-center justify-between font-label-sm text-label-sm pt-0.5">
              <div className="flex items-center gap-1.5 text-primary-container font-semibold uppercase tracking-wider">
                <MaterialIcon
                  name="fact_check"
                  className="text-[16px] text-primary-container"
                />
                <span>CÂU TRẢ LỜI TỔNG HỢP & 4 ĐIỂM TRÍCH DẪN</span>
              </div>
              <span className="font-code-sm text-code-sm text-secondary">
                Độ chuẩn xác 98.2%
              </span>
            </div>
            <div className="p-space-sm bg-surface-container-low rounded border border-outline-variant/30 text-on-surface-variant font-body-sm text-body-sm leading-snug">
              Hồ sơ ghi nhận hạn mức trần dự phòng là 550 triệu VND
              <button
                className={`inline-flex items-center justify-center w-4 h-4 rounded-[9999px] font-code-sm text-[10px] font-bold mx-0.5 ${
                  activeId === 1
                    ? 'bg-primary-container text-on-primary'
                    : 'bg-secondary text-on-secondary'
                }`}
                type="button"
                onClick={() => selectCitation(splitCitations[0])}
              >
                1
              </button>
              , trần bồi thường không vượt 100% chi phí 06 tháng
              <button
                className={`inline-flex items-center justify-center w-4 h-4 rounded-[9999px] font-code-sm text-[10px] font-bold mx-0.5 ${
                  activeId === 2
                    ? 'bg-primary-container text-on-primary'
                    : 'bg-secondary text-on-secondary'
                }`}
                type="button"
                onClick={() => selectCitation(splitCitations[1])}
              >
                2
              </button>
              , loại trừ hoàn toàn tổn thất gián tiếp
              <button
                className={`inline-flex items-center justify-center w-4 h-4 rounded-[9999px] font-code-sm text-[10px] font-bold mx-0.5 ${
                  activeId === 3
                    ? 'bg-primary-container text-on-primary'
                    : 'bg-secondary text-on-secondary'
                }`}
                type="button"
                onClick={() => selectCitation(splitCitations[2])}
              >
                3
              </button>
              và cơ chế hoãn SLA trong sự kiện bất khả kháng
              <button
                className={`inline-flex items-center justify-center w-4 h-4 rounded-[9999px] font-code-sm text-[10px] font-bold mx-0.5 ${
                  activeId === 4
                    ? 'bg-primary-container text-on-primary'
                    : 'bg-secondary text-on-secondary'
                }`}
                type="button"
                onClick={() => selectCitation(splitCitations[3])}
              >
                4
              </button>
              .
            </div>
          </div>

          <div className="flex-1 p-space-md space-y-space-sm overflow-y-auto">
            {splitCitations.map((citation) => (
              <CitationCard
                key={citation.id}
                citation={citation}
                active={activeId === citation.id}
                verdict={verdicts[citation.id] ?? 'none'}
                note={notes[citation.id] ?? ''}
                onActivate={() => selectCitation(citation)}
                onEdit={() => navigate('/chinh-sua-trich-dan')}
                onVerdict={(verdict) =>
                  setVerdicts((current) => ({
                    ...current,
                    [citation.id]: verdict,
                  }))
                }
                onNote={(value) =>
                  setNotes((current) => ({
                    ...current,
                    [citation.id]: value,
                  }))
                }
              />
            ))}
          </div>

          <div className="p-space-sm border-t border-outline-variant/40 bg-surface-container-low flex items-center justify-between text-secondary font-label-sm text-label-sm">
            <span className="flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-[9999px] bg-tertiary-container" />
              Đã thẩm định {reviewedCount}/4 trích dẫn
            </span>
            <span className="font-code-sm text-code-sm">
              Sovereign Engine v4.8
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
