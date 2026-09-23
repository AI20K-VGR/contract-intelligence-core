export type UploadPart = {
  id: number
  badge: string
  badgeClass: string
  fileName: string
  size: string
  pages: number
}

export const uploadParts: UploadPart[] = [
  {
    id: 1,
    badge: 'Phần 1 • Tệp gốc',
    badgeClass: 'bg-primary-container text-primary-fixed',
    fileName: 'Hop_dong_Tong_thau_EPC_Tap1.pdf',
    size: '48.5 MB / 50 MB',
    pages: 112,
  },
  {
    id: 2,
    badge: 'Phần 2 • Phụ lục Kỹ thuật',
    badgeClass: 'bg-secondary-container text-on-secondary-container',
    fileName: 'Phu_luc_Ky_thuat_SOW_Tap2.pdf',
    size: '46.2 MB / 50 MB',
    pages: 84,
  },
  {
    id: 3,
    badge: 'Phần 3 • Biểu phí & SLA',
    badgeClass: 'bg-surface-container-highest text-on-surface',
    fileName: 'Bieu_phi_SLA_Bao_lanh_Tap3.pdf',
    size: '44.8 MB / 50 MB',
    pages: 62,
  },
]

export const dossierCategories = [
  'Hợp đồng Xây dựng & Kỹ thuật (EPC)',
  'Thuê hạ tầng số & Cam kết dịch vụ (SLA)',
  'Mua bán & Sáp nhập doanh nghiệp (M&A)',
  'Tài trợ dự án & Bảo lãnh tín dụng quốc tế',
  'Chuyển giao quyền sở hữu công nghệ & IP',
]
