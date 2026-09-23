export type AuditType = 'verified' | 'edited' | 'flagged' | 'viewed'

export type AuditActor = {
  initials: string
  name: string
  role: string
  kind: 'human' | 'ai'
}

export type AuditEvent = {
  id: string
  time: string
  date: string
  type: AuditType
  actor: AuditActor
  location: string
  hash: string
  title: string
  detail?: string
  diff?: { label: string; from: string; to: string; note?: string }
  recommendation?: string
  extra?: string
  icon?: string
}

export const actorNam: AuditActor = {
  initials: 'TN',
  name: 'Luật sư Trần Nam',
  role: 'Chuyên viên Pháp chế Cấp cao',
  kind: 'human',
}

export const actorLinh: AuditActor = {
  initials: 'HL',
  name: 'Hoàng Linh',
  role: 'Phó Giám đốc Pháp chế (GC-Level)',
  kind: 'human',
}

export const actorLoan: AuditActor = {
  initials: 'TL',
  name: 'Thanh Loan',
  role: 'Kiểm toán viên Độc lập (PwC)',
  kind: 'human',
}

export const actorAi: AuditActor = {
  initials: 'AI',
  name: 'Lexis Compliance AI',
  role: 'Tự động quét quy chuẩn rủi ro',
  kind: 'ai',
}

