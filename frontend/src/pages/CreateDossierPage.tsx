import { useRef, useState, type DragEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  createDossier,
  createDossierErrorMessage,
  patchDossier,
} from '../api/dossiers'
import { dossiersLabel, dossiersPath } from '../auth/session'
import { useAuth } from '../auth/useAuth'
import { MaterialIcon } from '../components/icons'
import { structurePath } from '../data/dossiers'
import { dossierCategories } from '../data/upload'
import { useHeaderShowsPageTitle, usePageTitle } from '../hooks/usePageTitle'
import {
  STRUCTURE_MODE_KEY,
  structureModes,
  type StructureMode,
} from '../structure'

type PrivacyTier = 'private' | 'shared'
type UploadStatus = 'idle' | 'uploading'
type PickedFile = {
  key: string
  role: 'contract' | 'annex'
  file: File
}

function isPdf(file: File) {
  return (
    file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
  )
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function FileCard({
  item,
  disabled,
  onPreview,
  onReplace,
  onRemove,
}: {
  item: PickedFile
  disabled: boolean
  onPreview: () => void
  onReplace: () => void
  onRemove: () => void
}) {
  const contract = item.role === 'contract'
  return (
    <div className="p-space-lg rounded-xl bg-surface-container-lowest border-t border-surface-container hover:bg-surface-container-low transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-space-md shadow-sm">
      <div className="flex items-start gap-space-md min-w-0">
        <div className="w-10 h-10 rounded-lg bg-red-50 text-red-700 flex items-center justify-center shrink-0">
          <MaterialIcon name="picture_as_pdf" className="text-[22px]" />
        </div>
        <div className="flex flex-col min-w-0">
          <div className="flex items-center gap-space-sm flex-wrap">
            <span
              className={`font-label-sm text-label-sm px-space-sm py-0.5 rounded font-semibold uppercase tracking-wider ${
                contract
                  ? 'bg-primary-container text-primary-fixed'
                  : 'bg-secondary-container text-on-secondary-container'
              }`}
            >
              {contract ? 'Hợp đồng chính' : 'Phụ lục'}
            </span>
            <span
              className="font-body-md text-body-md font-semibold text-primary truncate max-w-sm"
              title={item.file.name}
            >
              {item.file.name}
            </span>
          </div>
          <div className="flex items-center gap-space-md font-code-sm text-code-sm text-on-surface-variant mt-1">
            <span className="text-primary font-medium">
              {formatSize(item.file.size)}
            </span>
            <span>•</span>
            <span className="text-emerald-700 font-semibold flex items-center gap-1">
              <MaterialIcon name="check_circle" className="text-[14px]" /> Đã
              chọn
            </span>
          </div>
        </div>
      </div>
      <div className="flex items-center gap-space-sm shrink-0 self-end sm:self-center">
        <button
          className="w-8 h-8 rounded bg-surface hover:bg-surface-container flex items-center justify-center text-on-surface-variant hover:text-primary transition-colors disabled:opacity-50"
          disabled={disabled}
          title="Xem trước tài liệu"
          type="button"
          onClick={onPreview}
        >
          <MaterialIcon name="visibility" className="text-[18px]" />
        </button>
        <button
          className="w-8 h-8 rounded bg-surface hover:bg-surface-container flex items-center justify-center text-on-surface-variant hover:text-primary transition-colors disabled:opacity-50"
          disabled={disabled}
          title="Thay thế tệp"
          type="button"
          onClick={onReplace}
        >
          <MaterialIcon name="sync" className="text-[18px]" />
        </button>
        <button
          className="w-8 h-8 rounded bg-surface hover:bg-error-container hover:text-error flex items-center justify-center text-on-surface-variant transition-colors disabled:opacity-50"
          disabled={disabled}
          title="Gỡ tệp"
          type="button"
          onClick={onRemove}
        >
          <MaterialIcon name="delete" className="text-[18px]" />
        </button>
      </div>
    </div>
  )
}

export function CreateDossierPage() {
  usePageTitle('Tải lên tài liệu')
  const titleInHeader = useHeaderShowsPageTitle()
  const { user } = useAuth()
  const navigate = useNavigate()
  const backTo = user ? dossiersPath(user.role) : '/'
  const backLabel = user ? dossiersLabel(user.role) : 'Hồ sơ'
  const canUpload =
    user?.backendRole === 'OPERATOR' || user?.backendRole === 'ADMINISTRATOR'

  const contractInputRef = useRef<HTMLInputElement>(null)
  const annexInputRef = useRef<HTMLInputElement>(null)
  const replaceKeyRef = useRef<string | null>(null)

  const [name, setName] = useState('')
  const [code, setCode] = useState('')
  const [category, setCategory] = useState(dossierCategories[0])
  const [privacy, setPrivacy] = useState<PrivacyTier>('private')
  const [structureMode, setStructureMode] = useState<StructureMode | null>(null)
  const [contract, setContract] = useState<PickedFile | null>(null)
  const [annexes, setAnnexes] = useState<PickedFile[]>([])
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)

  const files = contract ? [contract, ...annexes] : annexes
  const busy = uploadStatus === 'uploading'
  const totalBytes = files.reduce((sum, item) => sum + item.file.size, 0)

  function handleCancel() {
    navigate(backTo)
  }

  function takePdf(list: FileList | File[] | null): File | null {
    const file = list?.[0]
    if (!file) return null
    if (!isPdf(file)) {
      setError('Chỉ nhận tệp PDF.')
      return null
    }
    setError(null)
    return file
  }

  function addContract(file: File) {
    setContract({
      key: `contract-${file.name}-${file.size}-${file.lastModified}`,
      role: 'contract',
      file,
    })
  }

  function addAnnexes(list: FileList | File[]) {
    const next: PickedFile[] = []
    for (const file of Array.from(list)) {
      if (!isPdf(file)) {
        setError('Chỉ nhận tệp PDF.')
        return
      }
      next.push({
        key: `annex-${file.name}-${file.size}-${file.lastModified}-${crypto.randomUUID()}`,
        role: 'annex',
        file,
      })
    }
    setError(null)
    setAnnexes((current) => [...current, ...next])
  }

  function onContractChosen(list: FileList | null) {
    const replacing = replaceKeyRef.current
    replaceKeyRef.current = null
    const file = takePdf(list)
    if (!file) return
    if (replacing && contract?.key === replacing) {
      addContract(file)
      return
    }
    addContract(file)
  }

  function onAnnexChosen(list: FileList | null) {
    const replacing = replaceKeyRef.current
    replaceKeyRef.current = null
    if (replacing) {
      const file = takePdf(list)
      if (!file) return
      setAnnexes((current) =>
        current.map((item) =>
          item.key === replacing
            ? {
                ...item,
                file,
                key: `annex-${file.name}-${file.size}-${file.lastModified}`,
              }
            : item,
        ),
      )
      return
    }
    if (!list?.length) return
    addAnnexes(list)
  }

  function previewFile(file: File) {
    const url = URL.createObjectURL(file)
    window.open(url, '_blank', 'noopener,noreferrer')
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
  }

  function replaceFile(item: PickedFile) {
    replaceKeyRef.current = item.key
    if (item.role === 'contract') {
      contractInputRef.current?.click()
    } else {
      annexInputRef.current?.click()
    }
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setDragOver(false)
    if (busy) return
    const dropped = Array.from(event.dataTransfer.files)
    if (dropped.length === 0) return
    if (!contract) {
      const file = takePdf(dropped)
      if (file) addContract(file)
      if (dropped.length > 1) addAnnexes(dropped.slice(1))
      return
    }
    addAnnexes(dropped)
  }

  async function handleUpload() {
    if (busy) return
    const trimmedName = name.trim()
    if (!trimmedName) {
      setError('Nhập tên bộ hồ sơ.')
      return
    }
    if (trimmedName.length > 255) {
      setError('Tên bộ hồ sơ tối đa 255 ký tự.')
      return
    }
    if (!structureMode) {
      setError('Chọn loại cấu trúc tài liệu.')
      return
    }
    if (!contract) {
      setError('Chọn tệp PDF hợp đồng.')
      return
    }
    if (!canUpload) {
      setError('Chỉ vận hành và quản trị mới tải hồ sơ được.')
      return
    }

    setError(null)
    setUploadStatus('uploading')
    try {
      const created = await createDossier({
        contract: contract.file,
        metadata: { name: trimmedName },
        annexes: annexes.map((item) => item.file),
      })
      if (!created?.dossier_id) {
        setError('Backend không trả dossier_id.')
        setUploadStatus('idle')
        return
      }

      const extra: Record<string, unknown> = {
        privacy,
        category,
        [STRUCTURE_MODE_KEY]: structureMode,
      }
      if (code.trim()) extra.code = code.trim()
      try {
        await patchDossier(created.dossier_id, { metadata: extra })
      } catch {
        // POST đã tạo hồ sơ. PATCH chỉ ghi field UI thừa so với OpenAPI.
        // Loại cấu trúc vẫn được truyền qua state để trang cây dùng ngay.
      }

      navigate(structurePath(created.dossier_id), {
        state: { structureMode },
      })
    } catch (cause) {
      const message = createDossierErrorMessage(cause)
      if (message) setError(message)
      setUploadStatus('idle')
    }
  }

  return (
    <div className="flex flex-col w-full pb-margin-lg">
      <div className="flex flex-col gap-space-sm pt-space-md mb-space-xl">
        <nav className="flex items-center gap-space-xs font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">
          <Link className="hover:text-primary transition-colors" to={backTo}>
            {backLabel}
          </Link>
          <MaterialIcon name="chevron_right" className="text-[14px]" />
          <span className="text-on-surface font-semibold">Tạo hồ sơ mới</span>
        </nav>
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-space-md">
          <div className="flex flex-col gap-space-xs max-w-3xl">
            {titleInHeader ? null : (
              <h1 className="font-headline-lg text-headline-lg text-primary tracking-tight">
                Tải lên tài liệu
              </h1>
            )}
            <p className="font-body-md text-body-md text-on-surface-variant">
              Tải PDF hợp đồng. Hệ thống OCR và hiện cây cấu trúc khi xử lý
              xong.
            </p>
          </div>
        </div>
      </div>

      {!canUpload ? (
        <div className="mb-space-lg px-space-md py-space-sm rounded bg-surface-container text-on-surface font-body-sm text-body-sm">
          Tài khoản thẩm định không tải hồ sơ. Chỉ vận hành và quản trị gọi được
          API này.
        </div>
      ) : null}

      {error ? (
        <div
          className="mb-space-lg px-space-md py-space-sm rounded bg-error-container text-on-error-container font-body-sm text-body-sm"
          role="alert"
        >
          {error}
        </div>
      ) : null}

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
                  <span className="text-error" aria-hidden="true">
                    {' '}
                    *
                  </span>
                </label>
                <input
                  className="h-10 px-space-md bg-surface text-on-surface font-body-sm text-body-sm rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-on-tertiary-container focus:bg-surface-container-lowest transition-all"
                  aria-required="true"
                  disabled={busy}
                  id="dossier-name"
                  placeholder="Hợp đồng EPC — Dự án Điện gió"
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
                      disabled={busy}
                      id="dossier-code"
                      placeholder="LX-2024-EPC-092"
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
                      disabled={busy}
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

              <fieldset
                className="flex flex-col gap-space-xs pt-space-xs"
                disabled={busy}
              >
                <legend className="font-label-sm text-label-sm text-primary tracking-wider uppercase font-semibold mb-space-xs">
                  Loại cấu trúc tài liệu
                  <span className="text-error" aria-hidden="true">
                    {' '}
                    *
                  </span>
                </legend>
                <div className="flex flex-col gap-space-xs">
                  {structureModes.map((item) => {
                    const active = structureMode === item.value
                    return (
                      <label
                        key={item.value}
                        className={`flex items-center justify-between p-space-md rounded-lg transition-colors cursor-pointer ${
                          active
                            ? 'bg-primary-container/10 ring-1 ring-primary-container'
                            : 'bg-surface hover:bg-surface-container-low'
                        }`}
                      >
                        <div className="flex items-center gap-space-md">
                          <input
                            aria-required="true"
                            checked={active}
                            className="w-4 h-4 accent-primary-container"
                            name="structure-mode"
                            type="radio"
                            value={item.value}
                            onChange={() => setStructureMode(item.value)}
                          />
                          <div className="flex flex-col">
                            <span className="font-body-sm text-body-sm font-semibold text-primary">
                              {item.label}
                            </span>
                            <span className="font-code-sm text-code-sm text-on-surface-variant">
                              {item.hint}
                            </span>
                          </div>
                        </div>
                        <MaterialIcon
                          name={
                            item.value === 'numbered'
                              ? 'format_list_numbered'
                              : 'notes'
                          }
                          className={`text-[18px] ${
                            active ? 'text-primary' : 'text-on-surface-variant'
                          }`}
                        />
                      </label>
                    )
                  })}
                </div>
              </fieldset>

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
                        disabled={busy}
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
                        disabled={busy}
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
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-space-sm pb-space-xs">
              <div className="flex flex-col gap-space-xs">
                <div className="flex items-center gap-space-sm">
                  <MaterialIcon
                    name="upload_file"
                    className="text-primary text-[20px]"
                  />
                  <h2 className="font-title-sm text-title-sm text-primary uppercase tracking-wider">
                    Tệp PDF
                    <span className="text-error" aria-hidden="true">
                      {' '}
                      *
                    </span>
                  </h2>
                  <span className="font-label-sm text-label-sm bg-surface-container text-on-secondary-container px-space-sm py-0.5 rounded font-semibold">
                    {contract ? `${files.length} tệp` : 'Chưa chọn tệp'}
                  </span>
                </div>
                <p className="font-body-sm text-body-sm text-on-surface-variant">
                  Một tệp hợp đồng chính (bắt buộc) và phụ lục PDF tùy chọn.
                </p>
              </div>
              {files.length > 0 ? (
                <div className="flex flex-col sm:items-end text-on-surface-variant font-code-sm text-code-sm shrink-0">
                  <span className="text-body-md font-semibold text-primary">
                    {formatSize(totalBytes)}
                  </span>
                </div>
              ) : null}
            </div>

            <input
              ref={contractInputRef}
              accept="application/pdf,.pdf"
              aria-label="Chọn tệp hợp đồng"
              className="sr-only"
              disabled={busy}
              type="file"
              onChange={(event) => {
                onContractChosen(event.target.files)
                event.target.value = ''
              }}
            />
            <input
              ref={annexInputRef}
              accept="application/pdf,.pdf"
              aria-label="Chọn phụ lục"
              className="sr-only"
              disabled={busy}
              multiple
              type="file"
              onChange={(event) => {
                onAnnexChosen(event.target.files)
                event.target.value = ''
              }}
            />

            <div
              className={`rounded-lg px-space-lg py-12 flex flex-col items-center gap-space-sm text-center ${
                dragOver ? 'bg-surface-container' : 'bg-surface-container-low'
              }`}
              onDragLeave={() => setDragOver(false)}
              onDragOver={(event) => {
                event.preventDefault()
                if (!busy) setDragOver(true)
              }}
              onDrop={onDrop}
            >
              <MaterialIcon
                name="picture_as_pdf"
                className="text-secondary text-[28px]"
              />
              {!contract ? (
                <>
                  <p className="font-title-sm text-title-sm text-on-surface">
                    Chưa chọn tệp PDF
                    <span className="text-error" aria-hidden="true">
                      {' '}
                      *
                    </span>
                  </p>
                  <p className="font-body-sm text-body-sm text-on-surface-variant max-w-md">
                    Kéo thả hoặc chọn hợp đồng chính để tạo hồ sơ. Có thể thêm
                    phụ lục sau.
                  </p>
                  <button
                    className="mt-space-xs h-10 px-space-lg bg-primary text-on-primary hover:bg-primary-container font-body-sm text-body-sm font-semibold rounded-lg shadow-sm"
                    disabled={busy}
                    type="button"
                    onClick={() => contractInputRef.current?.click()}
                  >
                    Chọn tệp hợp đồng
                  </button>
                </>
              ) : (
                <>
                  <p className="font-body-sm text-body-sm text-on-surface-variant">
                    Thêm phụ lục PDF nếu hồ sơ có nhiều tệp.
                  </p>
                  <button
                    className="h-10 px-space-lg bg-surface-container-lowest text-on-surface hover:bg-surface-container font-body-sm text-body-sm font-semibold rounded-lg shadow-sm"
                    disabled={busy}
                    type="button"
                    onClick={() => {
                      replaceKeyRef.current = null
                      annexInputRef.current?.click()
                    }}
                  >
                    Thêm phụ lục
                  </button>
                </>
              )}
            </div>

            {files.length > 0 ? (
              <div className="grid grid-cols-1 gap-space-md">
                {files.map((item) => (
                  <FileCard
                    key={item.key}
                    disabled={busy}
                    item={item}
                    onPreview={() => previewFile(item.file)}
                    onReplace={() => replaceFile(item)}
                    onRemove={() => {
                      if (item.role === 'contract') setContract(null)
                      else
                        setAnnexes((current) =>
                          current.filter((row) => row.key !== item.key),
                        )
                    }}
                  />
                ))}
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <div className="sticky bottom-4 mt-space-xl p-space-lg bg-surface-container-lowest rounded-xl shadow-xl z-30 flex flex-col md:flex-row items-center justify-between gap-space-md">
        <div className="flex items-center justify-end gap-space-md w-full">
          <button
            className="h-10 px-space-lg font-body-sm text-body-sm font-medium text-on-surface-variant hover:text-primary transition-colors cursor-pointer rounded-lg hover:bg-surface-container-low"
            disabled={busy}
            type="button"
            onClick={handleCancel}
          >
            Hủy bỏ
          </button>
          <button
            className="h-10 px-space-lg bg-primary text-on-primary hover:bg-primary-container active:bg-tertiary transition-all font-body-sm text-body-sm font-semibold rounded-lg shadow-sm flex items-center gap-space-sm cursor-pointer disabled:opacity-80"
            disabled={busy || !canUpload}
            type="button"
            onClick={() => {
              void handleUpload()
            }}
          >
            {busy ? (
              <span>Đang tải lên…</span>
            ) : (
              <>
                <MaterialIcon name="cloud_upload" className="text-[18px]" />
                <span>Upload</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
