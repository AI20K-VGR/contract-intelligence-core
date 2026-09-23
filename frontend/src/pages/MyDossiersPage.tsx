import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { MaterialIcon } from '../components/icons'
import {
  myDossiers,
  dossierOpenTo,
  type Dossier,
  type DossierStatus,
} from '../data/dossiers'
import { dossiersLabel } from '../auth/session'
import { useAuth } from '../auth/useAuth'
import { usePageTitle } from '../hooks/usePageTitle'

type StatusFilter = 'all' | DossierStatus

const filters: { id: StatusFilter; label: string }[] = [
  { id: 'all', label: 'Tất cả' },
  { id: 'processing', label: 'Đang xử lý' },
  { id: 'ready', label: 'Sẵn sàng' },
  { id: 'review', label: 'Cần rà soát' },
]

function countByStatus(status?: DossierStatus) {
  if (!status) return myDossiers.length
  return myDossiers.filter((item) => item.status === status).length
}

function StatusCell({ dossier }: { dossier: Dossier }) {
  if (dossier.status === 'processing') {
    return (
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded font-label-sm text-label-sm font-semibold bg-amber-100 text-amber-900">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-600 animate-pulse" />
            Đang xử lý
          </span>
          <span className="font-code-sm text-label-sm text-on-surface-variant">
            {dossier.progressLabel}
          </span>
        </div>
        <div className="w-40 h-1.5 bg-surface-container-high rounded-full overflow-hidden">
          <div
            className="h-full bg-amber-500 rounded-full"
            style={{ width: `${dossier.progress ?? 0}%` }}
          />
        </div>
      </div>
    )
  }

  if (dossier.status === 'review') {
    return (
      <div className="flex flex-col gap-0.5">
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded font-label-sm text-label-sm font-semibold bg-error-container text-on-error-container w-fit">
          <MaterialIcon name="warning" className="text-[14px]" />
          Cần rà soát
        </span>
        {dossier.reviewNote ? (
          <span className="font-code-sm text-label-sm text-error font-medium mt-0.5">
            {dossier.reviewNote}
          </span>
        ) : null}
      </div>
    )
  }

  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded font-label-sm text-label-sm font-semibold bg-emerald-100 text-emerald-900">
      <MaterialIcon name="check_circle" className="text-[14px]" />
      Sẵn sàng
    </span>
  )
}

function AccessBadge({ dossier }: { dossier: Dossier }) {
  if (dossier.access === 'shared-admin') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-surface-container-high font-body-sm text-label-sm text-on-tertiary-container font-medium">
        <MaterialIcon name="share" className="text-[14px]" />
        <span>Đã chia sẻ với Admin</span>
      </span>
    )
  }

  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-surface-container font-body-sm text-label-sm text-on-secondary-container">
      <MaterialIcon name="lock" className="text-[14px]" />
      <span>Riêng tư</span>
    </span>
  )
}

