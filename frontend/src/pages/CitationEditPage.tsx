import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { MaterialIcon } from '../components/icons'
import { editCitations } from '../data/citationEdit'
import { usePageTitle } from '../hooks/usePageTitle'

type DiffTab = 'split' | 'current' | 'previous'
type Decision = 'none' | 'approve' | 'revert'
type SubmitState = 'idle' | 'saving' | 'sent'
type CommentSave = 'idle' | 'saved'

function tabClass(active: boolean) {
  return active
    ? 'px-space-sm py-1 rounded bg-surface-container-lowest text-on-surface font-label-md text-label-md shadow-xs flex items-center gap-1 transition-all'
    : 'px-space-sm py-1 rounded hover:bg-surface-container text-secondary font-label-md text-label-md flex items-center gap-1 transition-all'
}

function decisionClass(active: boolean) {
  return active
    ? 'flex items-center justify-center gap-1.5 px-space-sm py-2 rounded bg-primary-container text-on-primary hover:bg-[#1E293B] transition-all font-label-md text-label-md'
    : 'flex items-center justify-center gap-1.5 px-space-sm py-2 rounded bg-surface-container hover:bg-surface-container-high text-on-surface transition-all font-label-md text-label-md'
}

function PreviousVersion() {
  return (
    <div className="flex flex-col bg-surface-container-lowest rounded p-space-sm shadow-xs">
      <div className="flex items-center justify-between pb-1 mb-1.5 border-b border-surface-container">
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-[9999px] bg-secondary" />
          <span className="font-label-sm text-label-sm font-semibold text-secondary">
            Bản trước đó (v3.1)
          </span>
        </div>
        <span className="font-code-sm text-[11px] text-secondary">
          Trích xuất AI ban đầu
        </span>
      </div>
      <div className="font-body-sm text-body-sm leading-relaxed text-secondary">
        Mức trần chi phí phát sinh nâng cấp hạ tầng giai đoạn 1 được tạm ứng
        không vượt quá{' '}
        <span className="bg-[#FEE2E2] text-[#991B1B] font-semibold line-through px-1 rounded mx-0.5">
          500.000.000 VND
        </span>{' '}
        (Năm trăm triệu đồng) theo biểu giá điều chỉnh thỏa thuận đính kèm.
      </div>
      <div className="mt-2 pt-1 border-t border-surface-container-low flex items-center justify-between text-secondary font-code-sm text-[11px]">
        <span>Tạo lúc: 09:15 - 24/10</span>
        <span>Model: LexisAudit-LLM-4</span>
      </div>
    </div>
  )
}

