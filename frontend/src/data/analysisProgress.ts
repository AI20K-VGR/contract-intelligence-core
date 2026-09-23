export type PipelinePhaseStatus = 'done' | 'active' | 'waiting'

export type PipelinePhase = {
  id: number
  title: string
  status: PipelinePhaseStatus
  detail: string
  extra?: string
}

export type ProgressFile = {
  id: string
  name: string
  meta: string
  status: 'done' | 'reading' | 'waiting'
  label: string
}

export type ProgressLog = {
  id: string
  time: string
  text: string
  status: 'done' | 'active' | 'info' | 'success' | 'finish'
}

export const pipelinePhases: PipelinePhase[] = [
  { id: 1, title: '1. Tải tệp', status: 'done', detail: 'Hoàn tất' },
  {
    id: 2,
    title: '2. Nhận diện chữ',
    status: 'active',
    detail: '86%',
    extra: '224/258',
  },
  {
    id: 3,
    title: '3. Phân tích điều khoản',
    status: 'waiting',
    detail: 'Chờ xử lý',
  },
  { id: 4, title: '4. Hoàn tất', status: 'waiting', detail: 'Chờ xử lý' },
]

export const progressFiles: ProgressFile[] = [
  {
    id: 'tap-1',
    name: 'Hợp đồng Tổng thầu EPC',
    meta: '• 64 MB',
    status: 'done',
    label: 'Hoàn thành',
  },
  {
    id: 'tap-2',
    name: 'Phụ lục kỹ thuật & Phạm vi',
    meta: '• 84 trang',
    status: 'reading',
    label: 'Đang đọc 88%',
  },
  {
    id: 'tap-3',
    name: 'Biểu phí SLA & Bảo lãnh',
    meta: '• 32 MB',
    status: 'waiting',
    label: 'Chờ xử lý',
  },
]

export const initialProgressLogs: ProgressLog[] = [
  {
    id: 'log-1',
    time: '14:28',
    text: 'Tiếp nhận hợp lệ 3 tệp hồ sơ',
    status: 'done',
  },
  {
    id: 'log-2',
    time: '14:28',
    text: 'Đã hoàn thành đọc Tập 1',
    status: 'done',
  },
  {
    id: 'log-3',
    time: '14:28',
    text: 'Đang xử lý Tập 2: Phụ lục kỹ thuật',
    status: 'active',
  },
]

export const upcomingProgressLogs: ProgressLog[] = [
  {
    id: 'log-4',
    time: '14:28',
    text: 'Phần 2: Hoàn tất OCR trang 84/84. Đã lập ma trận thực thể điều khoản.',
    status: 'info',
  },
  {
    id: 'log-5',
    time: '14:28',
    text: 'Chuyển đổi luồng: Bắt đầu nạp Phần 3 (Bieu_phi_SLA_Bao_lanh_Tap3.pdf).',
    status: 'info',
  },
  {
    id: 'log-6',
    time: '14:28',
    text: 'Hoàn tất trích xuất biểu phí phạt chậm tiến độ 3 giai đoạn bàn giao.',
    status: 'info',
  },
  {
    id: 'log-7',
    time: '14:28',
    text: 'Khởi tạo cây tri thức Vector Embeddings (1536 chiều). Đồng bộ 100%.',
    status: 'success',
  },
  {
    id: 'log-8',
    time: '14:28',
    text: 'Pipeline hoàn thành 100%. Sẵn sàng phân tích sâu và tra cứu pháp lý!',
    status: 'finish',
  },
]
