import { Link } from 'react-router-dom'
import { useState } from 'react'
import { MaterialIcon } from './icons'
import {
  searchAnswerText,
  searchCitations,
  type SearchCitation,
} from '../data/dossierSearch'

function CitationMark({
  citation,
  active,
  onSelect,
}: {
  citation: SearchCitation
  active: boolean
  onSelect: (id: number) => void
}) {
  return (
    <button
      className={`inline-flex items-center justify-center w-5 h-5 ml-1 text-xs rounded-[9999px] cursor-pointer align-baseline transition-all ${
        active
          ? 'font-bold text-on-tertiary-fixed-variant bg-surface-container-high ring-2 ring-primary shadow-xs'
          : 'font-semibold text-secondary hover:text-primary bg-surface-container-low hover:bg-surface-container'
      }`}
      title={citation.title}
      type="button"
      onClick={() => onSelect(citation.id)}
    >
      <span className="text-[11px]">{citation.id}</span>
    </button>
  )
}

function MatchRow({
  citation,
  active,
  onSelect,
}: {
  citation: SearchCitation
  active: boolean
  onSelect: (id: number) => void
}) {
  return (
    <div className="p-space-md flex flex-col sm:flex-row sm:items-center justify-between gap-space-md hover:bg-surface-container-low transition-colors">
      <button
        className="flex items-start gap-space-md flex-1 min-w-0 text-left"
        type="button"
        onClick={() => onSelect(citation.id)}
      >
        <span
          className={`w-6 h-6 rounded-[9999px] font-semibold text-[12px] flex items-center justify-center flex-shrink-0 mt-0.5 ${
            active
              ? 'bg-primary text-on-primary font-bold'
              : 'bg-surface-container-high text-on-surface'
          }`}
        >
          {citation.id}
        </span>
        <div className="flex flex-col gap-1 min-w-0">
          <p className="font-body-md text-[14px] text-primary font-medium leading-relaxed">
            {citation.quote}
          </p>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-label-sm text-[11px] font-semibold text-secondary uppercase tracking-wide">
              Căn cứ:
            </span>
            <span className="font-code-sm text-[12px] font-semibold text-on-surface bg-surface-container px-2 py-0.5 rounded border border-outline-variant/30">
              {citation.source}
            </span>
          </div>
        </div>
      </button>
      <div className="flex items-center gap-space-md flex-shrink-0 self-end sm:self-center">
        <span className="inline-flex items-center gap-1 bg-[#ECFDF5] text-[#065F46] px-2 py-0.5 rounded font-label-sm text-[11px] font-semibold">
          <MaterialIcon name="verified" className="text-[13px]" />
          {citation.confidence}
        </span>
        <Link
          className="inline-flex items-center gap-1 text-primary hover:text-on-surface-variant font-label-sm text-label-sm font-semibold hover:underline"
          to="/doi-soat-trich-dan"
        >
          <span>Đối soát trích dẫn</span>
          <MaterialIcon name="arrow_forward" className="text-[16px]" />
        </Link>
      </div>
    </div>
  )
}