function CurrentVersion() {
  return (
    <div className="flex flex-col bg-surface-container-lowest rounded p-space-sm shadow-xs border-l-2 border-[#2563EB]">
      <div className="flex items-center justify-between pb-1 mb-1.5 border-b border-surface-container">
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 rounded-[9999px] bg-[#2563EB]" />
          <span className="font-label-sm text-label-sm font-semibold text-[#1E3A8A]">
            Bản hiện tại (v3.2)
          </span>
        </div>
        <span className="font-code-sm text-[11px] text-[#2563EB] font-medium">
          Sửa bởi LS. Trần Nam
        </span>
      </div>
      <div className="font-body-sm text-body-sm leading-relaxed text-on-surface">
        Mức trần chi phí phát sinh nâng cấp hạ tầng giai đoạn 1 được tạm ứng
        không vượt quá{' '}
        <span className="bg-[#DCFCE7] text-[#166534] font-semibold px-1 rounded mx-0.5">
          550.000.000 VND
        </span>{' '}
        (Năm trăm năm mươi triệu đồng) theo biểu giá điều chỉnh thỏa thuận đính
        kèm.
      </div>
      <div className="mt-2 pt-1 border-t border-surface-container-low flex items-center justify-between text-[#2563EB] font-code-sm text-[11px]">
        <span>Chỉnh sửa: 14:28 - 24/10</span>
        <span>Chênh lệch: +50.000.000 VND</span>
      </div>
    </div>
  )
}

export function CitationEditPage() {
  usePageTitle('Chỉnh sửa trích dẫn')
  const navigate = useNavigate()
  const [zoom, setZoom] = useState(115)
  const [rotation, setRotation] = useState(0)
  const [fullscreen, setFullscreen] = useState(false)
  const [diffTab, setDiffTab] = useState<DiffTab>('split')
  const [decision, setDecision] = useState<Decision>('none')
  const [showComment, setShowComment] = useState(false)
  const [comment, setComment] = useState('')
  const [commentSave, setCommentSave] = useState<CommentSave>('idle')
  const [activeId, setActiveId] = useState('01')
  const [submitState, setSubmitState] = useState<SubmitState>('idle')

  function handleSubmit() {
    if (submitState !== 'idle') return
    setSubmitState('saving')
    window.setTimeout(() => {
      setSubmitState('sent')
      window.setTimeout(() => {
        navigate('/ho-so-hop-dong', { state: { tab: 'activity' } })
      }, 900)
    }, 700)
  }

  function handleSaveComment() {
    setCommentSave('saved')
    setShowComment(false)
    window.setTimeout(() => setCommentSave('idle'), 1600)
  }

  const pdfSection = (
    <section
      className={`flex flex-col bg-surface-container-lowest rounded-xl shadow-sm overflow-hidden ${
        fullscreen ? 'fixed inset-0 z-[60] rounded-none' : 'lg:col-span-7'
      }`}
    >
      <div className="h-12 bg-surface-container-low px-space-md flex items-center justify-between border-b border-surface-container-high">
        <div className="flex items-center gap-space-sm min-w-0">
          <span className="font-code-sm text-code-sm text-on-surface font-semibold truncate">
            Tài liệu Gốc: HD_DienToanDamMay_v3.0.pdf
          </span>
          <span className="px-1.5 py-0.5 rounded bg-surface-container text-secondary font-label-sm text-label-sm shrink-0">
            Trang 04 / 28
          </span>
        </div>
        <div className="flex items-center gap-space-xs">
          <button
            className="w-8 h-8 rounded hover:bg-surface-container flex items-center justify-center text-on-surface-variant transition-colors"
            title="Thu nhỏ"
            type="button"
            onClick={() => setZoom((current) => Math.max(80, current - 5))}
          >
            <MaterialIcon name="zoom_out" className="text-[18px]" />
          </button>
          <span className="font-code-sm text-code-sm text-secondary px-1">
            {zoom}%
          </span>
          <button
            className="w-8 h-8 rounded hover:bg-surface-container flex items-center justify-center text-on-surface-variant transition-colors"
            title="Phóng to"
            type="button"
            onClick={() => setZoom((current) => Math.min(160, current + 5))}
          >
            <MaterialIcon name="zoom_in" className="text-[18px]" />
          </button>
          <div className="h-4 w-px bg-outline-variant mx-1" />
          <button
            className="w-8 h-8 rounded hover:bg-surface-container flex items-center justify-center text-on-surface-variant transition-colors"
            title="Xoay trang"
            type="button"
            onClick={() => setRotation((current) => (current + 90) % 360)}
          >
            <MaterialIcon name="rotate_right" className="text-[18px]" />
          </button>
          <button
            className="w-8 h-8 rounded hover:bg-surface-container flex items-center justify-center text-on-surface-variant transition-colors"
            title={fullscreen ? 'Thu nhỏ' : 'Mở toàn màn hình'}
            type="button"
            onClick={() => setFullscreen((current) => !current)}
          >
            <MaterialIcon
              name={fullscreen ? 'fullscreen_exit' : 'fullscreen'}
              className="text-[18px]"
            />
          </button>
        </div>
      </div>
      <div className="p-space-xl bg-surface-dim/30 overflow-y-auto max-h-[860px] flex justify-center flex-1">
        <div
          className="w-full max-w-[680px] bg-surface-container-lowest p-space-xl shadow-md flex flex-col relative text-[#1E293B] origin-top transition-transform duration-150"
          style={{ transform: `rotate(${rotation}deg) scale(${zoom / 100})` }}
        >
          <div className="flex justify-between items-start pb-space-lg mb-space-md border-b border-surface-container-high">
            <div className="flex flex-col">
              <span className="font-title-sm text-title-sm text-primary font-bold tracking-tight uppercase">
                CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
              </span>
              <span className="font-label-sm text-label-sm text-center text-secondary">
                Độc lập - Tự do - Hạnh phúc
              </span>
            </div>
            <div className="text-right">
              <span className="font-code-sm text-code-sm text-secondary block">
                Số: 89/2024/HĐ-DVCNTT
              </span>
              <span className="font-label-sm text-[11px] text-outline-variant">
                Lưu chiểu Pháp chế Số 1
              </span>
            </div>
          </div>
          <div className="space-y-space-md font-body-sm text-body-sm leading-relaxed text-justify">
            <h4 className="font-title-sm text-title-sm text-primary font-bold uppercase tracking-wide">
              ĐIỀU 5: PHÍ DỊCH VỤ, HẠN MỨC NGÂN SÁCH & CHI PHÍ PHÁT SINH
            </h4>
            <p className="text-on-surface">
              <span className="font-semibold">Khoản 5.1 (Phí Cố Định):</span>{' '}
              Phí duy trì nền tảng hạ tầng máy chủ ảo và bản quyền bảo mật định
              kỳ hàng quý được hai Bên thống nhất là 185.000.000 VND (Một trăm
              tám mươi lăm triệu đồng chẵn, đã bao gồm thuế Giá trị gia tăng
              GTGT 10%). Thanh toán vào ngày 05 của tháng đầu mỗi quý.
            </p>
            <div className="relative p-space-md bg-[#EFF6FF] rounded-sm transition-all">
              <div className="flex items-center justify-between mb-1.5 pb-1 border-b border-[#BFDBFE] gap-space-sm flex-wrap">
                <div className="flex items-center gap-1.5 text-primary-container">
                  <MaterialIcon
                    name="edit_note"
                    className="text-[16px] text-on-tertiary-container"
                  />
                  <span className="font-code-sm text-code-sm font-semibold">
                    Khoản 5.2 [Đang đối soát • Đã qua hiệu đính]
                  </span>
                </div>
                <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-primary-container text-on-primary font-label-sm text-[11px]">
                  <span>Sửa bởi LS. Trần Nam</span>
                  <span className="opacity-75">14:28 - 24/10</span>
                </div>
              </div>
              <p className="font-body-sm text-body-sm text-[#0F172A]">
                <span className="font-semibold text-primary">
                  Khoản 5.2 (Hạn mức phát sinh nâng cấp giai đoạn 1):
                </span>{' '}
                Trong trường hợp Bên A phát sinh nhu cầu mở rộng quy mô nút tính
                toán (Worker Nodes) vượt quá cấu hình tối thiểu quy định tại Phụ
                lục Kỹ thuật số 02, mức trần chi phí phát sinh nâng cấp hạ tầng
                giai đoạn 1 được tạm ứng không vượt quá{' '}
                <span className="bg-[#FEF08A] text-[#854D0E] font-semibold px-1 rounded mx-0.5">
                  550.000.000 VND
                </span>{' '}
                (Năm trăm năm mươi triệu đồng) theo biểu giá điều chỉnh thỏa
                thuận đính kèm. Mọi chi phí vượt hạn ngạch phải có văn bản phê
                duyệt bổ sung từ Hội đồng Công nghệ thông tin trước khi thực
                thi.
              </p>
              <div className="mt-2 pt-2 border-t border-[#DBEAFE] flex items-center justify-between text-secondary font-label-sm text-label-sm gap-space-sm flex-wrap">
                <span className="flex items-center gap-1">
                  <MaterialIcon name="pin_drop" className="text-[14px]" />
                  Tham chiếu Điều phối: Trích đoạn Điểm 3.b Phụ Lục Tài Chính số
                  04
                </span>
                <span className="font-code-sm text-[#1D4ED8] bg-[#DBEAFE] px-1.5 py-0.5 rounded font-medium">
                  Bản v3.2 Active
                </span>
              </div>
            </div>
            <p className="text-on-surface">
              <span className="font-semibold">
                Khoản 5.3 (Phương thức Thanh toán chậm & Phạt vi phạm):
              </span>{' '}
              Trường hợp Bên A chậm trễ thanh toán quá 15 (mười lăm) ngày làm
              việc kể từ thời điểm nhận Biên bản nghiệm thu và Hóa đơn hợp lệ từ
              Bên B, Bên B có quyền áp dụng mức lãi phạt suất tương đương
              0.05%/ngày trên tổng số tiền chậm trả, nhưng tổng số tiền phạt
              không vượt quá 8% tổng giá trị phần nghĩa vụ hợp đồng bị vi phạm
              theo Luật Thương mại hiện hành.
            </p>
            <p className="text-on-surface">
              <span className="font-semibold">
                Khoản 5.4 (Đối chiếu ngân sách dự phòng):
              </span>{' '}
              Hàng tháng, cán bộ đại diện pháp lý và kỹ thuật của hai Bên sẽ lập
              Biên bản đối soát tài nguyên thực tế đã tiêu thụ để quyết toán vào
              chu kỳ kế tiếp.
            </p>
            <div className="h-24 bg-surface-container-high/30 rounded p-space-md flex flex-col justify-center items-center text-secondary border border-dashed border-outline-variant">
              <MaterialIcon name="description" className="text-[24px]" />
              <span className="font-label-sm text-label-sm mt-1">
                Nội dung Điều 6 (Quyền Sở Hữu Trí Tuệ) tiếp tục ở trang sau...
              </span>
            </div>
          </div>
          <div className="mt-space-xl pt-space-md border-t border-surface-container flex justify-between items-center text-secondary font-label-sm text-label-sm">
            <span>Bảo mật cấp độ II - Phân phối nội bộ Tập đoàn</span>
            <span>Trang 4 / 28 - Bản lưu trữ số hóa</span>
          </div>
        </div>
      </div>
    </section>
  )

  return (
    <div className="flex flex-col w-full gap-space-md">
      <div className="w-full bg-surface-container-lowest rounded-xl p-space-md shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-space-md">
        <div className="flex items-center gap-space-md flex-wrap">
          <Link
            className="w-9 h-9 rounded bg-surface-container hover:bg-surface-container-high text-on-surface flex items-center justify-center"
            to="/nhan-xet-chinh-sua"
          >
            <MaterialIcon name="arrow_back" className="text-[18px]" />
          </Link>
          <div className="w-9 h-9 rounded bg-primary-container text-on-primary flex items-center justify-center font-title-sm text-title-sm">
            <MaterialIcon name="difference" className="text-[20px]" />
          </div>
          <div className="flex flex-col">
            <div className="flex items-center gap-space-sm flex-wrap">
              <span className="font-title-sm text-title-sm text-on-surface">
                HĐ-CNTT-2024/089-VINAPACK
              </span>
              <span className="px-space-xs py-0.5 rounded bg-surface-container-high text-on-surface-variant font-code-sm text-code-sm">
                v3.2
              </span>
              <span className="px-2 py-0.5 rounded bg-[#ECFDF5] text-[#065F46] font-label-sm text-label-sm font-semibold flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-[9999px] bg-[#059669]" />
                Đối soát Đa người dùng
              </span>
            </div>
            <span className="font-body-sm text-body-sm text-secondary">
              Hợp đồng Cung cấp Dịch vụ Điện toán Đám mây & An ninh Mạng Doanh
              nghiệp
            </span>
          </div>
        </div>
        <div className="flex items-center gap-space-md flex-wrap">
          <div className="flex items-center gap-space-sm bg-surface-container-low px-space-md py-1.5 rounded">
            <div className="w-7 h-7 rounded-[9999px] bg-tertiary-container text-on-tertiary flex items-center justify-center font-label-sm text-label-sm font-bold ring-2 ring-surface-container-lowest">
              HL
            </div>
            <div className="flex flex-col">
              <div className="flex items-center gap-1">
                <span className="font-label-sm text-label-sm text-on-surface font-semibold">
                  LS. Hoàng Linh
                </span>
                <span className="px-1 py-0.5 bg-secondary-container text-on-secondary-container font-label-sm text-[10px] rounded">
                  Bạn
                </span>
              </div>
              <span className="font-label-sm text-[11px] text-secondary">
                Phó Giám đốc Pháp chế (Đang thẩm định)
              </span>
            </div>
          </div>
          <div className="flex items-center gap-space-xs">
            <button
              className="px-space-md py-1.5 rounded bg-surface-container-high hover:bg-surface-dim text-on-surface font-label-md text-label-md transition-colors flex items-center gap-1"
              type="button"
            >
              <MaterialIcon name="file_download" className="text-[16px]" />
              Xuất Hồ sơ
            </button>
            <button
              className="px-space-md py-1.5 rounded bg-primary-container text-on-primary hover:bg-[#1E293B] font-label-md text-label-md transition-colors flex items-center gap-1 disabled:opacity-80"
              disabled={submitState !== 'idle'}
              type="button"
              onClick={handleSubmit}
            >
              {submitState === 'idle' ? (
                <>
                  <MaterialIcon
                    name="send_time_extension"
                    className="text-[16px]"
                  />
                  Trình Duyệt Hội Đồng
                </>
              ) : null}
              {submitState === 'saving' ? (
                <>
                  <MaterialIcon
                    name="refresh"
                    className="text-[16px] animate-spin"
                  />
                  Đang trình...
                </>
              ) : null}
              {submitState === 'sent' ? (
                <>
                  <MaterialIcon name="check" className="text-[16px]" />
                  Đã trình Hội đồng
                </>
              ) : null}
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-space-md w-full items-start">
        {pdfSection}

        <section className="lg:col-span-5 flex flex-col gap-space-md">
          <div className="bg-surface-container-lowest p-space-md rounded-xl shadow-sm border-l-4 border-primary-container flex flex-col gap-space-sm">
            <div className="flex items-start justify-between gap-space-sm">
              <div className="flex items-center gap-space-sm">
                <div className="relative">
                  <div className="w-9 h-9 rounded-[9999px] bg-primary-container text-on-primary flex items-center justify-center font-title-sm text-title-sm font-bold">
                    TN
                  </div>
                  <span className="absolute -bottom-0.5 -right-0.5 w-3 h-3 bg-[#10B981] rounded-[9999px] ring-2 ring-surface-container-lowest" />
                </div>
                <div className="flex flex-col">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="font-title-sm text-title-sm text-on-surface font-semibold">
                      Luật sư Trần Nam
                    </span>
                    <span className="px-1.5 py-0.5 bg-[#FEF3C7] text-[#92400E] font-label-sm text-label-sm rounded font-medium">
                      Đã có bản chỉnh sửa
                    </span>
                  </div>
                  <span className="font-label-sm text-label-sm text-secondary">
                    Chuyên viên Pháp chế Cấp cao • 14:28 - 24/10/2024
                  </span>
                </div>
              </div>
              <span className="font-code-sm text-code-sm px-2 py-0.5 rounded bg-surface-container-low text-primary-container font-semibold shrink-0">
                Diff #CR-104
              </span>
            </div>
            <p className="font-body-sm text-body-sm text-on-surface-variant bg-surface-container-low p-space-sm rounded">
              <span className="font-semibold text-on-surface">
                Ghi chú sửa đổi từ LS. Nam:
              </span>{' '}
              “Điều chỉnh nâng hạn mức trần từ 500 triệu lên 550 triệu theo Phụ
              lục tài chính sửa đổi ngày 22/10 do đối tác bổ sung thêm 2 module
              tường lửa chuyên dụng.”
            </p>
          </div>

          <div className="bg-surface-container-lowest p-space-md rounded-xl shadow-md border border-primary-container/40 flex flex-col gap-space-md relative">
            <div className="flex items-start justify-between gap-space-sm">
              <div className="flex items-center gap-space-sm">
                <span className="w-6 h-6 rounded bg-primary-container text-on-primary flex items-center justify-center font-code-sm text-code-sm font-bold">
                  01
                </span>
                <div>
                  <h3 className="font-title-sm text-title-sm text-on-surface font-bold">
                    Khoản 5.2 - Hạn mức chi phí phát sinh
                  </h3>
                  <span className="font-label-sm text-label-sm text-secondary">
                    Trang 04 • Đoạn văn thứ 2 • Mục Chi phí dự toán
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <MaterialIcon
                  name="verified"
                  className="text-[16px] text-[#059669]"
                />
                <span className="font-label-sm text-label-sm text-[#059669] font-semibold">
                  Độ tin cậy: 98.4%
                </span>
              </div>
            </div>

            <div className="flex items-center justify-between bg-surface-container-low p-1 rounded gap-space-sm flex-wrap">
              <div className="flex items-center gap-1 flex-wrap">
                <button
                  className={tabClass(diffTab === 'split')}
                  type="button"
                  onClick={() => setDiffTab('split')}
                >
                  <MaterialIcon name="compare_arrows" className="text-[14px]" />
                  So sánh Trước / Sau
                </button>
                <button
                  className={tabClass(diffTab === 'current')}
                  type="button"
                  onClick={() => setDiffTab('current')}
                >
                  Bản hiện tại (v3.2)
                </button>
                <button
                  className={tabClass(diffTab === 'previous')}
                  type="button"
                  onClick={() => setDiffTab('previous')}
                >
                  Bản ban đầu AI (v3.1)
                </button>
              </div>
              <span className="font-code-sm text-code-sm text-secondary pr-2">
                2 dòng thay đổi
              </span>
            </div>

            <div
              className={`grid gap-space-sm bg-surface-container-low p-space-sm rounded ${
                diffTab === 'split'
                  ? 'grid-cols-1 md:grid-cols-2'
                  : 'grid-cols-1'
              }`}
            >
              {diffTab === 'split' || diffTab === 'previous' ? (
                <PreviousVersion />
              ) : null}
              {diffTab === 'split' || diffTab === 'current' ? (
                <CurrentVersion />
              ) : null}
            </div>

            <div className="flex flex-col gap-space-xs pt-space-xs">
              <span className="font-label-sm text-label-sm text-secondary uppercase tracking-wider font-semibold">
                Quyết định thẩm định của bạn (Người dùng 2):
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-space-xs">
                <button
                  className={
                    decision === 'approve'
                      ? 'flex items-center justify-center gap-1.5 px-space-sm py-2 rounded bg-primary-container text-on-primary hover:bg-[#1E293B] transition-all font-label-md text-label-md'
                      : 'flex items-center justify-center gap-1.5 px-space-sm py-2 rounded bg-surface-container hover:bg-surface-container-high text-on-surface transition-all font-label-md text-label-md'
                  }
                  type="button"
                  onClick={() => setDecision('approve')}
                >
                  <MaterialIcon
                    name="check_circle"
                    className="text-[16px] text-[#34D399]"
                  />
                  Chấp thuận sửa đổi
                </button>
                <button
                  className={decisionClass(decision === 'revert')}
                  type="button"
                  onClick={() => {
                    setDecision('revert')
                    setDiffTab('previous')
                  }}
                >
                  <MaterialIcon
                    name="history"
                    className="text-[16px] text-error"
                  />
                  Khôi phục gốc AI
                </button>
                <button
                  className={
                    showComment
                      ? 'flex items-center justify-center gap-1.5 px-space-sm py-2 rounded bg-primary-container text-on-primary hover:bg-[#1E293B] transition-all font-label-md text-label-md'
                      : 'flex items-center justify-center gap-1.5 px-space-sm py-2 rounded bg-surface-container hover:bg-surface-container-high text-on-surface transition-all font-label-md text-label-md'
                  }
                  type="button"
                  onClick={() => setShowComment((current) => !current)}
                >
                  <MaterialIcon name="add_comment" className="text-[16px]" />
                  Thêm phản biện
                </button>
              </div>
              {showComment ? (
                <div className="mt-space-sm p-space-sm bg-surface-container-low rounded flex flex-col gap-space-xs">
                  <label className="font-label-sm text-label-sm text-on-surface font-medium uppercase tracking-wide">
                    Nhận định / Ý kiến phản hồi của LS. Hoàng Linh:
                  </label>
                  <textarea
                    className="w-full p-2 bg-surface-container-lowest text-on-surface font-body-sm text-body-sm rounded border border-outline-variant focus:outline-none focus:border-primary-container"
                    placeholder="Nhập ghi chú pháp lý hoặc yêu cầu đối tác xác thực lại chứng từ..."
                    rows={2}
                    value={comment}
                    onChange={(event) => setComment(event.target.value)}
                  />
                  <div className="flex justify-end gap-space-xs mt-1">
                    <button
                      className="px-space-sm py-1 text-secondary font-label-sm text-label-sm hover:text-on-surface"
                      type="button"
                      onClick={() => setShowComment(false)}
                    >
                      Hủy bỏ
                    </button>
                    <button
                      className="px-space-md py-1 bg-primary-container text-on-primary font-label-sm text-label-sm rounded font-medium"
                      type="button"
                      onClick={handleSaveComment}
                    >
                      Lưu nhận định
                    </button>
                  </div>
                </div>
              ) : null}
              {commentSave === 'saved' ? (
                <p className="font-label-sm text-label-sm text-[#065F46]">
                  Đã lưu nhận định phản biện.
                </p>
              ) : null}
            </div>

            <div className="flex items-center justify-between pt-space-xs text-secondary font-label-sm text-[11px] gap-space-sm flex-wrap">
              <span className="flex items-center gap-1">
                <MaterialIcon name="lock" className="text-[13px]" />
                Khóa đối soát tự động khi cả 2 người phê duyệt
              </span>
              <span className="font-code-sm">
                Mã băm kiểm chứng: SHA-256:7f4c..9b12
              </span>
            </div>
          </div>

          {editCitations
            .filter((item) => item.id !== '01')
            .map((item) => (
              <button
                key={item.id}
                className={`bg-surface-container-lowest p-space-md rounded-xl shadow-xs flex flex-col gap-space-xs hover:shadow transition-shadow text-left opacity-90 ${
                  activeId === item.id ? 'ring-1 ring-primary-container' : ''
                }`}
                type="button"
                onClick={() => setActiveId(item.id)}
              >
                <div className="flex items-center justify-between gap-space-sm">
                  <div className="flex items-center gap-space-sm min-w-0">
                    <span className="w-6 h-6 rounded bg-surface-container-high text-secondary flex items-center justify-center font-code-sm text-code-sm font-bold shrink-0">
                      {item.id}
                    </span>
                    <div>
                      <h4 className="font-title-sm text-title-sm text-on-surface font-semibold">
                        {item.title}
                      </h4>
                      <span className="font-label-sm text-label-sm text-secondary">
                        {item.meta}
                      </span>
                    </div>
                  </div>
                  {item.status === 'locked' ? (
                    <span className="px-2 py-0.5 rounded bg-[#ECFDF5] text-[#065F46] font-label-sm text-label-sm font-medium flex items-center gap-1 shrink-0">
                      <MaterialIcon name="done_all" className="text-[13px]" />
                      {item.statusLabel}
                    </span>
                  ) : null}
                  {item.status === 'waiting' ? (
                    <span className="px-2 py-0.5 rounded bg-[#FEF3C7] text-[#92400E] font-label-sm text-label-sm font-medium flex items-center gap-1 shrink-0">
                      <MaterialIcon name="schedule" className="text-[13px]" />
                      {item.statusLabel}
                    </span>
                  ) : null}
                  {item.status === 'pending' ? (
                    <span className="px-2 py-0.5 rounded bg-surface-container-high text-secondary font-label-sm text-label-sm font-medium shrink-0">
                      {item.statusLabel}
                    </span>
                  ) : null}
                </div>
                {item.excerpt ? (
                  <p className="font-body-sm text-body-sm text-secondary line-clamp-2 pl-8">
                    {item.excerpt}
                  </p>
                ) : null}
              </button>
            ))}
        </section>
      </div>
    </div>
  )
}
