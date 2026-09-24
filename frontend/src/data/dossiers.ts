export type DossierStatus = 'processing' | 'ready' | 'review' | 'failed'
export type DossierAccess = 'mine' | 'shared_out' | 'shared_in'

export type Dossier = {
  id: string
  title: string
  code: string
  size: string
  icon: 'folder' | 'folder_open'
  status: DossierStatus
  progressLabel?: string
  progress?: number
  reviewNote?: string
  documents: number | null
  updated: string
  access: DossierAccess
  shares?: { id: string; email: string; display_name: string }[]
  jobStatus?: string | null
  uploadedAt?: string
}

export function structurePath(dossierId: string) {
  return `/cau-truc/${encodeURIComponent(dossierId)}`
}

export function progressPath(dossierId: string) {
  return `/tien-trinh-phan-tich/${encodeURIComponent(dossierId)}`
}

export function dossierOpenTo(dossier: Dossier) {
  const job = dossier.jobStatus
  if (
    dossier.status === 'processing' ||
    dossier.status === 'failed' ||
    job === 'uploaded' ||
    job === 'processing' ||
    job === 'failed'
  ) {
    return progressPath(dossier.id)
  }
  return structurePath(dossier.id)
}

export const myDossiers: Dossier[] = [
  {
    id: 'HS-2024-MA-0089',
    title: 'Hợp đồng M&A Dự án Bất động sản Thủ Thiêm',
    code: 'HS-2024-MA-0089',
    size: '48.2 MB',
    icon: 'folder_open',
    status: 'processing',
    progressLabel: 'Cấu trúc (68%)',
    progress: 68,
    documents: 12,
    updated: '2 phút trước',
    access: 'mine',
  },
  {
    id: 'HS-2024-MED-0034',
    title: 'Hợp đồng Mua bán Thiết bị Y tế Quốc tế 2024',
    code: 'HS-2024-MED-0034',
    size: '14.8 MB',
    icon: 'folder',
    status: 'ready',
    documents: 4,
    updated: 'Hôm nay, 09:45',
    access: 'shared_out',
  },
  {
    id: 'HS-2024-CLD-0112',
    title: 'Thỏa thuận Cung cấp Dịch vụ Điện toán Đám mây (SLA)',
    code: 'HS-2024-CLD-0112',
    size: '8.1 MB',
    icon: 'folder',
    status: 'review',
    reviewNote: '2 điều khoản bất thường',
    documents: 3,
    updated: 'Hôm qua',
    access: 'mine',
  },
  {
    id: 'HS-2024-BCC-0045',
    title: 'Hợp đồng Hợp tác Kinh doanh (BCC) - Chi nhánh Hải Phòng',
    code: 'HS-2024-BCC-0045',
    size: '22.4 MB',
    icon: 'folder',
    status: 'ready',
    documents: 6,
    updated: '14/05/2024',
    access: 'shared_out',
  },
  {
    id: 'HS-2024-BID-0201',
    title: 'Hồ sơ Thầu Xây dựng Nhà máy Dược phẩm Khu Công nghệ cao',
    code: 'HS-2024-BID-0201',
    size: '96.5 MB',
    icon: 'folder_open',
    status: 'processing',
    progressLabel: 'OCR (40%)',
    progress: 40,
    documents: 18,
    updated: 'Hôm nay, 11:20',
    access: 'mine',
  },
  {
    id: 'HS-2024-NDA-0331',
    title: 'Thỏa thuận Không tiết lộ Thông tin (NDA) - Đối tác Fintech',
    code: 'HS-2024-NDA-0331',
    size: '3.2 MB',
    icon: 'folder',
    status: 'ready',
    documents: 2,
    updated: '12/05/2024',
    access: 'mine',
  },
  {
    id: 'HS-2024-HR-0156',
    title: 'Hợp đồng Lao động Cao cấp - Ban Giám đốc',
    code: 'HS-2024-HR-0156',
    size: '5.4 MB',
    icon: 'folder',
    status: 'ready',
    documents: 2,
    updated: '10/05/2024',
    access: 'mine',
  },
  {
    id: 'HS-2024-DIS-0078',
    title: 'Phụ lục Hợp đồng Phân phối Độc quyền Miền Nam',
    code: 'HS-2024-DIS-0078',
    size: '7.6 MB',
    icon: 'folder',
    status: 'ready',
    documents: 3,
    updated: '08/05/2024',
    access: 'shared_out',
  },
]
