import { useRef, useState, type ReactNode } from 'react'
import { MaterialIcon } from './icons'

type BranchChipProps = {
  color: string
  bg: string
  border: string
  text: string
  label: string
}

function BranchChip({ color, bg, border, text, label }: BranchChipProps) {
  return (
    <div
      className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 ${bg} border ${border} ${text} shadow-sm font-semibold text-[13px]`}
      style={{ borderRadius: '9999px' }}
    >
      <span
        className="w-2 h-2"
        style={{ borderRadius: '9999px', backgroundColor: color }}
      />
      {label}
    </div>
  )
}

function ClauseLink({
  id,
  selected,
  onSelect,
  border,
  hover,
  children,
  emphasize,
}: {
  id: string
  selected: string | null
  onSelect: (id: string) => void
  border: string
  hover: string
  children: ReactNode
  emphasize?: boolean
}) {
  return (
    <button
      className={`text-left text-xs pb-0.5 border-b-2 ${border} ${hover} cursor-pointer ${
        emphasize
          ? 'font-semibold text-slate-900'
          : 'font-medium text-slate-700'
      } ${selected === id ? 'ring-2 ring-[#0b1f3a] ring-offset-2' : ''}`}
      type="button"
      onClick={() => onSelect(id)}
    >
      {children}
    </button>
  )
}

function AnnexChip({
  tone,
  children,
}: {
  tone: 'sky' | 'emerald' | 'rose'
  children: ReactNode
}) {
  const tones = {
    sky: 'text-sky-800 bg-sky-100/80 border-sky-200',
    emerald: 'text-emerald-800 bg-emerald-100/80 border-emerald-200',
    rose: 'text-rose-800 bg-rose-100/80 border-rose-200',
  }
  return (
    <div
      className={`text-[11px] font-medium px-2 py-0.5 border flex items-center gap-1 ${tones[tone]}`}
      style={{ borderRadius: '0.25rem' }}
    >
      <MaterialIcon name="attachment" className="text-[13px]" />
      {children}
    </div>
  )
}

export function ContractMindmap() {
  const [zoom, setZoom] = useState(1)
  const [selected, setSelected] = useState<string | null>(null)
  const viewportRef = useRef<HTMLDivElement>(null)
  const shellRef = useRef<HTMLDivElement>(null)

  function updateZoom(next: number) {
    setZoom(Math.max(0.6, Math.min(1.4, next)))
  }

  function recenter() {
    updateZoom(1)
    viewportRef.current?.scrollTo({ left: 100, top: 40, behavior: 'smooth' })
  }

  function toggleFullscreen() {
    const node = shellRef.current
    if (!node) return
    if (document.fullscreenElement) {
      void document.exitFullscreen()
    } else {
      void node.requestFullscreen()
    }
  }

  return (
    <div
      ref={shellRef}
      className="bg-surface-container-lowest rounded-xl shadow-sm border border-outline-variant/20 overflow-hidden flex flex-col relative w-full"
      style={{ height: '720px' }}
    >
      <div className="px-6 py-3 bg-surface-container-low/60 border-b border-outline-variant/20 flex items-center justify-between z-10">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-primary font-title-sm text-title-sm">
            <MaterialIcon
              name="account_tree"
              className="text-[20px] text-primary"
            />
            <span className="font-semibold">
              Sơ Đồ Mindmap Cấu Trúc Hợp Đồng & Phụ Lục
            </span>
          </div>
          <span
            className="font-label-sm text-[11px] text-secondary bg-surface-container px-2.5 py-0.5 font-mono"
            style={{ borderRadius: '9999px' }}
          >
            Dạng cây nhánh cong • 9 Điều khoản • 4 Phụ lục
          </span>
        </div>
        <span
          className="flex items-center gap-1.5 text-xs text-secondary bg-surface-container px-2.5 py-1"
          style={{ borderRadius: '9999px' }}
        >
          <span
            className="w-2 h-2 bg-[#059669]"
            style={{ borderRadius: '9999px' }}
          />
          Sơ đồ trực quan tương tác
        </span>
      </div>

      <div
        ref={viewportRef}
        className="relative w-full flex-1 overflow-auto bg-[#fafbff] flex items-center p-8"
      >
        <div
          className="relative min-w-[1080px] w-full h-[620px] mx-auto transition-transform duration-200 origin-center select-none"
          style={{ transform: `scale(${zoom})` }}
        >
          <svg
            className="absolute inset-0 w-full h-full pointer-events-none z-0 fill-none"
            fill="none"
            viewBox="0 0 1080 620"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M 195 310 C 270 310, 270 105, 340 105"
              stroke="#1e3a8a"
              strokeWidth="2.5"
              strokeLinecap="round"
            />
            <path
              d="M 515 105 C 560 105, 560 70, 610 70"
              stroke="#1e3a8a"
              strokeWidth="1.75"
              strokeLinecap="round"
            />
            <path
              d="M 515 105 C 560 105, 560 140, 610 140"
              stroke="#1e3a8a"
              strokeWidth="1.75"
              strokeLinecap="round"
            />
            <path
              d="M 195 310 C 270 310, 280 205, 340 205"
              stroke="#0284c7"
              strokeWidth="2.5"
              strokeLinecap="round"
            />
            <path
              d="M 545 205 C 585 205, 585 180, 625 180"
              stroke="#0284c7"
              strokeWidth="1.75"
              strokeLinecap="round"
            />
            <path
              d="M 545 205 C 585 205, 585 230, 625 230"
              stroke="#0284c7"
              strokeWidth="1.75"
              strokeLinecap="round"
            />
            <path
              d="M 825 180 C 855 180, 855 180, 880 180"
              stroke="#0284c7"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeDasharray="3 3"
            />
            <path
              d="M 825 230 C 855 230, 855 230, 880 230"
              stroke="#0284c7"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeDasharray="3 3"
            />
            <path
              d="M 195 310 C 270 310, 275 310, 340 310"
              stroke="#059669"
              strokeWidth="2.5"
              strokeLinecap="round"
            />
            <path
              d="M 545 310 C 585 310, 585 285, 625 285"
              stroke="#059669"
              strokeWidth="1.75"
              strokeLinecap="round"
            />
            <path
              d="M 545 310 C 585 310, 585 335, 625 335"
              stroke="#059669"
              strokeWidth="1.75"
              strokeLinecap="round"
            />
            <path
              d="M 845 285 C 875 285, 875 285, 900 285"
              stroke="#059669"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeDasharray="3 3"
            />
            <path
              d="M 195 310 C 270 310, 280 415, 340 415"
              stroke="#d97706"
              strokeWidth="2.5"
              strokeLinecap="round"
            />
            <path
              d="M 545 415 C 585 415, 585 390, 625 390"
              stroke="#d97706"
              strokeWidth="1.75"
              strokeLinecap="round"
            />
            <path
              d="M 545 415 C 585 415, 585 440, 625 440"
              stroke="#d97706"
              strokeWidth="1.75"
              strokeLinecap="round"
            />
            <path
              d="M 195 310 C 270 310, 270 515, 340 515"
              stroke="#e11d48"
              strokeWidth="2.5"
              strokeLinecap="round"
            />
            <path
              d="M 545 515 C 585 515, 585 490, 625 490"
              stroke="#e11d48"
              strokeWidth="1.75"
              strokeLinecap="round"
            />
            <path
              d="M 545 515 C 585 515, 585 540, 625 540"
              stroke="#e11d48"
              strokeWidth="1.75"
              strokeLinecap="round"
            />
            <path
              d="M 830 490 C 860 490, 860 490, 885 490"
              stroke="#e11d48"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeDasharray="3 3"
            />
          </svg>

          <button
            className="absolute left-[20px] top-[282px] z-20 cursor-pointer group"
            type="button"
            onClick={() => setSelected('root')}
          >
            <div
              className={`bg-[#0b1f3a] text-white px-5 py-3 shadow-lg flex items-center gap-2.5 border-2 border-slate-700/30 hover:scale-105 transition-transform ${
                selected === 'root' ? 'ring-2 ring-[#0b1f3a] ring-offset-2' : ''
              }`}
              style={{ borderRadius: '9999px' }}
            >
              <MaterialIcon
                name="folder_special"
                className="text-[20px] text-amber-300"
              />
              <div className="flex flex-col text-left">
                <span className="font-bold text-[14px] leading-tight tracking-wide">
                  HĐ Tổng thầu EPC
                </span>
                <span className="text-[10px] text-slate-300 font-mono">
                  Dự án Đầm Mây • v3.2
                </span>
              </div>
            </div>
          </button>

          <div className="absolute left-[340px] top-[90px] z-10">
            <BranchChip
              color="#1e3a8a"
              bg="bg-blue-50"
              border="border-blue-200"
              text="text-blue-950"
              label="Điều khoản chung & Hiệu lực"
            />
          </div>
          <div className="absolute left-[610px] top-[58px] z-10">
            <ClauseLink
              id="d1"
              selected={selected}
              onSelect={setSelected}
              border="border-blue-800"
              hover="hover:text-blue-900"
            >
              Điều 1: Định nghĩa & Giải thích thuật ngữ
            </ClauseLink>
          </div>
          <div className="absolute left-[610px] top-[128px] z-10">
            <ClauseLink
              id="d8"
              selected={selected}
              onSelect={setSelected}
              border="border-blue-800"
              hover="hover:text-blue-900"
            >
              Điều 8: Bất khả kháng & Chấm dứt HĐ
            </ClauseLink>
          </div>

          <div className="absolute left-[340px] top-[190px] z-10">
            <BranchChip
              color="#0284c7"
              bg="bg-sky-50"
              border="border-sky-200"
              text="text-sky-950"
              label="Phạm vi & Dịch vụ kỹ thuật"
            />
          </div>
          <div className="absolute left-[625px] top-[168px] z-10 flex items-center gap-2">
            <ClauseLink
              id="d2"
              selected={selected}
              onSelect={setSelected}
              border="border-sky-600"
              hover="hover:text-sky-800"
            >
              Điều 2: Phạm vi công việc & Hạ tầng
            </ClauseLink>
          </div>
          <div className="absolute left-[880px] top-[168px] z-10">
            <AnnexChip tone="sky">Phụ lục A (Data Center Tier III)</AnnexChip>
          </div>
          <div className="absolute left-[625px] top-[218px] z-10 flex items-center gap-2">
            <ClauseLink
              id="d3"
              selected={selected}
              onSelect={setSelected}
              border="border-sky-600"
              hover="hover:text-sky-800"
            >
              Điều 3: Tiêu chuẩn dịch vụ (SLA 99.99%)
            </ClauseLink>
          </div>
          <div className="absolute left-[880px] top-[218px] z-10">
            <AnnexChip tone="sky">Phụ lục B (Cam kết SLA)</AnnexChip>
          </div>

          <div className="absolute left-[340px] top-[295px] z-10">
            <BranchChip
              color="#059669"
              bg="bg-emerald-50"
              border="border-emerald-200"
              text="text-emerald-950"
              label="Tài chính, Giá trị & Thuế"
            />
          </div>
          <div className="absolute left-[625px] top-[273px] z-10 flex items-center gap-2">
            <ClauseLink
              id="d4"
              selected={selected}
              onSelect={setSelected}
              border="border-emerald-600"
              hover="hover:text-emerald-800"
            >
              Điều 4: Phí dịch vụ, Thuế & Thanh toán
            </ClauseLink>
          </div>
          <div className="absolute left-[900px] top-[273px] z-10">
            <AnnexChip tone="emerald">Phụ lục C (Biểu phí XLSX)</AnnexChip>
          </div>
          <div className="absolute left-[625px] top-[323px] z-10">
            <ClauseLink
              id="d5"
              selected={selected}
              onSelect={setSelected}
              border="border-emerald-600"
              hover="hover:text-emerald-800"
              emphasize
            >
              <span className="flex items-center gap-1.5">
                <MaterialIcon
                  name="star"
                  className="text-[14px] text-amber-500"
                />
                Điều 5: Giá trị HĐ & Dự phòng (28,45 tỷ)
              </span>
            </ClauseLink>
          </div>

          <div className="absolute left-[340px] top-[400px] z-10">
            <BranchChip
              color="#d97706"
              bg="bg-amber-50"
              border="border-amber-200"
              text="text-amber-950"
              label="Rủi ro & Bồi thường nghĩa vụ"
            />
          </div>
          <div className="absolute left-[625px] top-[378px] z-10">
            <ClauseLink
              id="d6"
              selected={selected}
              onSelect={setSelected}
              border="border-amber-500"
              hover="hover:text-amber-800"
            >
              Điều 6: Trách nhiệm bồi thường (Max 100%)
            </ClauseLink>
          </div>
          <div className="absolute left-[625px] top-[428px] z-10">
            <ClauseLink
              id="ins"
              selected={selected}
              onSelect={setSelected}
              border="border-amber-500"
              hover="hover:text-amber-800"
            >
              Giới hạn bảo hiểm rủi ro tài sản
            </ClauseLink>
          </div>

          <div className="absolute left-[340px] top-[500px] z-10">
            <BranchChip
              color="#e11d48"
              bg="bg-rose-50"
              border="border-rose-200"
              text="text-rose-950"
              label="Bảo mật & Tranh chấp pháp lý"
            />
          </div>
          <div className="absolute left-[625px] top-[478px] z-10 flex items-center gap-2">
            <ClauseLink
              id="d7"
              selected={selected}
              onSelect={setSelected}
              border="border-rose-600"
              hover="hover:text-rose-800"
            >
              Điều 7: Bảo mật thông tin & SHTT
            </ClauseLink>
          </div>
          <div className="absolute left-[885px] top-[478px] z-10">
            <AnnexChip tone="rose">Phụ lục D (Thỏa thuận NDA)</AnnexChip>
          </div>
          <div className="absolute left-[625px] top-[528px] z-10">
            <ClauseLink
              id="d9"
              selected={selected}
              onSelect={setSelected}
              border="border-rose-600"
              hover="hover:text-rose-800"
            >
              Điều 9: Luật áp dụng & VIAC
            </ClauseLink>
          </div>
        </div>
      </div>

      <div
        className="absolute bottom-5 left-1/2 -translate-x-1/2 z-30 flex items-center gap-2 bg-white/95 backdrop-blur shadow-lg border border-slate-200/80 px-3 py-1.5 text-slate-700"
        style={{ borderRadius: '9999px' }}
      >
        <div
          className="flex items-center gap-1 text-xs font-medium px-2 py-1 bg-slate-100 hover:bg-slate-200 cursor-pointer transition-colors mr-1"
          style={{ borderRadius: '9999px' }}
        >
          <span>Việt</span>
          <MaterialIcon name="keyboard_arrow_down" className="text-[14px]" />
        </div>
        <div className="h-4 w-px bg-slate-200" />
        <button
          className="w-7 h-7 flex items-center justify-center hover:bg-slate-100 transition-colors text-slate-600 active:scale-95"
          style={{ borderRadius: '9999px' }}
          title="Thu nhỏ"
          type="button"
          onClick={() => updateZoom(zoom - 0.1)}
        >
          <MaterialIcon name="remove" className="text-[18px]" />
        </button>
        <span className="text-xs font-medium font-mono px-1 min-w-[42px] text-center text-slate-800">
          {Math.round(zoom * 100)}%
        </span>
        <button
          className="w-7 h-7 flex items-center justify-center hover:bg-slate-100 transition-colors text-slate-600 active:scale-95"
          style={{ borderRadius: '9999px' }}
          title="Phóng to"
          type="button"
          onClick={() => updateZoom(zoom + 0.1)}
        >
          <MaterialIcon name="add" className="text-[18px]" />
        </button>
        <div className="h-4 w-px bg-slate-200" />
        <button
          className="flex items-center gap-1 text-xs font-medium px-2.5 py-1 hover:bg-slate-100 transition-colors text-slate-700"
          style={{ borderRadius: '9999px' }}
          type="button"
        >
          <MaterialIcon name="palette" className="text-[16px]" />
          <span>Kiểu dáng</span>
        </button>
        <button
          className="w-7 h-7 flex items-center justify-center hover:bg-slate-100 transition-colors text-slate-600"
          style={{ borderRadius: '9999px' }}
          title="Căn giữa sơ đồ"
          type="button"
          onClick={recenter}
        >
          <MaterialIcon name="center_focus_strong" className="text-[16px]" />
        </button>
        <button
          className="w-7 h-7 flex items-center justify-center hover:bg-slate-100 transition-colors text-slate-600"
          style={{ borderRadius: '9999px' }}
          title="Toàn màn hình"
          type="button"
          onClick={toggleFullscreen}
        >
          <MaterialIcon name="fullscreen" className="text-[16px]" />
        </button>
        <div className="h-4 w-px bg-slate-200" />
        <button
          className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1 bg-primary text-white hover:bg-primary-container shadow-sm transition-all"
          style={{ borderRadius: '9999px' }}
          type="button"
        >
          <MaterialIcon name="download" className="text-[15px]" />
          <span>Xuất MindMap</span>
        </button>
      </div>
    </div>
  )
}
