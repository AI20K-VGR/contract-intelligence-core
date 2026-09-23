import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { dossiersLabel, dossiersPath } from '../auth/session'
import { useAuth } from '../auth/useAuth'
import { MaterialIcon } from '../components/icons'
import { dossierCategories, uploadParts, type UploadPart } from '../data/upload'
import { usePageTitle } from '../hooks/usePageTitle'

type PrivacyTier = 'private' | 'shared'
type UploadStatus = 'idle' | 'uploading'

function UploadPartCard({ part }: { part: UploadPart }) {
  return (
    <div className="p-space-lg rounded-xl bg-surface-container-lowest border-t border-surface-container hover:bg-surface-container-low transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-space-md shadow-sm">
      <div className="flex items-start gap-space-md min-w-0">
        <div className="w-10 h-10 rounded-lg bg-red-50 text-red-700 flex items-center justify-center shrink-0">
          <MaterialIcon name="picture_as_pdf" className="text-[22px]" />
        </div>
        <div className="flex flex-col min-w-0">
          <div className="flex items-center gap-space-sm flex-wrap">
            <span
              className={`font-label-sm text-label-sm px-space-sm py-0.5 rounded font-semibold uppercase tracking-wider ${part.badgeClass}`}
            >
              {part.badge}
            </span>
            <span
              className="font-body-md text-body-md font-semibold text-primary truncate max-w-sm"
              title={part.fileName}
            >
              {part.fileName}
            </span>
          </div>
          <div className="flex items-center gap-space-md font-code-sm text-code-sm text-on-surface-variant mt-1">
            <span className="text-primary font-medium">{part.size}</span>
            <span>•</span>
            <span>{part.pages} trang</span>
            <span>•</span>
            <span className="text-emerald-700 font-semibold flex items-center gap-1">
              <MaterialIcon name="check_circle" className="text-[14px]" /> Đã
              sẵn sàng
            </span>
          </div>
        </div>
      </div>
      <div className="flex items-center gap-space-sm shrink-0 self-end sm:self-center">
        <button
          className="w-8 h-8 rounded bg-surface hover:bg-surface-container flex items-center justify-center text-on-surface-variant hover:text-primary transition-colors"
          title="Xem trước tài liệu"
          type="button"
        >
          <MaterialIcon name="visibility" className="text-[18px]" />
        </button>
        <button
          className="w-8 h-8 rounded bg-surface hover:bg-error-container hover:text-error flex items-center justify-center text-on-surface-variant transition-colors"
          title="Thay thế tệp"
          type="button"
        >
          <MaterialIcon name="sync" className="text-[18px]" />
        </button>
      </div>
    </div>
  )
}

