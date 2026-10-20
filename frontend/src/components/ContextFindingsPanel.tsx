export type ContextFindingPanelItem = {
  id: string
  reasonCode: string
  subject: string
  reviewState: string
}

export type EvidenceIssuePanelItem = {
  code: string
  message: string
}

export type ContextFindingsPanelModel = {
  facts: unknown[]
  findings: unknown[]
  contextFindings: ContextFindingPanelItem[]
  evidenceIssues: EvidenceIssuePanelItem[]
  coverage: Record<string, unknown>
  trace: Array<Record<string, unknown>>
  reviewState: string
}

import {
  issueLabel,
  reasonLabel,
  reviewStateLabel,
  stateLabel,
} from '../structure/displayLabels'
import { TechnicalDetail } from './TechnicalDetail'

function scalar(value: unknown) {
  if (typeof value === 'string' || typeof value === 'number')
    return String(value)
  return ''
}

export function ContextFindingsPanel({
  model,
}: {
  model: ContextFindingsPanelModel
}) {
  const pages = scalar(model.coverage.pages) || '?'
  const covered = scalar(model.coverage.covered) || '?'
  const coverageStatus = stateLabel(scalar(model.coverage.status))

  return (
    <section
      aria-label="Phát hiện và căn cứ"
      className="rounded-xl border border-outline-variant/30 bg-surface-container-lowest p-space-md shadow-sm"
    >
      <div className="flex flex-wrap items-center justify-between gap-space-sm">
        <h2 className="font-title-sm text-title-sm font-semibold text-primary">
          Phát hiện và mức độ căn cứ
        </h2>
        <span className="rounded bg-amber-50 px-space-xs py-0.5 font-code-sm text-code-sm text-amber-900">
          {reviewStateLabel(model.reviewState)}
        </span>
      </div>

      <div className="mt-space-sm grid gap-space-sm sm:grid-cols-3">
        <div className="rounded bg-surface-container-low p-space-sm font-body-sm text-body-sm">
          <strong className="block font-code-sm text-code-sm text-primary">
            {model.facts.length} dữ kiện
          </strong>
          <span className="text-secondary">Dữ liệu có cấu trúc</span>
        </div>
        <div className="rounded bg-surface-container-low p-space-sm font-body-sm text-body-sm">
          <strong className="block font-code-sm text-code-sm text-primary">
            {model.findings.length} phát hiện
          </strong>
          <span className="text-secondary">So sánh/xung đột</span>
        </div>
        <div className="rounded bg-surface-container-low p-space-sm font-body-sm text-body-sm">
          <strong className="block font-code-sm text-code-sm text-primary">
            {covered} / {pages}
          </strong>
          <span className="text-secondary">
            Số trang có căn cứ · {coverageStatus}
          </span>
        </div>
      </div>

      <div className="mt-space-md grid gap-space-md lg:grid-cols-2">
        <div>
          <h3 className="font-label-md text-label-md font-semibold text-on-surface">
            Phát hiện theo ngữ cảnh ({model.contextFindings.length})
          </h3>
          {model.contextFindings.length === 0 ? (
            <p className="mt-space-xs font-body-sm text-body-sm text-secondary">
              Chưa có phát hiện nào.
            </p>
          ) : (
            <ul className="mt-space-xs space-y-space-xs">
              {model.contextFindings.map((finding) => (
                <li
                  key={finding.id}
                  className="rounded border border-outline-variant/20 p-space-sm font-body-sm text-body-sm"
                >
                  <span className="font-semibold text-primary">
                    {reasonLabel(finding.reasonCode)}
                  </span>
                  <span className="ml-2 text-on-surface">
                    {finding.subject}
                  </span>
                  <span className="ml-2 text-secondary">
                    {reviewStateLabel(finding.reviewState)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div>
          <h3 className="font-label-md text-label-md font-semibold text-on-surface">
            Vấn đề về căn cứ ({model.evidenceIssues.length})
          </h3>
          {model.evidenceIssues.length === 0 ? (
            <p className="mt-space-xs font-body-sm text-body-sm text-secondary">
              Chưa có vấn đề nào.
            </p>
          ) : (
            <ul className="mt-space-xs space-y-space-xs">
              {model.evidenceIssues.map((issue) => (
                <li
                  key={issue.code}
                  className="rounded border border-amber-200 bg-amber-50 p-space-sm font-body-sm text-body-sm text-amber-950"
                >
                  {issueLabel(issue.code)}
                  <TechnicalDetail text={`${issue.code}: ${issue.message}`} />
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="mt-space-md border-t border-outline-variant/20 pt-space-sm">
        <h3 className="font-label-md text-label-md font-semibold text-on-surface">
          Các bước suy luận ({model.trace.length})
        </h3>
        {model.trace.length === 0 ? (
          <p className="mt-space-xs font-body-sm text-body-sm text-secondary">
            Chưa có thông tin các bước suy luận.
          </p>
        ) : (
          <p className="mt-space-xs font-body-sm text-body-sm text-secondary">
            AI đã thực hiện {model.trace.length} bước để tìm câu trả lời.
            <TechnicalDetail
              text={model.trace
                .map((event) => scalar(event.code) || scalar(event.type))
                .filter(Boolean)
                .join(' → ')}
            />
          </p>
        )}
      </div>
    </section>
  )
}