export const auditEvents: AuditEvent[] = [
  {
    id: 'a84f9e21',
    time: '14:28:11',
    date: '24/10/2024',
    type: 'edited',
    actor: actorNam,
    location: 'Khoản 5.2, Trang 3',
    hash: '#a84f..9e21',
    title: 'Điều chỉnh hạn mức bồi thường vi phạm hợp đồng (Liability Cap)',
    diff: {
      label: 'Giá trị thẩm định:',
      from: '500.000.000 VND',
      to: '550.000.000 VND',
      note: '"Điều chỉnh theo phụ lục tài chính sửa đổi số 01 ký ngày 22/10."',
    },
  },
  {
    id: 'e31b44c9',
    time: '11:14:02',
    date: '24/10/2024',
    type: 'flagged',
    actor: { ...actorAi, role: 'Tự động quét quy chuẩn rủi ro' },
    location: 'Khoản 8.4, Trang 19',
    hash: '#e31b..44c9',
    title: 'Gắn cờ cảnh báo rủi ro pháp định',
    icon: 'warning',
    detail:
      'Mức phạt vi phạm quy định hợp đồng là 12% vượt quá mức trần tối đa 8% quy định tại Điều 301 Luật Thương mại 2005 đối với phần nghĩa vụ bị vi phạm.',
    recommendation: 'Khuyến nghị: Sửa giảm về ≤ 8%',
    extra: 'Xem tiền lệ tương đương',
  },
  {
    id: '992c11fa',
    time: '09:45:30',
    date: '24/10/2024',
    type: 'verified',
    actor: actorLinh,
    location: 'Khoản 14.1, Trang 27',
    hash: '#992c..11fa',
    title:
      'Xác nhận đối chiếu trích dẫn thẩm quyền tài phán khớp 100% với tài liệu gốc đã ký số.',
    extra:
      'VIAC (Trung tâm Trọng tài Quốc tế Việt Nam) • Chứng thư số USB Token: VNPT-CA Validated',
  },
  {
    id: '21cabb05',
    time: '17:05:44',
    date: '23/10/2024',
    type: 'edited',
    actor: actorNam,
    location: 'Phụ lục SLA, Trang 36',
    hash: '#21ca..bb05',
    title:
      'Cập nhật cam kết độ sẵn sàng hệ thống máy chủ dữ liệu (Uptime Commitment)',
    diff: {
      label: 'Chỉ số cam kết tối thiểu:',
      from: '99.5%',
      to: '99.95% (Tier III Enterprise)',
      note: '"Áp dụng tiêu chuẩn bổ sung theo yêu cầu an toàn thông tin cấp độ 4 của khách hàng."',
    },
  },
  {
    id: '5f33e209',
    time: '15:20:19',
    date: '23/10/2024',
    type: 'viewed',
    actor: actorLoan,
    location: 'Khoản 12.3, Trang 24',
    hash: '#5f33..e209',
    title:
      'Truy cập trích dẫn điều khoản bảo mật thông tin (Non-Disclosure Agreement & Data Privacy).',
    extra:
      'Thời lượng tương tác: 4 phút 12 giây • IP: 118.69.182.10 (VNPT Enterprise Gateway)',
  },
  {
    id: '17bbaa31',
    time: '10:11:05',
    date: '22/10/2024',
    type: 'verified',
    actor: actorLinh,
    location: 'Khoản 3.1, Trang 2',
    hash: '#17bb..aa31',
    title:
      'Xác nhận điều kiện bàn giao nghiệm thu từng giai đoạn (Milestone Acceptance Criteria).',
    extra:
      'Phù hợp hoàn toàn với Nghị định 73/2019/NĐ-CP về quản lý đầu tư CNTT.',
  },
  {
    id: '31dd88bc',
    time: '08:30:14',
    date: '22/10/2024',
    type: 'flagged',
    actor: { ...actorAi, role: 'Trí tuệ Pháp chế Tự động' },
    location: 'Khoản 18.2, Trang 31',
    hash: '#31dd..88bc',
    title: 'Xung đột pháp lý: Luật chuyển giao dữ liệu xuyên biên giới',
    icon: 'gpp_maybe',
    detail:
      'Điều khoản sao lưu đám mây ra ngoài lãnh thổ Việt Nam chưa có cam kết lập Hồ sơ Đánh giá Tác động Chuyển dữ liệu theo Nghị định 13/2023/NĐ-CP (PDPD).',
  },
  {
    id: '44ae12c1',
    time: '16:42:08',
    date: '21/10/2024',
    type: 'edited',
    actor: actorNam,
    location: 'Khoản 6.2, Trang 12',
    hash: '#44ae..12c1',
    title: 'Hiệu đính trần bồi thường thiệt hại 06 tháng liền kề',
    diff: {
      label: 'Giá trị thẩm định:',
      from: '80% giá trị dịch vụ',
      to: '100% giá trị dịch vụ',
      note: '"Khớp với thông lệ viễn thông và Phụ lục SLA."',
    },
  },
  {
    id: '90bb33d2',
    time: '14:05:22',
    date: '21/10/2024',
    type: 'edited',
    actor: actorLinh,
    location: 'Khoản 7.4, Trang 15',
    hash: '#90bb..33d2',
    title: 'Bổ sung ngoại lệ nghĩa vụ bảo mật tại Điều 7',
    diff: {
      label: 'Phạm vi ngoại lệ:',
      from: 'Không quy định',
      to: 'Ngoại trừ yêu cầu của cơ quan nhà nước có thẩm quyền',
    },
  },
  {
    id: '12cc78e3',
    time: '11:20:40',
    date: '21/10/2024',
    type: 'edited',
    actor: actorNam,
    location: 'Khoản 11.1, Trang 28',
    hash: '#12cc..78e3',
    title: 'Chốt cơ quan tài phán VIAC thay vì Tòa án nhân dân',
    diff: {
      label: 'Thẩm quyền giải quyết:',
      from: 'TAND TP. Hà Nội',
      to: 'VIAC',
    },
  },
  {
    id: '67df09f4',
    time: '09:18:55',
    date: '21/10/2024',
    type: 'edited',
    actor: actorNam,
    location: 'Khoản 5.3, Trang 4',
    hash: '#67df..09f4',
    title: 'Điều chỉnh lãi phạt chậm thanh toán',
    diff: {
      label: 'Lãi suất ngày:',
      from: '0.08%/ngày',
      to: '0.05%/ngày',
    },
  },
  {
    id: 'ab10c8a5',
    time: '18:02:11',
    date: '20/10/2024',
    type: 'flagged',
    actor: actorAi,
    location: 'Khoản 9.2, Trang 21',
    hash: '#ab10..c8a5',
    title: 'Cảnh báo thiếu điều khoản chấm dứt vì vi phạm nghiêm trọng',
    icon: 'flag',
    detail:
      'Hồ sơ chưa nêu rõ ngưỡng vi phạm nghiêm trọng để Bên A đơn phương chấm dứt theo Bộ luật Dân sự 2015.',
  },
  {
    id: 'cd21d9b6',
    time: '16:44:30',
    date: '20/10/2024',
    type: 'viewed',
    actor: actorLoan,
    location: 'Khoản 5.2, Trang 3',
    hash: '#cd21..d9b6',
    title: 'Đối soát hạn mức chi phí phát sinh giai đoạn 1.',
    extra: 'Thời lượng tương tác: 2 phút 08 giây',
  },
  {
    id: 'ef32e0c7',
    time: '15:11:19',
    date: '20/10/2024',
    type: 'viewed',
    actor: actorNam,
    location: 'Khoản 8.1, Trang 18',
    hash: '#ef32..e0c7',
    title: 'Xem điều khoản tạm hoãn SLA khi bất khả kháng.',
    extra: 'Thời lượng tương tác: 1 phút 33 giây',
  },
  {
    id: 'f043f1d8',
    time: '13:27:04',
    date: '20/10/2024',
    type: 'viewed',
    actor: actorLinh,
    location: 'Khoản 6.4, Trang 14',
    hash: '#f043..f1d8',
    title: 'Rà soát miễn trừ trách nhiệm tổn thất gián tiếp.',
    extra: 'Thời lượng tương tác: 3 phút 50 giây',
  },
  {
    id: '0154a2e9',
    time: '10:02:47',
    date: '20/10/2024',
    type: 'viewed',
    actor: actorLoan,
    location: 'Phụ lục SLA, Trang 36',
    hash: '#0154..a2e9',
    title: 'Kiểm tra bảng tỷ lệ khấu trừ cước viễn thông.',
    extra: 'Thời lượng tương tác: 6 phút 21 giây',
  },
  {
    id: '1265b3fa',
    time: '17:40:12',
    date: '24/10/2024',
    type: 'verified',
    actor: actorLinh,
    location: 'Khoản 5.1, Trang 4',
    hash: '#1265..b3fa',
    title: 'Xác nhận phí cố định 185.000.000 VND/quý đã khớp hóa đơn mẫu.',
  },
  {
    id: '2376c40b',
    time: '16:12:33',
    date: '24/10/2024',
    type: 'verified',
    actor: actorNam,
    location: 'Khoản 5.4, Trang 4',
    hash: '#2376..c40b',
    title: 'Xác nhận quy trình đối soát ngân sách dự phòng hàng tháng.',
  },
  {
    id: '3487d51c',
    time: '08:55:01',
    date: '23/10/2024',
    type: 'verified',
    actor: actorLinh,
    location: 'Khoản 2.1, Trang 1',
    hash: '#3487..d51c',
    title: 'Xác nhận phạm vi dịch vụ điện toán đám mây và an ninh mạng.',
  },
  {
    id: '4598e62d',
    time: '19:08:26',
    date: '22/10/2024',
    type: 'verified',
    actor: actorNam,
    location: 'Khoản 4.2, Trang 6',
    hash: '#4598..e62d',
    title: 'Xác nhận lịch nghiệm thu UAT Core Gateway.',
  },
  {
    id: '56a9f73e',
    time: '11:33:18',
    date: '22/10/2024',
    type: 'verified',
    actor: actorLinh,
    location: 'Khoản 10.1, Trang 22',
    hash: '#56a9..f73e',
    title: 'Xác nhận điều khoản bảo mật thông tin cá nhân theo PDPD.',
  },
  {
    id: '67ba084f',
    time: '09:47:52',
    date: '21/10/2024',
    type: 'verified',
    actor: actorNam,
    location: 'Khoản 13.2, Trang 25',
    hash: '#67ba..084f',
    title: 'Xác nhận nghĩa vụ thông báo sự cố trong 24 giờ.',
  },
  {
    id: '78cb1960',
    time: '15:29:41',
    date: '21/10/2024',
    type: 'verified',
    actor: actorLinh,
    location: 'Khoản 15.1, Trang 29',
    hash: '#78cb..1960',
    title: 'Xác nhận hiệu lực hợp đồng và điều kiện chữ ký số.',
  },
  {
    id: '89dc2a71',
    time: '13:14:09',
    date: '20/10/2024',
    type: 'verified',
    actor: actorNam,
    location: 'Khoản 1.2, Trang 1',
    hash: '#89dc..2a71',
    title: 'Xác nhận định nghĩa Bên A / Bên B và tài liệu đính kèm.',
  },
  {
    id: '9aed3b82',
    time: '12:02:55',
    date: '20/10/2024',
    type: 'verified',
    actor: actorLinh,
    location: 'Khoản 16.3, Trang 30',
    hash: '#9aed..3b82',
    title: 'Xác nhận điều khoản bất khả kháng có xác nhận cơ quan thẩm quyền.',
  },
  {
    id: 'abfe4c93',
    time: '08:21:37',
    date: '20/10/2024',
    type: 'verified',
    actor: actorNam,
    location: 'Khoản 19.1, Trang 32',
    hash: '#abfe..4c93',
    title: 'Xác nhận phụ lục kỹ thuật số 02 còn hiệu lực.',
  },
  {
    id: 'bc0f5da4',
    time: '18:55:20',
    date: '23/10/2024',
    type: 'verified',
    actor: actorLinh,
    location: 'Khoản 20.2, Trang 33',
    hash: '#bc0f..5da4',
    title: 'Xác nhận điều khoản sửa đổi phụ lục bằng văn bản.',
  },
  {
    id: 'cd106eb5',
    time: '07:48:03',
    date: '24/10/2024',
    type: 'verified',
    actor: actorNam,
    location: 'Khoản 21.1, Trang 34',
    hash: '#cd10..6eb5',
    title: 'Xác nhận bản v3.2 là bản có chữ ký số CA hợp lệ.',
  },
]