export function CreateDossierPage() {
  usePageTitle('Tải lên tài liệu')
  const { user } = useAuth()
  const navigate = useNavigate()
  const backTo = user ? dossiersPath(user.role) : '/'
  const backLabel = user ? dossiersLabel(user.role) : 'Hồ sơ'

  const [name, setName] = useState(
    'Hợp đồng Tổng thầu EPC - Dự án Điện gió Nam Định 2024',
  )
  const [code, setCode] = useState('LX-2024-EPC-092')
  const [category, setCategory] = useState(dossierCategories[0])
  const [privacy, setPrivacy] = useState<PrivacyTier>('private')
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>('idle')

  function handleCancel() {
    navigate(backTo)
  }

  function handleUpload() {
    if (uploadStatus !== 'idle') return
    setUploadStatus('uploading')
    window.setTimeout(() => {
      navigate('/tien-trinh-phan-tich', { state: { name } })
    }, 1200)
  }

  return (
    <div className="flex flex-col w-full pb-margin-lg">
      <div className="flex flex-col gap-space-sm pt-space-md mb-space-xl">
        <nav className="flex items-center gap-space-xs font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">
          <Link className="hover:text-primary transition-colors" to={backTo}>
            {backLabel}
          </Link>
          <MaterialIcon name="chevron_right" className="text-[14px]" />
          <span className="text-on-surface font-semibold">
            Tạo hồ sơ mới & Phân tích tự động
          </span>
        </nav>
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-space-md">
          <div className="flex flex-col gap-space-xs max-w-3xl">
            <h1 className="font-headline-lg text-headline-lg text-primary tracking-tight">
              Tải lên tài liệu & Thiết lập xử lý AI
            </h1>
            <p className="font-body-md text-body-md text-on-surface-variant">
              Tải lên các tài liệu thuộc bộ hợp đồng để hệ thống phân tích và
              đối chiếu tự động.
            </p>
          </div>
          <div className="flex items-center gap-space-sm self-start md:self-auto shrink-0 bg-surface-container-low px-space-md py-space-xs rounded-lg shadow-sm">
            <span className="w-2 h-2 rounded-full bg-emerald-600 animate-pulse" />
            <span className="font-code-sm text-code-sm text-on-surface font-semibold">
              Lexis Legal-Core v4.2
            </span>
            <span className="text-outline-variant">•</span>
            <span className="font-label-sm text-label-sm text-on-surface-variant">
              SOC 2 Type II
            </span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-gutter-lg items-start">
        <div className="lg:col-span-4 flex flex-col gap-gutter">
          <section className="bg-surface-container-lowest p-space-xl rounded-xl shadow-sm flex flex-col gap-space-lg">
            <div className="flex items-center justify-between pb-space-xs">
              <div className="flex items-center gap-space-sm">
                <MaterialIcon
                  name="assignment"
                  className="text-primary text-[20px]"
                />
                <h2 className="font-title-sm text-title-sm text-primary uppercase tracking-wider">
                  Thông tin hồ sơ
                </h2>
              </div>
              <span className="font-label-sm text-label-sm bg-surface-container px-space-sm py-0.5 rounded text-on-secondary-container font-semibold">
                Bắt buộc
              </span>
            </div>

            <div className="flex flex-col gap-space-md">
              <div className="flex flex-col gap-space-xs">
                <label
                  className="font-label-sm text-label-sm text-primary tracking-wider uppercase font-semibold"
                  htmlFor="dossier-name"
                >
                  Tên bộ hồ sơ hợp đồng
                </label>
                <input
                  className="h-10 px-space-md bg-surface text-on-surface font-body-sm text-body-sm rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-on-tertiary-container focus:bg-surface-container-lowest transition-all"
                  id="dossier-name"
                  type="text"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                />
              </div>

              <div className="grid grid-cols-1 gap-space-md">
                <div className="flex flex-col gap-space-xs">
                  <label
                    className="font-label-sm text-label-sm text-primary tracking-wider uppercase font-semibold"
                    htmlFor="dossier-code"
                  >
                    Mã vụ việc / Dự án liên kết
                  </label>
                  <div className="relative flex items-center">
                    <MaterialIcon
                      name="tag"
                      className="absolute left-space-md text-on-surface-variant text-[18px]"
                    />
                    <input
                      className="w-full h-10 pl-10 pr-space-md bg-surface font-code-sm text-code-sm text-on-surface rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-on-tertiary-container transition-all"
                      id="dossier-code"
                      type="text"
                      value={code}
                      onChange={(event) => setCode(event.target.value)}
                    />
                  </div>
                </div>

                <div className="flex flex-col gap-space-xs">
                  <label
                    className="font-label-sm text-label-sm text-primary tracking-wider uppercase font-semibold"
                    htmlFor="dossier-category"
                  >
                    Phân loại lĩnh vực pháp lý
                  </label>
                  <div className="relative flex items-center">
                    <select
                      className="w-full h-10 px-space-md appearance-none bg-surface text-on-surface font-body-sm text-body-sm rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-on-tertiary-container cursor-pointer"
                      id="dossier-category"
                      value={category}
                      onChange={(event) => setCategory(event.target.value)}
                    >
                      {dossierCategories.map((item) => (
                        <option key={item} value={item}>
                          {item}
                        </option>
                      ))}
                    </select>
                    <MaterialIcon
                      name="expand_more"
                      className="absolute right-space-md pointer-events-none text-on-surface-variant text-[18px]"
                    />
                  </div>
                </div>
              </div>

              <div className="flex flex-col gap-space-xs pt-space-xs">
                <span className="font-label-sm text-label-sm text-primary tracking-wider uppercase font-semibold">
                  Quyền riêng tư mặc định
                </span>
                <div className="flex flex-col gap-space-xs">
                  <label className="flex items-center justify-between p-space-md rounded-lg bg-surface hover:bg-surface-container-low transition-colors cursor-pointer group">
                    <div className="flex items-center gap-space-md">
                      <input
                        checked={privacy === 'private'}
                        className="w-4 h-4 accent-primary-container"
                        name="privacy-tier"
                        type="radio"
                        onChange={() => setPrivacy('private')}
                      />
                      <div className="flex flex-col">
                        <span className="font-body-sm text-body-sm font-semibold text-primary">
                          Riêng tư (Chỉ mình tôi)
                        </span>
                        <span className="font-code-sm text-code-sm text-on-surface-variant">
                          Không truy cập chéo giữa các tổ chức vụ việc
                        </span>
                      </div>
                    </div>
                    <MaterialIcon
                      name="lock"
                      className="text-primary text-[18px]"
                    />
                  </label>
                  <label className="flex items-center justify-between p-space-md rounded-lg bg-surface hover:bg-surface-container-low transition-colors cursor-pointer group">
                    <div className="flex items-center gap-space-md">
                      <input
                        checked={privacy === 'shared'}
                        className="w-4 h-4 accent-primary-container"
                        name="privacy-tier"
                        type="radio"
                        onChange={() => setPrivacy('shared')}
                      />
                      <div className="flex flex-col">
                        <span className="font-body-sm text-body-sm font-semibold text-primary">
                          Chia sẻ với Trưởng ban Pháp chế
                        </span>
                        <span className="font-code-sm text-code-sm text-on-surface-variant">
                          Tự động báo cáo rủi ro cấp điều hành
                        </span>
                      </div>
                    </div>
                    <MaterialIcon
                      name="groups"
                      className="text-on-surface-variant text-[18px]"
                    />
                  </label>
                </div>
              </div>
            </div>
          </section>
        </div>

        <div className="lg:col-span-8 flex flex-col gap-gutter">
          <div className="p-space-xl bg-surface-container-lowest rounded-xl shadow-sm flex flex-col gap-space-lg">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-space-sm pb-space-xs border-t border-surface-container pt-0">
              <div className="flex flex-col gap-space-xs">
                <div className="flex items-center gap-space-sm">
                  <MaterialIcon
                    name="splitscreen"
                    className="text-primary text-[20px]"
                  />
                  <h2 className="font-title-sm text-title-sm text-primary uppercase tracking-wider">
                    Tải lên theo phần (Multipart Upload 3 Slot)
                  </h2>
                  <span className="font-label-sm text-label-sm bg-emerald-50 text-emerald-700 px-space-sm py-0.5 rounded font-semibold">
                    Đã nạp đủ 3/3
                  </span>
                </div>
                <p className="font-body-sm text-body-sm text-on-surface-variant">
                  Bộ hồ sơ lớn được chia thành tối đa 3 phần (≤50MB/phần, tổng
                  150MB) để nạp song song và gộp xử lý OCR/AI đồng bộ.
                </p>
              </div>
              <div className="flex flex-col sm:items-end text-on-surface-variant font-code-sm text-code-sm shrink-0">
                <span className="text-body-md font-semibold text-primary">
                  139.5 / 150 MB
                </span>
                <span className="text-label-sm text-emerald-700 font-medium flex items-center gap-1">
                  <MaterialIcon name="speed" className="text-[14px]" /> Tối ưu
                  OCR song song
                </span>
              </div>
            </div>

            <div className="w-full bg-surface-container rounded-full h-2 overflow-hidden">
              <div
                className="bg-primary h-2 rounded-full transition-all duration-300"
                style={{ width: '93%' }}
              />
            </div>

            <div className="grid grid-cols-1 gap-space-md">
              {uploadParts.map((part) => (
                <UploadPartCard key={part.id} part={part} />
              ))}
            </div>

            <div className="px-space-md py-space-sm bg-surface-container-low rounded-lg flex items-center justify-between gap-space-sm text-on-surface-variant">
              <div className="flex items-center gap-space-xs font-label-sm text-label-sm">
                <MaterialIcon
                  name="verified"
                  className="text-[16px] text-primary"
                />
                <span>
                  Đã hoàn tất nạp 3 phần tài liệu. Công cụ phân tích sẽ liên kết
                  chỉ mục các phần thành một cây hồ sơ duy nhất.
                </span>
              </div>
              <span className="font-code-sm text-code-sm font-semibold text-primary shrink-0">
                3 / 3 Slot
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="sticky bottom-4 mt-space-xl p-space-lg bg-surface-container-lowest rounded-xl shadow-xl z-30 flex flex-col md:flex-row items-center justify-between gap-space-md">
        <div className="flex items-center justify-end gap-space-md w-full">
          <button
            className="h-10 px-space-lg font-body-sm text-body-sm font-medium text-on-surface-variant hover:text-primary transition-colors cursor-pointer rounded-lg hover:bg-surface-container-low"
            type="button"
            onClick={handleCancel}
          >
            Hủy bỏ
          </button>
          <button
            className="h-10 px-space-lg bg-surface hover:bg-surface-container-low transition-colors font-body-sm text-body-sm font-semibold rounded-lg shadow-sm text-on-surface cursor-pointer"
            type="button"
          >
            Lưu nháp
          </button>
          <button
            className="h-10 px-space-lg bg-primary text-on-primary hover:bg-primary-container active:bg-tertiary transition-all font-body-sm text-body-sm font-semibold rounded-lg shadow-sm flex items-center gap-space-sm cursor-pointer disabled:opacity-80"
            disabled={uploadStatus !== 'idle'}
            type="button"
            onClick={handleUpload}
          >
            {uploadStatus === 'idle' ? (
              <>
                <MaterialIcon name="cloud_upload" className="text-[18px]" />
                <span>Upload</span>
              </>
            ) : null}
            {uploadStatus === 'uploading' ? (
              <span>Đang khởi tạo Pipeline AI...</span>
            ) : null}
          </button>
        </div>
      </div>
    </div>
  )
}
