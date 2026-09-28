import { useLocation } from 'react-router-dom'
import {
  DynamicCitationViewer,
  normalizeCitationViewerModel,
} from '../components/DynamicCitationViewer'
import { usePageTitle } from '../hooks/usePageTitle'

export function CitationComparePage() {
  usePageTitle('Đối soát citation')
  const location = useLocation()
  const state = location.state as {
    citation?: unknown
    dossierId?: string
  } | null
  const citation = normalizeCitationViewerModel(
    state?.citation,
    state?.dossierId ?? '',
  )

  return (
    <main className="w-full space-y-space-md">
      <div className="rounded-xl border border-outline-variant/30 bg-surface-container-lowest p-space-md">
        <h1 className="font-headline-md text-headline-md text-primary">
          Đối soát citation
        </h1>
        <p className="mt-space-xs font-body-sm text-body-sm text-secondary">
          Viewer dùng dossier/document/source citation từ Backend; citation chưa
          resolve được giữ ở trạng thái gap.
        </p>
      </div>
      <DynamicCitationViewer citation={citation} />
    </main>
  )
}
