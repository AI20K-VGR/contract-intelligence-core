import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  loadDossierStructurePreview,
  type DossierStructurePreview as PreviewData,
} from '../api/structure'
import { structurePath } from '../data/dossiers'
import { StructureMindmap } from './StructureMindmap'

export function DossierStructurePreview({
  dossierId,
  title,
}: {
  dossierId: string
  title: string
}) {
  const [data, setData] = useState<PreviewData | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    setData(null)
    setError(null)
    loadDossierStructurePreview(dossierId, controller.signal)
      .then(setData)
      .catch((cause: unknown) => {
        if (!controller.signal.aborted) {
          setError(
            cause instanceof Error
              ? cause.message
              : 'Không tải được cây cấu trúc.',
          )
        }
      })
    return () => controller.abort()
  }, [dossierId])

  if (error) {
    return <p className="font-body-sm text-body-sm text-error">{error}</p>
  }
  if (!data) {
    return (
      <p className="font-body-sm text-body-sm text-secondary">
        Đang tải cây cấu trúc hồ sơ...
      </p>
    )
  }
  if (data.mode === 'tables') {
    return (
      <div className="rounded-lg bg-surface-container-low p-space-md font-body-sm text-body-sm text-secondary">
        Hồ sơ này chủ yếu là bảng, không có cây Điều/Khoản dạng số.{' '}
        <Link
          className="font-semibold text-primary hover:underline"
          to={structurePath(dossierId)}
        >
          Mở cấu trúc bảng và OCR
        </Link>
      </div>
    )
  }
  if (data.nodes.length === 0) {
    return (
      <div className="rounded-lg bg-surface-container-low p-space-md font-body-sm text-body-sm text-secondary">
        Chưa nhận diện được tiêu đề cấu trúc từ OCR.{' '}
        <Link
          className="font-semibold text-primary hover:underline"
          to={structurePath(dossierId)}
        >
          Mở cấu trúc hồ sơ
        </Link>
      </div>
    )
  }
  return (
    <StructureMindmap
      title={title}
      subtitle={data.document?.filename}
      nodes={data.nodes}
    />
  )
}
