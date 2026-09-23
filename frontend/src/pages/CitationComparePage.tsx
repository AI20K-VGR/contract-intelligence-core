import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { MaterialIcon } from '../components/icons'
import { useAuth } from '../auth/useAuth'
import { usePageTitle } from '../hooks/usePageTitle'

type Verdict = 'correct' | 'deviation' | 'edit'
type SaveState = 'idle' | 'saving' | 'saved'

const relatedCitations = [
  {
    id: 1,
    title: 'Khoản 6.2 - Trần trách nhiệm bồi thường',
    meta: 'Hiện tại',
    current: true,
  },
  { id: 2, title: 'Khoản 7.4 - Nghĩa vụ bảo mật', meta: 'Tr. 15' },
  { id: 3, title: 'Khoản 11.1 - Cơ quan tài phán VIAC', meta: 'Tr. 28' },
] as const

function verdictClass(active: boolean) {
  return active
    ? 'flex items-center justify-center gap-1 py-1 px-space-xs rounded bg-primary-container text-on-primary font-label-sm text-label-sm font-semibold transition-colors shadow-sm'
    : 'flex items-center justify-center gap-1 py-1 px-space-xs rounded bg-surface-container hover:bg-surface-container-high text-on-surface-variant font-label-sm text-label-sm font-medium transition-colors'
}

