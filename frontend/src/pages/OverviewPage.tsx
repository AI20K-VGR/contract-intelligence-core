import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { MaterialIcon } from '../components/icons'
import {
  recentActivities,
  teamMembers,
  type MemberRole,
  type TeamMember,
} from '../data/overview'
import { usePageTitle } from '../hooks/usePageTitle'

const roleLabel: Record<MemberRole, string> = {
  admin: 'Quản trị viên',
  user: 'Người dùng',
}

function MemberRow({ member }: { member: TeamMember }) {
  return (
    <tr className="hover:bg-surface-container-low/60 transition-colors">
      <td className="py-3.5 px-space-lg">
        <div className="flex items-center gap-space-md">
          <div
            className={`w-8 h-8 rounded-full flex items-center justify-center font-title-sm text-title-sm font-semibold shrink-0 ${
              member.emphasize
                ? 'bg-primary-container text-on-primary'
                : 'bg-surface-container text-secondary'
            } ${member.muted ? 'opacity-60' : ''}`}
          >
            {member.initials}
          </div>
          <div className="flex flex-col min-w-0">
            <span
              className={`font-title-sm text-title-sm text-on-surface truncate ${
                member.muted ? 'opacity-75' : ''
              }`}
            >
              {member.name}
            </span>
            <span className="font-body-sm text-body-sm text-secondary truncate">
              {member.email}
            </span>
          </div>
        </div>
      </td>
      <td className="py-3.5 px-space-md">
        <span
          className={`inline-flex items-center px-2 py-0.5 rounded font-label-sm text-label-sm ${
            member.role === 'admin'
              ? 'bg-primary-container text-on-primary'
              : 'bg-surface-container text-secondary'
          }`}
        >
          {roleLabel[member.role]}
        </span>
      </td>
      <td className="py-3.5 px-space-md text-secondary">{member.lastActive}</td>
      <td
        className={`py-3.5 px-space-md font-code-sm text-code-sm ${
          member.muted ? 'text-secondary' : 'text-on-surface'
        }`}
      >
        {member.shared}
      </td>
      <td className="py-3.5 px-space-md">
        {member.status === 'active' ? (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-surface-container text-on-surface font-label-sm text-label-sm">
            <span className="w-1.5 h-1.5 rounded-full bg-secondary" />
            Đang hoạt động
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-surface-container-high text-secondary font-label-sm text-label-sm">
            <span className="w-1.5 h-1.5 rounded-full bg-outline" />
            Đã mời
          </span>
        )}
      </td>
      <td className="py-3.5 px-space-md text-right">
        <button
          className="w-7 h-7 rounded flex items-center justify-center text-secondary hover:bg-surface-container hover:text-on-surface transition-colors ml-auto"
          type="button"
        >
          <MaterialIcon name="more_vert" className="text-[18px]" />
        </button>
      </td>
    </tr>
  )
}