export const auditTotalCount = auditEvents.length

export const auditTypeCounts: Record<AuditType | 'all', number> = {
  all: auditEvents.length,
  verified: auditEvents.filter((item) => item.type === 'verified').length,
  edited: auditEvents.filter((item) => item.type === 'edited').length,
  flagged: auditEvents.filter((item) => item.type === 'flagged').length,
  viewed: auditEvents.filter((item) => item.type === 'viewed').length,
}

export const auditUsers = [
  { id: 'all', label: 'Tất cả người dùng (3 thành viên)' },
  { id: actorNam.name, label: actorNam.name },
  { id: actorLinh.name, label: actorLinh.name },
  { id: actorLoan.name, label: actorLoan.name },
  { id: actorAi.name, label: actorAi.name },
] as const

export const PAGE_SIZE = 7
export const LEDGER_HASH = '7f8a9e1022bc3d45ef8199201aa2b3c2e6840d2105e4fa'

export function exportAuditCsv(events: AuditEvent[] = auditEvents) {
  const header = 'Thời gian,Ngày,Người,Hành động,Vị trí,Chi tiết,Hash'
  const rows = events.map((event) =>
    [
      event.time,
      event.date,
      event.actor.name,
      event.type,
      event.location,
      `"${event.title.replaceAll('"', '""')}"`,
      event.hash,
    ].join(','),
  )
  const blob = new Blob([`${header}\n${rows.join('\n')}`], {
    type: 'text/csv;charset=utf-8;',
  })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'audit-log-DOS-2024-884.csv'
  link.click()
  URL.revokeObjectURL(url)
}
