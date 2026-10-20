import { useState } from 'react'
import { updateDossierAi2Consent } from '../../api/dossiers'
import { MaterialIcon } from '../icons'

export type ContentSharingConsentProps = {
  dossierId: string
  enabled: boolean
  /**
   * Chỉ chủ hồ sơ hoặc Quản trị (DOSSIER_MANAGE) đổi được; người khác chỉ
   * thấy trạng thái, để không bấm rồi mới nhận 403.
   */
  canChange: boolean
  onSaved: (enabled: boolean) => void
}

export function ContentSharingConsent({
  dossierId,
  enabled,
  canChange,
  onSaved,
}: ContentSharingConsentProps) {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function changeConsent(next: boolean) {
    if (!canChange || pending || next === enabled) return
    if (
      next &&
      !window.confirm(
        'Cho phép gửi nội dung hồ sơ này tới dịch vụ AI ở lần phân tích tiếp theo?',
      )
    ) {
      return
    }
    setPending(true)
    setError(null)
    try {
      const response = await updateDossierAi2Consent(dossierId, next)
      onSaved(response.enabled)
    } catch {
      setError(
        'Không lưu được quyền chia sẻ nội dung. Trạng thái trước đó vẫn được giữ.',
      )
    } finally {
      setPending(false)
    }
  }

  // Lời giải thích để ở gợi ý khi rê chuột, không chiếm thêm một dòng.
  const hint = canChange
    ? 'Thay đổi có hiệu lực từ lần phân tích tiếp theo.'
    : 'Chỉ chủ hồ sơ hoặc Quản trị đổi được.'
  return (
    <div className="flex flex-col items-end gap-1" aria-busy={pending}>
      {canChange ? (
        <label
          className="inline-flex h-9 cursor-pointer items-center gap-space-xs rounded-full border border-outline-variant/30 bg-surface-container-lowest px-space-md font-body-sm text-body-sm font-semibold text-on-surface shadow-[0_1px_2px_rgba(15,23,42,0.06)] hover:bg-surface-container"
          title={hint}
        >
          <input
            type="checkbox"
            className="h-4 w-4 accent-primary"
            checked={enabled}
            disabled={pending}
            onChange={(event) =>
              void changeConsent(event.currentTarget.checked)
            }
          />
          Cho phép AI phân tích nội dung hồ sơ
          {pending ? (
            <MaterialIcon
              name="progress_activity"
              className="animate-spin text-[16px] text-primary"
            />
          ) : null}
        </label>
      ) : (
        <span
          className="inline-flex h-9 items-center gap-space-xs rounded-full bg-surface-container px-space-md font-body-sm text-body-sm text-on-surface-variant"
          title={hint}
        >
          <MaterialIcon
            name={enabled ? 'check_circle' : 'block'}
            className="text-[16px]"
          />
          AI phân tích nội dung hồ sơ: {enabled ? 'đang bật' : 'đang tắt'}
        </span>
      )}
      {pending ? (
        <span role="status" className="sr-only">
          Đang lưu quyền chia sẻ…
        </span>
      ) : null}
      {error ? (
        <p role="alert" className="font-label-sm text-label-sm text-error">
          {error}
        </p>
      ) : null}
    </div>
  )
}