export function CitationComparePage() {
  usePageTitle('Đối soát trích dẫn')
  const { user } = useAuth()
  const navigate = useNavigate()
  const [verdict, setVerdict] = useState<Verdict>('correct')
  const [note, setNote] = useState(
    'Điều khoản phù hợp thông lệ viễn thông; lưu ý ngoại trừ nghĩa vụ bảo mật tại Điều 7.',
  )
  const [saveState, setSaveState] = useState<SaveState>('idle')
  const [page, setPage] = useState(12)
  const [zoom, setZoom] = useState(100)
  const [relatedId, setRelatedId] = useState(1)

  function adjustZoom(delta: number) {
    setZoom((current) => Math.min(140, Math.max(80, current + delta)))
  }

  function handleSave() {
    if (saveState !== 'idle') return
    setSaveState('saving')
    window.setTimeout(() => {
      setSaveState('saved')
      window.setTimeout(() => setSaveState('idle'), 1500)
    }, 600)
  }

  return (
    <div className="flex flex-col w-full">
      <div className="flex flex-wrap items-center justify-between gap-space-sm mb-space-md">
        <div className="flex items-center gap-space-md">
          <Link
            className="inline-flex items-center gap-space-xs px-space-md py-space-xs bg-surface-container-lowest text-on-surface hover:bg-surface-container-high rounded transition-colors shadow-sm font-label-md text-label-md"
            to="/ho-so-hop-dong"
            state={{ showSearch: true }}
          >
            <MaterialIcon name="arrow_back" className="text-[16px]" />
            <span>Quay lại kết quả tìm kiếm</span>
          </Link>
          <div className="h-4 w-px bg-outline-variant" />
          <div className="flex items-center gap-space-xs font-code-sm text-code-sm text-secondary">
            <span className="text-on-surface font-semibold">#DOS-2024-884</span>
            <span>/</span>
            <span className="text-on-tertiary-fixed-variant bg-tertiary-fixed px-space-xs py-0.5 rounded font-medium">
              Đối soát trích dẫn [1]
            </span>
            <span>/</span>
            <span className="text-on-surface-variant">
              Điều 6.2 (Giới hạn trách nhiệm)
            </span>
          </div>
        </div>
        <div className="flex items-center gap-space-sm">
          <div className="flex items-center gap-space-xs bg-surface-container-lowest px-space-md py-1 rounded shadow-sm">
            <span className="w-2 h-2 rounded-[9999px] bg-[#059669] animate-pulse" />
            <span className="font-label-sm text-label-sm text-on-surface-variant font-medium">
              Bản ghi có hiệu lực chứng thư điện tử
            </span>
          </div>
          <div className="flex items-center gap-space-xs bg-primary-container text-on-primary px-space-md py-1 rounded font-label-sm text-label-sm font-semibold">
            <MaterialIcon name="verified" className="text-[15px]" />
            <span>SOC2 TYPE II AUDIT</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-space-lg items-start">
        <div className="col-span-12 lg:col-span-5 flex flex-col gap-space-md">
          <div className="bg-surface-container-lowest rounded shadow-sm p-space-md flex flex-col gap-space-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-space-xs">
                <MaterialIcon
                  name="fact_check"
                  className="text-[18px] text-on-tertiary-container"
                />
                <span className="font-label-md text-label-md text-on-surface font-bold uppercase tracking-wide">
                  Thẩm định trích dẫn [1]
                </span>
              </div>
              <div className="flex items-center gap-1">
                <span className="bg-surface-container-low text-[#059669] px-2 py-0.5 rounded font-label-sm text-label-sm font-semibold flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-[9999px] bg-[#059669]" />
                  Độ tin cậy: 99.2%
                </span>
                <span className="bg-surface-container text-on-surface px-2 py-0.5 rounded font-code-sm text-code-sm font-medium">
                  Trang {page} / 48
                </span>
              </div>
            </div>

            <div className="p-space-sm bg-surface-container-low rounded border border-surface-container">
              <p className="font-body-md text-body-md text-on-surface leading-relaxed">
                “...mức trần bồi thường thiệt hại được giới hạn{' '}
                <span className="bg-surface-container-highest font-semibold text-primary px-1 py-0.5 rounded">
                  không vượt quá 100% tổng giá trị dịch vụ thực tế
                </span>{' '}
                mà bên sử dụng đã thanh toán trong 06 tháng liền kề...”
              </p>
            </div>

            <div className="flex flex-col gap-space-xs pt-space-xs">
              <div className="flex items-center justify-between text-secondary font-label-sm text-label-sm">
                <span className="font-semibold text-on-surface-variant uppercase tracking-wider">
                  Nhận định của chuyên viên
                </span>
                <span>{user?.name ?? 'LS. Trần Nam'}</span>
              </div>

              <div className="grid grid-cols-3 gap-1">
                <button
                  className={verdictClass(verdict === 'correct')}
                  type="button"
                  onClick={() => setVerdict('correct')}
                >
                  <MaterialIcon name="check_circle" className="text-[14px]" />
                  <span>Chính xác</span>
                </button>
                <button
                  className={verdictClass(verdict === 'deviation')}
                  type="button"
                  onClick={() => setVerdict('deviation')}
                >
                  <MaterialIcon name="cancel" className="text-[14px]" />
                  <span>Sai lệch</span>
                </button>
                <button
                  className={verdictClass(verdict === 'edit')}
                  type="button"
                  onClick={() => navigate('/nhan-xet-chinh-sua')}
                >
                  <MaterialIcon name="edit_note" className="text-[14px]" />
                  <span>Sửa nhận định</span>
                </button>
              </div>

              <div className="flex flex-col gap-space-xs mt-1">
                <textarea
                  className="w-full p-space-xs bg-surface-container-low text-on-surface font-body-sm text-body-sm rounded outline-none focus:bg-surface-container-lowest focus:ring-1 focus:ring-outline-variant transition-all resize-none placeholder:text-outline"
                  placeholder="Ghi chú thẩm định..."
                  rows={2}
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                />
                <div className="flex justify-end pt-1">
                  <button
                    className="inline-flex items-center gap-1 px-space-md py-1 bg-primary hover:bg-primary-container text-on-primary rounded font-label-sm text-label-sm font-semibold transition-all shadow-sm disabled:opacity-80"
                    disabled={saveState !== 'idle'}
                    type="button"
                    onClick={handleSave}
                  >
                    {saveState === 'idle' ? (
                      <>
                        <MaterialIcon name="save" className="text-[15px]" />
                        <span>Lưu thẩm định</span>
                      </>
                    ) : null}
                    {saveState === 'saving' ? (
                      <>
                        <MaterialIcon
                          name="refresh"
                          className="text-[16px] animate-spin"
                        />
                        <span>Đang ghi sổ...</span>
                      </>
                    ) : null}
                    {saveState === 'saved' ? (
                      <>
                        <MaterialIcon name="check" className="text-[16px]" />
                        <span>Đã lưu thành công</span>
                      </>
                    ) : null}
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-surface-container-lowest rounded shadow-sm p-space-sm flex flex-col gap-space-xs">
            <div className="flex items-center justify-between px-1">
              <span className="font-label-sm text-label-sm uppercase text-secondary font-semibold">
                Trích dẫn liên đới
              </span>
              <span className="font-code-sm text-code-sm text-secondary">
                3 điều khoản
              </span>
            </div>
            <div className="flex flex-col gap-1">
              {relatedCitations.map((item) => {
                const current = relatedId === item.id
                return (
                  <button
                    key={item.id}
                    className={`flex items-center justify-between px-space-sm py-1 rounded transition-colors text-left ${
                      current
                        ? 'bg-surface-container-low'
                        : 'hover:bg-surface-container-low text-on-surface-variant'
                    }`}
                    type="button"
                    onClick={() => setRelatedId(item.id)}
                  >
                    <div className="flex items-center gap-space-xs truncate">
                      <span
                        className={`w-4 h-4 rounded text-[10px] font-bold flex items-center justify-center shrink-0 ${
                          current
                            ? 'bg-primary-container text-on-primary'
                            : 'bg-surface-container-high text-on-surface'
                        }`}
                      >
                        {item.id}
                      </span>
                      <span
                        className={`font-body-sm text-body-sm truncate ${
                          current ? 'text-on-surface font-medium' : ''
                        }`}
                      >
                        {item.title}
                      </span>
                    </div>
                    <span
                      className={`font-label-sm text-label-sm shrink-0 ml-2 ${
                        current
                          ? 'text-[#059669] font-semibold'
                          : 'text-secondary'
                      }`}
                    >
                      {current ? 'Hiện tại' : item.meta}
                    </span>
                  </button>
                )
              })}
            </div>
          </div>
        </div>

        <div className="col-span-12 lg:col-span-7 flex flex-col bg-surface-container-lowest rounded shadow-sm overflow-hidden">
          <div className="px-space-md py-space-sm bg-surface-container flex flex-wrap items-center justify-between gap-space-sm">
            <div className="flex items-center gap-space-sm min-w-0">
              <MaterialIcon
                name="picture_as_pdf"
                className="text-[18px] text-error"
              />
              <div className="flex flex-col min-w-0">
                <span className="font-title-sm text-title-sm text-on-surface truncate font-semibold">
                  HopDong_DichVu_CNTT_VNPT_v3.2.pdf
                </span>
                <span className="font-label-sm text-label-sm text-secondary">
                  Bản gốc có chữ ký số điện tử CA • Cấp bảo mật: Lưu hành nội bộ
                </span>
              </div>
            </div>
            <div className="flex items-center gap-space-xs">
              <div className="flex items-center bg-surface-container-lowest rounded px-space-xs py-0.5 shadow-sm">
                <button
                  className="w-6 h-6 flex items-center justify-center text-on-surface-variant hover:text-on-surface"
                  title="Trang trước"
                  type="button"
                  onClick={() => setPage((current) => Math.max(1, current - 1))}
                >
                  <MaterialIcon name="chevron_left" className="text-[16px]" />
                </button>
                <span className="font-code-sm text-code-sm px-space-xs text-on-surface font-semibold">
                  {page} / 48
                </span>
                <button
                  className="w-6 h-6 flex items-center justify-center text-on-surface-variant hover:text-on-surface"
                  title="Trang sau"
                  type="button"
                  onClick={() =>
                    setPage((current) => Math.min(48, current + 1))
                  }
                >
                  <MaterialIcon name="chevron_right" className="text-[16px]" />
                </button>
              </div>
              <div className="h-4 w-px bg-outline-variant" />
              <div className="flex items-center bg-surface-container-lowest rounded shadow-sm">
                <button
                  className="w-7 h-7 flex items-center justify-center text-on-surface-variant hover:text-on-surface"
                  title="Thu nhỏ"
                  type="button"
                  onClick={() => adjustZoom(-5)}
                >
                  <MaterialIcon name="remove" className="text-[16px]" />
                </button>
                <span className="font-code-sm text-code-sm px-space-xs text-secondary font-medium">
                  {zoom}%
                </span>
                <button
                  className="w-7 h-7 flex items-center justify-center text-on-surface-variant hover:text-on-surface"
                  title="Phóng to"
                  type="button"
                  onClick={() => adjustZoom(5)}
                >
                  <MaterialIcon name="add" className="text-[16px]" />
                </button>
              </div>
              <button
                className="w-7 h-7 flex items-center justify-center bg-surface-container-lowest text-on-surface-variant hover:text-on-surface rounded shadow-sm"
                title="Tìm trong trang"
                type="button"
              >
                <MaterialIcon name="search" className="text-[16px]" />
              </button>
              <button
                className="w-7 h-7 flex items-center justify-center bg-surface-container-lowest text-on-surface-variant hover:text-on-surface rounded shadow-sm"
                title="Tải xuống bản gốc"
                type="button"
              >
                <MaterialIcon name="download" className="text-[16px]" />
              </button>
            </div>
          </div>

          <div className="p-space-lg bg-surface-dim overflow-y-auto max-h-[820px] flex justify-center">
            <div
              className="w-full max-w-[680px] bg-surface-container-lowest shadow-md p-space-xl flex flex-col gap-space-md text-on-surface select-text relative origin-top duration-150"
              style={{ transform: `scale(${zoom / 100})` }}
            >
              <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-[0.03] select-none">
                <span className="text-display-lg font-bold tracking-widest text-on-surface -rotate-45">
                  LEXIS SOVEREIGN AUDIT
                </span>
              </div>
              <div className="flex flex-col items-center text-center pb-space-sm">
                <span className="font-label-md text-label-md uppercase tracking-wider font-bold">
                  CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
                </span>
                <span className="font-label-sm text-label-sm font-medium">
                  Độc lập - Tự do - Hạnh phúc
                </span>
                <div className="w-24 h-0.5 bg-on-surface mt-1" />
                <span className="font-code-sm text-code-sm text-secondary mt-space-sm">
                  Số: 884/2024/HĐDV-VNPT-FINTECH
                </span>
              </div>
              <div className="mt-space-xs">
                <h3 className="font-title-sm text-title-sm uppercase font-bold text-center tracking-wide">
                  ĐIỀU 6: TRÁCH NHIỆM BỒI THƯỜNG VÀ GIỚI HẠN NGHĨA VỤ
                </h3>
              </div>
              <div className="flex flex-col gap-space-md font-body-md text-body-md leading-relaxed text-justify">
                <p>
                  <strong className="font-semibold">
                    Khoản 6.1 (Các trường hợp vi phạm nghĩa vụ hợp đồng):
                  </strong>{' '}
                  Trong trường hợp một trong hai Bên vi phạm bất kỳ cam kết,
                  nghĩa vụ hoặc thỏa thuận nào quy định tại Hợp đồng này mà
                  không khắc phục được trong thời hạn ba mươi (30) ngày kể từ
                  ngày nhận được thông báo bằng văn bản từ Bên không vi phạm,
                  Bên bị vi phạm có quyền áp dụng các chế tài theo thỏa thuận và
                  quy định của pháp luật hiện hành.
                </p>
                <div className="relative bg-surface-container-highest p-space-md rounded shadow-sm">
                  <div className="flex items-center justify-between mb-space-xs">
                    <span className="inline-flex items-center gap-space-xs bg-primary-container text-on-primary px-space-xs py-0.5 rounded font-label-sm text-label-sm font-bold">
                      <MaterialIcon name="pin_drop" className="text-[14px]" />
                      [1] TRÍCH DẪN MỤC TIÊU CẦN ĐỐI SOÁT
                    </span>
                    <span className="font-code-sm text-code-sm text-on-tertiary-fixed-variant font-semibold">
                      Tọa độ: P12_L24-L31
                    </span>
                  </div>
                  <p className="font-medium text-on-surface">
                    <strong className="font-semibold text-primary">
                      Khoản 6.2 (Giới hạn mức bồi thường tối đa):
                    </strong>{' '}
                    Trong mọi trường hợp phát sinh lỗi trực tiếp từ Bên Cung
                    Cấp,{' '}
                    <span className="bg-surface-container font-semibold px-1 py-0.5 rounded text-on-surface">
                      tổng mức bồi thường thiệt hại thực tế không vượt quá 100%
                      tổng giá trị dịch vụ thực tế mà Bên Sử Dụng đã thanh toán
                      trong 06 (sáu) tháng liền kề
                    </span>{' '}
                    trước thời điểm xảy ra sự cố kỹ thuật hoặc tranh chấp.
                  </p>
                </div>
                <p>
                  <strong className="font-semibold">
                    Khoản 6.3 (Thủ tục yêu cầu bồi thường):
                  </strong>{' '}
                  Bên yêu cầu bồi thường phải gửi thông báo chi tiết bằng văn
                  bản kèm theo các bằng chứng, hóa đơn, chứng từ hợp lệ chứng
                  minh thiệt hại thực tế phát sinh trong thời hạn không quá bốn
                  mươi lăm (45) ngày kể từ thời điểm phát hiện thiệt hại. Mọi
                  yêu cầu vượt quá thời hạn trên sẽ được xem là đương nhiên từ
                  bỏ quyền khiếu nại đối với sự kiện đó.
                </p>
                <p>
                  <strong className="font-semibold">
                    Khoản 6.4 (Miễn trừ trách nhiệm đối với thiệt hại gián
                    tiếp):
                  </strong>{' '}
                  Các Bên thống nhất loại trừ và không chịu trách nhiệm đối với
                  bất kỳ tổn thất gián tiếp nào, bao gồm nhưng không giới hạn ở:
                  mất cơ hội kinh doanh, suy giảm doanh thu dự kiến, giảm sút
                  lợi nhuận hoặc thiệt hại về danh tiếng thương hiệu của Bên
                  kia, trừ trường hợp hành vi đó là cố ý vi phạm nghiêm trọng
                  theo phán quyết có hiệu lực của cơ quan tài phán có thẩm
                  quyền.
                </p>
              </div>
              <div className="mt-space-lg pt-space-md bg-surface-container-low p-space-sm rounded flex flex-col gap-space-xs">
                <div className="flex items-center justify-between font-label-sm text-label-sm">
                  <span className="text-secondary">
                    Trang {page} của Hợp đồng số 884/2024/HĐDV-VNPT-FINTECH
                  </span>
                  <span className="font-code-sm text-code-sm text-on-surface-variant">
                    Ký số điện tử: VNPT-CA / SHA-256 Validated
                  </span>
                </div>
                <div className="flex items-center justify-between font-code-sm text-code-sm text-secondary">
                  <span className="truncate">
                    Mã băm khối:{' '}
                    <span className="text-on-surface font-semibold">
                      9fa8b12c7d...e4a198
                    </span>
                  </span>
                  <span className="text-[#059669] font-medium flex items-center gap-1">
                    <MaterialIcon name="verified" className="text-[13px]" />
                    Toàn vẹn dữ liệu
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="px-space-md py-space-xs bg-surface-container flex flex-wrap items-center justify-between text-secondary font-label-sm text-label-sm">
            <div className="flex items-center gap-space-md">
              <span className="flex items-center gap-1">
                <MaterialIcon
                  name="history_edu"
                  className="text-[15px] text-on-tertiary-container"
                />
                Thẩm định bởi:{' '}
                <strong className="text-on-surface font-semibold">
                  {user?.name ?? 'Trần Nam'} (GC-Level)
                </strong>
              </span>
              <span>•</span>
              <span>
                Phiên bản tài liệu: <strong>v3.2 Final Signed</strong>
              </span>
            </div>
            <div className="flex items-center gap-space-xs font-code-sm text-code-sm">
              <span>Thời gian đối soát: 14:32:09 GMT+7</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
