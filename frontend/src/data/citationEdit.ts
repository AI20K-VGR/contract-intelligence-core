export type EditCitationStatus = 'active' | 'locked' | 'waiting' | 'pending'

export type EditCitation = {
  id: string
  title: string
  meta: string
  excerpt?: string
  status: EditCitationStatus
  statusLabel: string
}

export const editCitations: EditCitation[] = [
  {
    id: '01',
    title: 'Khoản 5.2 - Hạn mức chi phí phát sinh',
    meta: 'Trang 04 • Đoạn văn thứ 2 • Mục Chi phí dự toán',
    status: 'active',
    statusLabel: 'Độ tin cậy: 98.4%',
  },
  {
    id: '02',
    title: 'Khoản 5.1 - Chu kỳ thanh toán phí cố định',
    meta: 'Trang 04 • 185.000.000 VND / quý',
    excerpt:
      'Phí duy trì nền tảng hạ tầng máy chủ ảo và bản quyền bảo mật định kỳ hàng quý được hai Bên thống nhất là 185.000.000 VND...',
    status: 'locked',
    statusLabel: 'Đã chốt • Khớp AI',
  },
  {
    id: '03',
    title: 'Khoản 5.3 - Lãi phạt chậm thanh toán',
    meta: 'Trang 04 • Hạn mức trần 8% theo Luật Thương mại',
    excerpt:
      'Mức phạt suất tương đương 0.05%/ngày trên tổng số tiền chậm trả, tổng số tiền phạt không vượt quá 8% tổng giá trị vi phạm...',
    status: 'waiting',
    statusLabel: 'Chờ LS. Trần Nam xem xét',
  },
  {
    id: '04',
    title: 'Khoản 8.4 - Nghĩa vụ Bảo mật & Bồi thường Rò rỉ Dữ liệu',
    meta: 'Trang 09 • Tiêu chuẩn ISO/IEC 27001',
    status: 'pending',
    statusLabel: 'Chưa thẩm định',
  },
]
