import { useState } from 'react'
import { createRoot } from 'react-dom/client'
import { Ai2GraphDossierView } from './components/ai2-graph/ContractGraphCanvas'
import './index.css'

function ManualGraphCheck() {
  const [action, setAction] = useState('Chưa mở bằng chứng (dữ liệu kiểm tra tổng hợp).')
  const resolveNodeLabel = (nodeId: string, documentId?: string | null) =>
    `${documentId === 'body-doc' ? 'Hợp đồng gốc' : `Phụ lục ${documentId ?? 'chưa rõ'}`} · ${nodeId}`

  return (
    <div className="mx-auto flex min-w-0 max-w-5xl flex-col gap-3 p-3">
      <p role="status" className="break-words text-sm">
        Manual viewport fixture · API responses mocked · chỉ dữ liệu tổng hợp
      </p>
      <Ai2GraphDossierView
        enabled
        dossierId="manual-dossier"
        jobId="manual-job"
        snapshotDigest="manual-snapshot"
        graphKind="pair"
        resolveNodeLabel={resolveNodeLabel}
        onOpenCitation={(ref, node) => setAction(`Citation action: ${ref} · ${node}`)}
        onSelectRelation={() => {}}
      />
      <p role="status" aria-live="polite">{action}</p>
    </div>
  )
}

createRoot(document.getElementById('root')!).render(<ManualGraphCheck />)
