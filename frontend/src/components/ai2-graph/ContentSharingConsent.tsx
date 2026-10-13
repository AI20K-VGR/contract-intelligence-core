import { useState } from 'react'
import { updateDossierAi2Consent } from '../../api/dossiers'

export type ContentSharingConsentProps = {
  dossierId: string
  enabled: boolean
  onSaved: (enabled: boolean) => void
}

export function ContentSharingConsent({
  dossierId,
  enabled,
  onSaved,
}: ContentSharingConsentProps) {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function changeConsent(next: boolean) {
    if (pending || next === enabled) return
    if (next && !window.confirm('Cho phép AI2 gửi nội dung hồ sơ này tới nhà cung cấp AI ở lần xử lý tiếp theo?')) return
    setPending(true)
    setError(null)
    try {
      const response = await updateDossierAi2Consent(dossierId, next)
      onSaved(response.enabled)
    } catch {
      setError('Không lưu được quyền chia sẻ nội dung. Trạng thái trước đó vẫn được giữ.')
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="ai2-content-consent" aria-busy={pending}>
      <label>
        <input
          type="checkbox"
          checked={enabled}
          disabled={pending}
          onChange={(event) => void changeConsent(event.currentTarget.checked)}
        />{' '}
        Cho phép AI2 xử lý nội dung hồ sơ
      </label>
      <p>Thay đổi có hiệu lực từ yêu cầu AI2 tiếp theo.</p>
      {pending && <span role="status">Đang lưu quyền chia sẻ…</span>}
      {error && <p role="alert">{error}</p>}
    </div>
  )
}
