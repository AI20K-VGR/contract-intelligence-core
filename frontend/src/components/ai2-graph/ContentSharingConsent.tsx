import { useState } from 'react'
import { updateDossierAi2Consent } from '../../api/dossiers'

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
        'Cho phép AI2 gửi nội dung hồ sơ này tới nhà cung cấp AI ở lần xử lý tiếp theo?',
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

  return (
    <div className="flex flex-col gap-1" aria-busy={pending}>
      {canChange ? (
        <label className="flex cursor-pointer items-center gap-space-xs font-body-sm text-body-sm text-on-surface">
          <input
            type="checkbox"
            className="h-4 w-4 accent-primary"
            checked={enabled}
            disabled={pending}
            onChange={(event) =>
              void changeConsent(event.currentTarget.checked)
            }
          />
          Cho phép AI2 xử lý nội dung hồ sơ
        </label>
      ) : (
        <span className="font-body-sm text-body-sm text-on-surface">
          AI2 xử lý nội dung hồ sơ: {enabled ? 'đang bật' : 'đang tắt'}
        </span>
      )}
      <p className="font-label-sm text-label-sm text-on-surface-variant">
        {canChange
          ? 'Thay đổi có hiệu lực từ yêu cầu AI2 tiếp theo.'
          : 'Chỉ chủ hồ sơ hoặc Quản trị đổi được.'}
      </p>
      {pending ? (
        <span
          role="status"
          className="font-label-sm text-label-sm text-on-surface-variant"
        >
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
