export type MemberRole = 'admin' | 'user'
export type MemberStatus = 'active' | 'invited'

export type TeamMember = {
  initials: string
  name: string
  email: string
  role: MemberRole
  lastActive: string
  shared: string
  status: MemberStatus
  emphasize?: boolean
  muted?: boolean
}

export type ActivityItem = {
  icon: string
  title: string
  time: string
  detail: string
}

export const teamMembers: TeamMember[] = [
  {
    initials: 'NA',
    name: 'Nguyễn Văn An',
    email: 'an.nguyen@apexlaw.vn',
    role: 'admin',
    lastActive: '10 phút trước',
    shared: '24 hồ sơ',
    status: 'active',
    emphasize: true,
  },
  {
    initials: 'TM',
    name: 'Trần Thị Mai',
    email: 'mai.tran@apexlaw.vn',
    role: 'user',
    lastActive: '35 phút trước',
    shared: '8 hồ sơ',
    status: 'active',
  },
  {
    initials: 'HN',
    name: 'Lê Hoàng Nam',
    email: 'nam.le@apexlaw.vn',
    role: 'user',
    lastActive: '2 giờ trước',
    shared: '14 hồ sơ',
    status: 'active',
  },
  {
    initials: 'QB',
    name: 'Phạm Quốc Bảo',
    email: 'bao.pham@apexlaw.vn',
    role: 'user',
    lastActive: 'Hôm qua',
    shared: '3 hồ sơ',
    status: 'active',
  },
  {
    initials: 'TH',
    name: 'Đỗ Thu Hà',
    email: 'ha.do@apexlaw.vn',
    role: 'user',
    lastActive: '5 ngày trước',
    shared: '0 hồ sơ',
    status: 'invited',
    muted: true,
  },
]

export const recentActivities: ActivityItem[] = [
  {
    icon: 'person_add',
    title: 'Mời thành viên mới',
    time: '15p trước',
    detail: 'nam.le@apexlaw.vn',
  },
  {
    icon: 'share',
    title: 'Chia sẻ quyền truy cập',
    time: '1 giờ trước',
    detail: 'Trần Thị Mai chia sẻ 1 hồ sơ',
  },
  {
    icon: 'admin_panel_settings',
    title: 'Cập nhật phân quyền',
    time: '3 giờ trước',
    detail: 'Phòng ban Tài chính',
  },
  {
    icon: 'security',
    title: 'Đăng nhập SSO',
    time: '5 giờ trước',
    detail: 'Xác thực qua SAML 2.0',
  },
  {
    icon: 'domain_add',
    title: 'Tạo không gian làm việc',
    time: 'Hôm qua',
    detail: 'Chi nhánh TP.HCM',
  },
]