export function OverviewPage() {
  usePageTitle('Tổng quan hệ thống')
  const [query, setQuery] = useState('')
  const [role, setRole] = useState<'all' | MemberRole>('all')

  const filteredMembers = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return teamMembers.filter((member) => {
      const matchesRole = role === 'all' || member.role === role
      const matchesQuery =
        needle.length === 0 ||
        member.name.toLowerCase().includes(needle) ||
        member.email.toLowerCase().includes(needle)
      return matchesRole && matchesQuery
    })
  }, [query, role])

  const isFiltered = query.trim().length > 0 || role !== 'all'
  const total = isFiltered ? filteredMembers.length : 48
  const from = filteredMembers.length === 0 ? 0 : 1
  const to = filteredMembers.length

  return (
    <div className="flex flex-col w-full gap-space-lg">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-space-md">
        <div className="flex flex-col gap-space-xs">
          <h1 className="font-headline-lg text-headline-lg text-on-surface tracking-tight">
            Tổng quan hệ thống
          </h1>
        </div>
        <div className="flex items-center gap-space-sm self-start md:self-auto">
          <button
            className="flex items-center gap-space-xs px-space-md py-2 rounded bg-surface-container-lowest text-on-surface hover:bg-surface-container transition-colors shadow-sm font-label-md text-label-md"
            type="button"
          >
            <MaterialIcon
              name="file_download"
              className="text-[18px] text-secondary"
            />
            <span>Xuất báo cáo</span>
          </button>
          <button
            className="flex items-center gap-space-xs px-space-lg py-2 rounded bg-primary-container text-on-primary hover:bg-inverse-surface transition-colors shadow-sm font-label-md text-label-md"
            type="button"
          >
            <MaterialIcon name="person_add" className="text-[18px]" />
            <span>Mời thành viên</span>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-space-md">
        <div className="bg-surface-container-lowest p-space-lg rounded shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-secondary">
            <span className="font-label-sm text-label-sm tracking-wider uppercase">
              Tổng người dùng
            </span>
            <MaterialIcon name="group" className="text-[20px] text-secondary" />
          </div>
          <div className="mt-space-md flex items-baseline justify-between">
            <span className="font-display-lg text-display-lg text-on-surface font-semibold">
              48
            </span>
            <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-surface-container text-secondary font-label-sm text-label-sm">
              <MaterialIcon name="trending_up" className="text-[12px]" /> +3
            </span>
          </div>
        </div>

        <div className="bg-surface-container-lowest p-space-lg rounded shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-secondary">
            <span className="font-label-sm text-label-sm tracking-wider uppercase">
              Hồ sơ hoạt động
            </span>
            <MaterialIcon
              name="inventory_2"
              className="text-[20px] text-secondary"
            />
          </div>
          <div className="mt-space-md flex items-baseline justify-between">
            <span className="font-display-lg text-display-lg text-on-surface font-semibold">
              1.240
            </span>
          </div>
        </div>

        <div className="bg-surface-container-lowest p-space-lg rounded shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-secondary">
            <span className="font-label-sm text-label-sm tracking-wider uppercase">
              Dung lượng
            </span>
            <MaterialIcon
              name="cloud_done"
              className="text-[20px] text-secondary"
            />
          </div>
          <div className="mt-space-md">
            <div className="flex items-baseline justify-between">
              <span className="font-headline-lg text-headline-lg text-on-surface font-semibold">
                68.4{' '}
                <span className="font-title-sm text-title-sm text-secondary font-normal">
                  / 100 GB
                </span>
              </span>
              <span className="font-code-sm text-code-sm text-on-surface font-semibold">
                68%
              </span>
            </div>
            <div className="w-full bg-surface-container rounded-full h-1.5 mt-space-sm overflow-hidden">
              <div
                className="bg-primary-container h-full rounded-full"
                style={{ width: '68%' }}
              />
            </div>
          </div>
        </div>

        <div className="bg-surface-container-lowest p-space-lg rounded shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-secondary">
            <span className="font-label-sm text-label-sm tracking-wider uppercase">
              Lời mời chờ duyệt
            </span>
            <MaterialIcon
              name="mark_email_unread"
              className="text-[20px] text-secondary"
            />
          </div>
          <div className="mt-space-md flex items-baseline justify-between">
            <span className="font-display-lg text-display-lg text-on-surface font-semibold">
              4
            </span>
          </div>
        </div>
      </div>

      <div className="w-full bg-surface-container-low px-space-lg py-space-md rounded flex items-center justify-between gap-space-md">
        <div className="flex items-center gap-space-md min-w-0">
          <div className="w-7 h-7 rounded bg-surface-container flex items-center justify-center shrink-0">
            <MaterialIcon name="lock" className="text-secondary text-[16px]" />
          </div>
          <p className="font-body-sm text-body-sm text-on-surface-variant truncate md:whitespace-normal">
            <strong className="font-title-sm text-title-sm text-on-surface">
              Chính sách:
            </strong>{' '}
            Admin chỉ xem được hồ sơ khi người dùng chủ động chia sẻ.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-space-lg items-start">
        <div className="lg:col-span-8 flex flex-col bg-surface-container-lowest rounded shadow-sm overflow-hidden">
          <div className="p-space-lg flex flex-col sm:flex-row sm:items-center justify-between gap-space-md bg-surface-container-lowest">
            <div>
              <h2 className="font-headline-md text-headline-md text-on-surface font-semibold">
                Thành viên nhóm
              </h2>
            </div>
            <div className="flex items-center gap-space-sm flex-wrap">
              <div className="relative flex items-center">
                <MaterialIcon
                  name="search"
                  className="absolute left-2.5 text-secondary text-[16px]"
                />
                <input
                  className="pl-8 pr-space-md py-1.5 bg-surface-container text-on-surface rounded font-body-sm text-body-sm placeholder:text-outline focus:outline-none focus:bg-surface-container-lowest focus:ring-1 focus:ring-secondary w-44 sm:w-56"
                  placeholder="Tìm theo tên, email..."
                  type="search"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
              </div>
              <div className="relative">
                <select
                  className="appearance-none bg-surface-container text-on-surface font-body-sm text-body-sm py-1.5 pl-3 pr-8 rounded focus:outline-none cursor-pointer"
                  value={role}
                  onChange={(event) =>
                    setRole(event.target.value as 'all' | MemberRole)
                  }
                >
                  <option value="all">Tất cả vai trò</option>
                  <option value="admin">Quản trị viên</option>
                  <option value="user">Người dùng</option>
                </select>
                <MaterialIcon
                  name="expand_more"
                  className="absolute right-2 top-2 pointer-events-none text-secondary text-[16px]"
                />
              </div>
            </div>
          </div>

          <div className="w-full overflow-x-auto">
            <table className="w-full text-left text-on-surface font-body-sm text-body-sm">
              <thead>
                <tr className="bg-surface-container-low text-secondary font-label-sm text-label-sm uppercase tracking-wider">
                  <th className="py-3 px-space-lg" scope="col">
                    Thành viên
                  </th>
                  <th className="py-3 px-space-md" scope="col">
                    Vai trò
                  </th>
                  <th className="py-3 px-space-md" scope="col">
                    Hoạt động gần nhất
                  </th>
                  <th className="py-3 px-space-md" scope="col">
                    Được chia sẻ
                  </th>
                  <th className="py-3 px-space-md" scope="col">
                    Trạng thái
                  </th>
                  <th className="py-3 px-space-md text-right" scope="col" />
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-container-low">
                {filteredMembers.map((member) => (
                  <MemberRow key={member.email} member={member} />
                ))}
              </tbody>
            </table>
          </div>

          <div className="p-space-md bg-surface-container-lowest flex items-center justify-between">
            <span className="font-body-sm text-body-sm text-secondary">
              Hiển thị{' '}
              <span className="font-semibold text-on-surface">
                {from} - {to}
              </span>{' '}
              của <span className="font-semibold text-on-surface">{total}</span>{' '}
              thành viên
            </span>
            <div className="flex items-center gap-space-xs">
              <button
                className="px-space-md py-1 rounded bg-surface-container-low text-outline font-label-sm text-label-sm cursor-not-allowed"
                disabled
                type="button"
              >
                Trước
              </button>
              <button
                className="px-space-md py-1 rounded bg-surface-container text-on-surface hover:bg-surface-container-high font-label-sm text-label-sm transition-colors"
                type="button"
              >
                Sau
              </button>
            </div>
          </div>
        </div>

        <div className="lg:col-span-4 flex flex-col bg-surface-container-lowest rounded shadow-sm p-space-lg">
          <div className="flex items-center justify-between mb-space-md">
            <div className="flex items-center gap-space-xs">
              <MaterialIcon
                name="history"
                className="text-[18px] text-secondary"
              />
              <h2 className="font-headline-md text-headline-md text-on-surface font-semibold">
                Hoạt động gần đây
              </h2>
            </div>
            <Link
              className="font-label-sm text-label-sm text-secondary hover:text-on-surface underline"
              to="/nhat-ky-phap-ly"
            >
              Xem tất cả
            </Link>
          </div>

          <div className="flex flex-col gap-space-lg relative">
            {recentActivities.map((event) => (
              <div key={event.title} className="flex items-start gap-space-md">
                <div className="w-7 h-7 rounded bg-surface-container flex items-center justify-center text-secondary shrink-0 mt-0.5">
                  <MaterialIcon name={event.icon} className="text-[15px]" />
                </div>
                <div className="flex flex-col min-w-0 flex-1">
                  <div className="flex items-baseline justify-between gap-space-xs">
                    <span className="font-title-sm text-title-sm text-on-surface truncate">
                      {event.title}
                    </span>
                    <span className="font-label-sm text-label-sm text-secondary shrink-0">
                      {event.time}
                    </span>
                  </div>
                  <p className="font-body-sm text-body-sm text-secondary mt-0.5 truncate">
                    {event.detail}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
