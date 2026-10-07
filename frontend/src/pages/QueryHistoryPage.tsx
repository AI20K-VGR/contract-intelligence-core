import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { dossiersLabel, dossiersPath } from '../auth/session'
import { useAuth } from '../auth/useAuth'
import { MaterialIcon } from '../components/icons'
import { QueryHistoryPanel } from '../components/QueryHistoryPanel'
import { usePageTitle } from '../hooks/usePageTitle'

function stateName(state: unknown) {
  if (!state || typeof state !== 'object') return null
  const name = (state as { name?: unknown }).name
  return typeof name === 'string' && name ? name : null
}

/** Lịch sử hỏi đáp của một hồ sơ. "Hỏi lại" quay về trang cấu trúc với câu hỏi điền sẵn. */
export function QueryHistoryPage() {
  const { dossierId = '' } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const { user } = useAuth()
  const name = stateName(location.state)
  const structurePath = '/cau-truc/' + encodeURIComponent(dossierId)
  usePageTitle(name ? `Lịch sử hỏi đáp · ${name}` : 'Lịch sử hỏi đáp')

  return (
    <div className="flex flex-col gap-space-md pt-space-md pb-space-lg">
      <nav className="flex items-center gap-space-xs font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">
        <Link
          className="hover:text-primary transition-colors"
          to={user ? dossiersPath(user.role) : '/'}
        >
          {user ? dossiersLabel(user.role) : 'Hồ sơ'}
        </Link>
        <MaterialIcon name="chevron_right" className="text-[14px]" />
        <Link className="hover:text-primary transition-colors" to={structurePath}>
          Cấu trúc cây
        </Link>
        <MaterialIcon name="chevron_right" className="text-[14px]" />
        <span className="text-on-surface font-semibold">Lịch sử hỏi đáp</span>
      </nav>
      <QueryHistoryPanel
        dossierId={dossierId}
        refreshKey={0}
        onReuse={(question) =>
          navigate(structurePath, { state: { query: question } })
        }
      />
    </div>
  )
}
