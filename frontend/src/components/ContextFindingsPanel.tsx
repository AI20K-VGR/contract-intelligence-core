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
  const coverageStatus = scalar(model.coverage.status) || 'UNKNOWN'

  return (
    <section
      aria-label="Context findings and evidence"
      className="rounded-xl border border-outline-variant/30 bg-surface-container-lowest p-space-md shadow-sm"
    >
      <div className="flex flex-wrap items-center justify-between gap-space-sm">
        <h2 className="font-title-sm text-title-sm font-semibold text-primary">
          Context & evidence coverage
        </h2>
        <span className="rounded bg-amber-50 px-space-xs py-0.5 font-code-sm text-code-sm text-amber-900">
          {model.reviewState}
        </span>
      </div>

      <div className="mt-space-sm grid gap-space-sm sm:grid-cols-3">
        <div className="rounded bg-surface-container-low p-space-sm font-body-sm text-body-sm">
          <strong className="block font-code-sm text-code-sm text-primary">
            {model.facts.length} facts
          </strong>
          <span className="text-secondary">Dữ liệu có cấu trúc</span>
        </div>
        <div className="rounded bg-surface-container-low p-space-sm font-body-sm text-body-sm">
          <strong className="block font-code-sm text-code-sm text-primary">
            {model.findings.length} findings
          </strong>
          <span className="text-secondary">So sánh/xung đột</span>
        </div>
        <div className="rounded bg-surface-container-low p-space-sm font-body-sm text-body-sm">
          <strong className="block font-code-sm text-code-sm text-primary">
            {covered} / {pages}
          </strong>
          <span className="text-secondary">Coverage · {coverageStatus}</span>
        </div>
      </div>

      <div className="mt-space-md grid gap-space-md lg:grid-cols-2">
        <div>
          <h3 className="font-label-md text-label-md font-semibold text-on-surface">
            Context findings ({model.contextFindings.length})
          </h3>
          {model.contextFindings.length === 0 ? (
            <p className="mt-space-xs font-body-sm text-body-sm text-secondary">
              Không có context finding từ backend.
            </p>
          ) : (
            <ul className="mt-space-xs space-y-space-xs">
              {model.contextFindings.map((finding) => (
                <li
                  key={finding.id}
                  className="rounded border border-outline-variant/20 p-space-sm font-body-sm text-body-sm"
                >
                  <span className="font-code-sm text-code-sm text-primary">
                    {finding.reasonCode}
                  </span>
                  <span className="ml-2 text-on-surface">
                    {finding.subject}
                  </span>
                  <span className="ml-2 text-secondary">
                    {finding.reviewState}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div>
          <h3 className="font-label-md text-label-md font-semibold text-on-surface">
            Evidence issues ({model.evidenceIssues.length})
          </h3>
          {model.evidenceIssues.length === 0 ? (
            <p className="mt-space-xs font-body-sm text-body-sm text-secondary">
              Không có evidence issue từ backend.
            </p>
          ) : (
            <ul className="mt-space-xs space-y-space-xs">
              {model.evidenceIssues.map((issue) => (
                <li
                  key={issue.code}
                  className="rounded border border-amber-200 bg-amber-50 p-space-sm font-body-sm text-body-sm text-amber-950"
                >
                  <span className="font-code-sm text-code-sm">
                    {issue.code}
                  </span>
                  <span className="ml-2">{issue.message}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="mt-space-md border-t border-outline-variant/20 pt-space-sm">
        <h3 className="font-label-md text-label-md font-semibold text-on-surface">
          Trace ({model.trace.length})
        </h3>
        {model.trace.length === 0 ? (
          <p className="mt-space-xs font-body-sm text-body-sm text-secondary">
            Backend không trả reasoning trace.
          </p>
        ) : (
          <ul className="mt-space-xs flex flex-wrap gap-space-xs">
            {model.trace.map((event, index) => (
              <li
                key={`${scalar(event.code) || 'trace'}-${index}`}
                className="rounded bg-surface-container px-space-xs py-0.5 font-code-sm text-code-sm text-secondary"
              >
                {scalar(event.code) || scalar(event.type) || 'trace'}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}
