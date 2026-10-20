import { useEffect } from 'react'

/**
 * Nguyên văn lỗi kỹ thuật (mã lỗi, thông báo gốc của dịch vụ) không hiện trên giao diện.
 * Ghi vào Console của trình duyệt (F12 → Console, lọc "[Lỗi kỹ thuật]") để tra nguyên nhân.
 */
export function TechnicalDetail({ text }: { text: string | null | undefined }) {
  useEffect(() => {
    if (text) console.warn('[Lỗi kỹ thuật]', text)
  }, [text])
  return null
}