function DossierToolbar({
  query,
  onQueryChange,
  status,
  onStatusChange,
}: {
  query: string
  onQueryChange: (value: string) => void
  status: StatusFilter
  onStatusChange: (value: StatusFilter) => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-space-md flex-1">
      <div className="relative min-w-[260px] max-w-sm">
        <MaterialIcon
          name="search"
          className="absolute left-space-sm top-1/2 -translate-y-1/2 text-on-surface-variant text-[18px]"
        />
        <input
          className="w-full h-9 pl-9 pr-space-md bg-surface-container-low text-on-surface placeholder:text-on-surface-variant font-body-sm text-body-sm rounded focus:outline-none focus:bg-surface-container-lowest shadow-inner"
          placeholder="Tìm kiếm theo tên, mã hồ sơ..."
          type="search"
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
        />
      </div>
      <div className="inline-flex items-center bg-surface-container-low p-1 rounded-lg gap-1">
        {filters.map((item) => {
          const active = status === item.id
          const count =
            item.id === 'all' ? countByStatus() : countByStatus(item.id)
          return (
            <button
              key={item.id}
              className={`px-3 py-1 rounded font-label-sm text-label-sm uppercase tracking-wide flex items-center gap-1.5 transition-colors ${
                active
                  ? 'bg-surface-container-lowest text-on-surface shadow-sm font-semibold'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
              type="button"
              onClick={() => onStatusChange(item.id)}
            >
              {item.id === 'processing' ? (
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
              ) : null}
              {item.id === 'ready' ? (
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
              ) : null}
              {item.id === 'review' ? (
                <span className="w-1.5 h-1.5 rounded-full bg-error" />
              ) : null}
              <span>{item.label}</span>
              <span
                className={`font-code-sm text-[11px] ${
                  item.id === 'all' && active ? 'text-on-surface-variant' : ''
                }`}
              >
                {count}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

export function MyDossiersPage() {
  const { user } = useAuth()
  const heading = user ? dossiersLabel(user.role) : 'Hồ sơ'
  usePageTitle(heading)
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<StatusFilter>('all')

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase()
    return myDossiers.filter((item) => {
      const matchesStatus = status === 'all' || item.status === status
      const matchesQuery =
        needle.length === 0 ||
        item.title.toLowerCase().includes(needle) ||
        item.code.toLowerCase().includes(needle)
      return matchesStatus && matchesQuery
    })
  }, [query, status])

  return (
    <div className="flex flex-col w-full pb-margin-lg">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-space-md pt-space-lg pb-space-lg">
        <div className="flex flex-col gap-space-xs">
          <div className="flex items-center gap-space-sm">
            <h1 className="font-headline-lg text-headline-lg text-on-surface tracking-tight">
              {heading}
            </h1>
            <span className="px-2 py-0.5 rounded bg-surface-container text-on-surface-variant font-code-sm text-code-sm">
              {myDossiers.length} hồ sơ hoạt động
            </span>
          </div>
          <p className="font-body-sm text-body-sm text-on-surface-variant">
            Quản lý, phân tích ngữ nghĩa và tra cứu tài liệu hợp đồng pháp lý cá
            nhân
          </p>
        </div>
        <div className="flex items-center gap-space-sm">
          <button
            className="flex items-center gap-space-xs px-space-md py-2 bg-surface-container-lowest text-on-surface font-title-sm text-body-sm rounded shadow-[0_1px_2px_rgba(15,23,42,0.06)] hover:bg-surface-container transition-colors"
            type="button"
          >
            <MaterialIcon
              name="file_copy"
              className="text-[18px] text-secondary"
            />
            <span>Nhập từ mẫu</span>
          </button>
          <Link
            className="flex items-center gap-space-xs px-space-md py-2 bg-primary-container text-on-primary font-title-sm text-body-sm rounded shadow-sm hover:bg-tertiary-container transition-colors"
            to="/tao-ho-so"
          >
            <MaterialIcon name="add" className="text-[18px]" />
            <span>Tạo hồ sơ mới</span>
          </Link>
        </div>
      </div>

      <div className="bg-surface-container-lowest rounded-lg shadow-[0_1px_3px_rgba(15,23,42,0.06)] flex flex-col overflow-hidden">
        <div className="p-space-md flex flex-col xl:flex-row xl:items-center justify-between gap-space-md bg-surface-container-lowest">
          <DossierToolbar
            query={query}
            onQueryChange={setQuery}
            status={status}
            onStatusChange={setStatus}
          />
          <div className="flex items-center gap-space-xs self-end xl:self-auto">
            <div className="flex items-center gap-1 text-on-surface-variant font-body-sm text-body-sm px-2.5 py-1.5 bg-surface-container-low rounded">
              <MaterialIcon name="swap_vert" className="text-[16px]" />
              <span className="text-on-surface font-title-sm text-body-sm">
                Mới nhất trước
              </span>
            </div>
            <button
              className="p-1.5 text-on-surface-variant hover:text-on-surface hover:bg-surface-container rounded transition-colors"
              title="Bộ lọc nâng cao"
              type="button"
            >
              <MaterialIcon name="tune" className="text-[20px]" />
            </button>
          </div>
        </div>

        <div className="w-full overflow-x-auto">
          <table className="w-full text-left font-body-sm text-body-sm border-collapse">
            <thead>
              <tr className="bg-surface-container-low text-on-secondary-container font-label-sm text-label-sm uppercase tracking-wider">
                <th className="py-3 px-space-md font-semibold w-[36%] min-w-[300px]">
                  Tên hồ sơ
                </th>
                <th className="py-3 px-space-md font-semibold w-[26%] min-w-[240px]">
                  Trạng thái & Tiến trình
                </th>
                <th className="py-3 px-space-md font-semibold text-center w-[10%]">
                  Số tài liệu
                </th>
                <th className="py-3 px-space-md font-semibold w-[12%]">
                  Cập nhật
                </th>
                <th className="py-3 px-space-md font-semibold w-[12%]">
                  Quyền truy cập
                </th>
                <th className="py-3 px-space-sm text-right pr-space-md font-semibold w-[4%]">
                  Thao tác
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-container-low text-on-surface">
              {filtered.map((dossier) => (
                <tr
                  key={dossier.id}
                  className="hover:bg-surface-container-low/70 transition-colors bg-surface-container-lowest"
                >
                  <td className="py-3.5 px-space-md">
                    <div className="flex items-start gap-space-sm">
                      <MaterialIcon
                        name={dossier.icon}
                        className="text-primary-container text-[20px] mt-0.5 flex-shrink-0"
                      />
                      <div className="flex flex-col">
                        <Link
                          className="font-title-sm text-title-sm text-on-surface hover:text-on-tertiary-container cursor-pointer leading-tight font-semibold"
                          state={
                            dossier.status === 'processing'
                              ? { name: dossier.title }
                              : undefined
                          }
                          to={dossierOpenTo(dossier)}
                        >
                          {dossier.title}
                        </Link>
                        <span className="font-code-sm text-label-sm text-on-surface-variant mt-1 whitespace-nowrap">
                          {dossier.code} • {dossier.size}
                        </span>
                      </div>
                    </div>
                  </td>
                  <td className="py-3.5 px-space-md">
                    <StatusCell dossier={dossier} />
                  </td>
                  <td className="py-3.5 px-space-md text-center whitespace-nowrap">
                    <span className="font-code-sm text-body-sm font-medium">
                      {dossier.documents} tài liệu
                    </span>
                  </td>
                  <td className="py-3.5 px-space-md whitespace-nowrap">
                    <span className="text-on-surface-variant text-body-sm">
                      {dossier.updated}
                    </span>
                  </td>
                  <td className="py-3.5 px-space-md whitespace-nowrap">
                    <AccessBadge dossier={dossier} />
                  </td>
                  <td className="py-3.5 px-space-sm text-right pr-space-md whitespace-nowrap">
                    <button
                      aria-label="Thao tác"
                      className="p-1 hover:bg-surface-container rounded text-on-surface-variant hover:text-on-surface transition-colors"
                      type="button"
                    >
                      <MaterialIcon name="more_vert" className="text-[18px]" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