export function DossierSearchResults() {
  const [activeId, setActiveId] = useState(1)

  async function copyAnswer() {
    await navigator.clipboard.writeText(searchAnswerText)
  }

  return (
    <div className="w-full flex flex-col gap-space-md">
      <div className="w-full bg-surface-container-lowest rounded-xl shadow-sm border border-outline-variant/30 p-space-lg flex flex-col gap-space-md">
        <div className="flex items-center justify-between pb-space-xs border-b border-outline-variant/20">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-surface-container flex items-center justify-center text-primary">
              <MaterialIcon name="neurology" className="text-[18px]" />
            </div>
            <div>
              <h2 className="font-title-sm text-title-sm font-semibold text-primary">
                Câu trả lời tổng hợp AI
              </h2>
              <p className="font-label-sm text-label-sm text-secondary">
                Tổng hợp và đối chiếu tự động từ 4 điều khoản & phụ lục liên
                quan
              </p>
            </div>
          </div>
          <div className="flex items-center gap-space-xs">
            <button
              className="flex items-center gap-1 px-space-sm py-1 rounded hover:bg-surface-container-low text-secondary text-label-sm font-medium transition-colors"
              title="Sao chép toàn bộ"
              type="button"
              onClick={() => {
                void copyAnswer()
              }}
            >
              <MaterialIcon name="content_copy" className="text-[16px]" />
              Sao chép
            </button>
            <button
              className="flex items-center gap-1 px-space-sm py-1 rounded hover:bg-surface-container-low text-secondary text-label-sm font-medium transition-colors"
              title="Xuất báo cáo PDF"
              type="button"
            >
              <MaterialIcon name="ios_share" className="text-[16px]" />
              Chia sẻ
            </button>
          </div>
        </div>

        <div className="font-body-md text-on-surface leading-relaxed space-y-3">
          <p>
            Theo quy định tại hồ sơ hợp đồng dịch vụ viễn thông & CNTT, mức trần
            bồi thường thiệt hại được giới hạn không vượt quá 100% tổng giá trị
            dịch vụ thực tế mà bên sử dụng đã thanh toán trong 06 tháng liền kề
            trước thời điểm xảy ra sự cố
            <CitationMark
              citation={searchCitations[0]}
              active={activeId === 1}
              onSelect={setActiveId}
            />
            . Đồng thời, các trường hợp đứt cáp quang biển hoặc sự kiện bất khả
            kháng diện rộng sẽ được tạm hoãn áp dụng chế tài tính phạt vi phạm
            SLA trong khoảng thời gian tối đa 72 giờ kể từ khi gửi thông báo
            bằng văn bản hoặc email hợp lệ
            <CitationMark
              citation={searchCitations[1]}
              active={activeId === 2}
              onSelect={setActiveId}
            />
            .
          </p>
          <p>
            Bên B được miễn trừ hoàn toàn trách nhiệm đối với các tổn thất gián
            tiếp, thiệt hại hệ quả hoặc mất doanh thu cơ hội kinh doanh ngoài
            phạm vi nghĩa vụ trực tiếp đã thỏa thuận
            <CitationMark
              citation={searchCitations[2]}
              active={activeId === 3}
              onSelect={setActiveId}
            />
            . Tỷ lệ khấu trừ cụ thể và tiêu chuẩn thời gian khắc phục sự cố
            (MTTR) được quy định chi tiết tại Phụ lục cam kết chất lượng dịch vụ
            SLA
            <CitationMark
              citation={searchCitations[3]}
              active={activeId === 4}
              onSelect={setActiveId}
            />
            .
          </p>
        </div>
      </div>

      <div className="w-full flex flex-col gap-space-sm">
        <div className="flex items-center justify-between px-1">
          <div className="flex items-center gap-2">
            <MaterialIcon
              name="fact_check"
              className="text-[18px] text-secondary"
            />
            <h3 className="font-title-sm text-[14px] font-semibold text-primary uppercase tracking-wider">
              DANH SÁCH CÂU TRẢ LỜI KHỚP
            </h3>
            <span
              className="bg-surface-container-high text-secondary px-2 py-0.5 font-code-sm text-[11px] font-semibold"
              style={{ borderRadius: '9999px' }}
            >
              4 câu trả lời khớp
            </span>
          </div>
          <span className="font-code-sm text-[12px] text-secondary">
            Nhấp vào từng câu trả lời để đối soát ngữ cảnh trong tài liệu
          </span>
        </div>

        <div className="bg-surface-container-lowest rounded-xl border border-outline-variant/30 shadow-sm divide-y divide-outline-variant/20 overflow-hidden">
          {searchCitations.map((citation) => (
            <MatchRow
              key={citation.id}
              citation={citation}
              active={activeId === citation.id}
              onSelect={setActiveId}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
