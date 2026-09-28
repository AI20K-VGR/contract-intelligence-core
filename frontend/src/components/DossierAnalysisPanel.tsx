import { useEffect, useState } from 'react'
import {
  getDossierAi2Analysis,
  listDossierFacts,
  listDossierFindings,
  type Ai2Analysis,
  type DossierFact,
  type DossierFinding,
  type StructuredEvidence,
} from '../api/analysis'
import {
  ContextFindingsPanel,
  type ContextFindingsPanelModel,
} from './ContextFindingsPanel'

export type DossierAnalysisPanelProps = {
  dossierId: string
  onOpenEvidence?: (evidence: StructuredEvidence, fallbackText: string) => void
}

function valueText(value: unknown) {
  if (typeof value === 'string') return value
  if (value === null || value === undefined) return ''
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {}
}

function stringValue(value: unknown, fallback: string) {
  return typeof value === 'string' && value.trim() ? value : fallback
}

export function contextPanelModel(
  analysis: Ai2Analysis,
  facts: DossierFact[],
  findings: DossierFinding[],
): ContextFindingsPanelModel {
  return {
    facts,
    findings,
        contextFindings: analysis.contextFindings.map((item, index) => {
      const row = recordValue(item)
      const metadata = recordValue(row.metadata)
      const relation = stringValue(metadata.relation, '')
      return {
        id: stringValue(
          row.context_finding_id ?? row.finding_id ?? row.id,
          `context-${index + 1}`,
        ),
        reasonCode: stringValue(
          row.reason_code ?? row.kind ?? row.code,
          'CONTEXT_REVIEW',
        ),
        subject: stringValue(
          row.subject ?? row.summary ?? row.reason ?? row.message,
          'AI2 yêu cầu kiểm tra thêm ngữ cảnh.',
        ),
        reviewState: stringValue(row.review_state ?? row.state, 'NEEDS_REVIEW'),
        relation,
      }
    }),
    evidenceIssues: analysis.evidenceIssues.map((item, index) => {
      const row = recordValue(item)
      return {
        code: stringValue(row.code ?? row.reason_code, `ISSUE_${index + 1}`),
        message: stringValue(
          row.message ?? row.detail ?? row.reason,
          'Citation/evidence cần được kiểm tra.',
        ),
      }
    }),
    coverage: analysis.coverage,
    trace: [],
    reviewState: analysis.reviewState,
  }
}

function EvidenceStatus({ evidence }: { evidence: StructuredEvidence }) {
  return (
    <span>
      {evidence.status}
      {evidence.citationId ? ` · ${evidence.citationId}` : ''}
    </span>
  )
}

function FactCard({
  fact,
  onOpenEvidence,
}: {
  fact: DossierFact
  onOpenEvidence?: DossierAnalysisPanelProps['onOpenEvidence']
}) {
  const canOpen = fact.evidence.status === 'LOCATABLE' && onOpenEvidence
  return (
    <article className="rounded border border-outline-variant/30 p-space-sm">
      <div className="flex items-center justify-between gap-space-xs">
        <span className="font-label-md text-label-md font-semibold text-on-surface">
          {fact.key || 'Fact chưa đặt tên'}
        </span>
        <span className="font-code-sm text-code-sm text-secondary">
          {Math.round(fact.confidence * 100)}% · {fact.reviewState}
        </span>
      </div>
      <p className="mt-space-xs font-body-md text-body-md text-on-surface">
        {valueText(fact.effectiveValue) || 'Chưa có giá trị'}
      </p>
      <div className="mt-space-xs flex items-center justify-between gap-space-xs font-body-sm text-body-sm text-secondary">
        <EvidenceStatus evidence={fact.evidence} />
        {canOpen ? (
          <button
            className="text-primary underline"
            type="button"
            onClick={() => onOpenEvidence(fact.evidence, fact.rawText)}
          >
            Mở nguồn
          </button>
        ) : null}
      </div>
      {fact.evidence.quote ? (
        <p className="mt-space-xs line-clamp-2 font-body-sm text-body-sm text-secondary">
          “{fact.evidence.quote}”
        </p>
      ) : null}
    </article>
  )
}

function FindingCard({
  finding,
  onOpenEvidence,
}: {
  finding: DossierFinding
  onOpenEvidence?: DossierAnalysisPanelProps['onOpenEvidence']
}) {
  return (
    <article className="rounded border border-outline-variant/30 p-space-sm">
      <div className="flex flex-wrap items-center gap-space-xs font-label-sm text-label-sm">
        <span className="font-semibold text-on-surface">
          {finding.topic || 'Nội dung cần kiểm tra'}
        </span>
        <span className="text-secondary">{finding.scope}</span>
        <span className="text-secondary">{finding.severity || '—'}</span>
      </div>
      <p className="mt-space-xs font-body-sm text-body-sm text-secondary">
        {finding.rationale || 'Không có diễn giải; cần kiểm tra nguồn.'}
      </p>
      {finding.sides.length > 0 ? (
        <div className="mt-space-sm grid gap-space-xs md:grid-cols-2">
          {finding.sides.map((side, index) => {
            const canOpen =
              side.evidence.status === 'LOCATABLE' && Boolean(onOpenEvidence)
            return (
              <div
                key={`${finding.id}-${side.documentId}-${index}`}
                className="rounded bg-surface-container-low p-space-xs font-body-sm text-body-sm"
              >
                <div className="flex justify-between gap-space-xs">
                  <span>{side.documentRole || side.side || 'Nguồn'}</span>
                  <EvidenceStatus evidence={side.evidence} />
                </div>
                <p className="mt-1">{valueText(side.valueSnapshot)}</p>
                {canOpen ? (
                  <button
                    className="mt-1 text-primary underline"
                    type="button"
                    onClick={() =>
                      onOpenEvidence(
                        side.evidence,
                        valueText(side.valueSnapshot),
                      )
                    }
                  >
                    Mở nguồn
                  </button>
                ) : null}
              </div>
            )
          })}
        </div>
      ) : (
        <p className="mt-space-sm text-secondary">
          Chưa có các phía đối chiếu.
        </p>
      )}
      {finding.disclaimer ? (
        <p className="mt-space-xs font-code-sm text-code-sm text-secondary">
          {finding.disclaimer}
        </p>
      ) : null}
    </article>
  )
}

export function DossierAnalysisPanel({
  dossierId,
  onOpenEvidence,
}: DossierAnalysisPanelProps) {
  const [reloadKey, setReloadKey] = useState(0)
  const [analysis, setAnalysis] = useState<Ai2Analysis | null>(null)
  const [facts, setFacts] = useState<DossierFact[]>([])
  const [findings, setFindings] = useState<DossierFinding[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!dossierId) {
      setAnalysis(null)
      setFacts([])
      setFindings([])
      setError(null)
      return
    }

    const controller = new AbortController()
    setAnalysis(null)
    setFacts([])
    setFindings([])
    setLoading(true)
    setError(null)
    void Promise.allSettled([
      getDossierAi2Analysis(dossierId, controller.signal),
      listDossierFacts(dossierId, controller.signal),
      listDossierFindings(dossierId, controller.signal),
    ])
      .then(([analysisResult, factsResult, findingsResult]) => {
        if (controller.signal.aborted) return
        if (analysisResult.status === 'fulfilled')
          setAnalysis(analysisResult.value)
        if (factsResult.status === 'fulfilled') setFacts(factsResult.value)
        if (findingsResult.status === 'fulfilled')
          setFindings(findingsResult.value)
        const errors = [analysisResult, factsResult, findingsResult]
          .filter(
            (result): result is PromiseRejectedResult =>
              result.status === 'rejected',
          )
          .map((result) =>
            result.reason instanceof Error
              ? result.reason.message
              : 'Không tải được facts/findings từ AI2.',
          )
        setError(errors.length > 0 ? errors.join(' ') : null)
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })

    return () => controller.abort()
  }, [dossierId, reloadKey])

  return (
    <section className="space-y-space-lg rounded-xl bg-surface-container-lowest p-space-lg shadow-sm">
      <div>
        <h2 className="font-headline-md text-headline-md text-on-surface">
          Phân tích AI2
        </h2>
        <button
          className="mt-space-xs inline-flex items-center rounded border border-outline-variant/40 px-space-sm py-space-xs font-label-sm text-label-sm text-primary hover:bg-surface-container-low disabled:cursor-not-allowed disabled:opacity-50"
          type="button"
          onClick={() => setReloadKey((value) => value + 1)}
          disabled={loading}
        >
          Tải lại phân tích
        </button>
        <p className="mt-space-xs font-body-sm text-body-sm text-secondary">
          Facts, findings và bằng chứng được lấy từ snapshot AI2 đã lưu. Mục nào
          thiếu citation định vị sẽ không được coi là nguồn đã xác minh.
        </p>
      </div>

      {loading ? (
        <p className="font-body-sm text-body-sm text-secondary">
          Đang tải facts và findings...
        </p>
      ) : null}
      {error ? (
        <p className="font-body-sm text-body-sm text-error" role="alert">
          {error}
        </p>
      ) : null}

      {analysis ? (
        <section className="space-y-space-sm rounded-lg border border-outline-variant/30 bg-surface-container-low p-space-md">
          <div className="flex flex-wrap items-center justify-between gap-space-sm">
            <div>
              <h3 className="font-title-sm text-title-sm font-semibold text-on-surface">
                Trạng thái phân tích AI2
              </h3>
              <p className="font-body-sm text-body-sm text-secondary">
                {analysis.available
                  ? `Run ${analysis.runId ?? 'không xác định'} · ${analysis.completenessState}`
                  : 'Chưa có AI2 projection được lưu cho hồ sơ này.'}
              </p>
            </div>
            <span
              className={`rounded px-space-xs py-0.5 font-code-sm text-code-sm ${analysis.evidenceReady ? 'bg-emerald-100 text-emerald-900' : 'bg-amber-100 text-amber-900'}`}
            >
              {analysis.evidenceReady ? 'EVIDENCE_READY' : analysis.reviewState}
            </span>
          </div>
          {analysis.available ? (
            <>
              <div className="grid gap-space-sm sm:grid-cols-3 lg:grid-cols-6">
                {[
                  ['Chunks', analysis.outputCounts.chunks],
                  ['Citations', analysis.outputCounts.citations],
                  ['Facts', analysis.outputCounts.facts],
                  ['Findings', analysis.outputCounts.findings],
                  ['Context', analysis.outputCounts.context_findings],
                  ['Evidence issues', analysis.evidenceIssueCount],
                ].map(([label, value]) => (
                  <div
                    key={String(label)}
                    className="rounded bg-surface-container-lowest p-space-sm"
                  >
                    <strong className="block font-code-sm text-code-sm text-primary">
                      {value ?? 0}
                    </strong>
                    <span className="font-body-sm text-body-sm text-secondary">
                      {label}
                    </span>
                  </div>
                ))}
              </div>
              {!analysis.evidenceReady ? (
                <p className="font-body-sm text-body-sm text-amber-900">
                  AI2 đã trả kết quả nhưng evidence chưa đủ để coi là đã xác
                  minh.
                  {analysis.reasonCode ? ` Lý do: ${analysis.reasonCode}.` : ''}
                </p>
              ) : null}
              <ContextFindingsPanel
                model={contextPanelModel(analysis, facts, findings)}
              />
            </>
          ) : null}
        </section>
      ) : null}

      <div>
        <h3 className="font-title-sm text-title-sm text-on-surface">
          Facts / fields ({facts.length})
        </h3>
        {facts.length === 0 ? (
          <p className="mt-space-xs font-body-sm text-body-sm text-secondary">
            Chưa có fact có cấu trúc cho hồ sơ này.
          </p>
        ) : (
          <div className="mt-space-sm grid gap-space-sm md:grid-cols-2">
            {facts.map((fact) => (
              <FactCard
                key={fact.id}
                fact={fact}
                onOpenEvidence={onOpenEvidence}
              />
            ))}
          </div>
        )}
      </div>

      <div>
        <h3 className="font-title-sm text-title-sm text-on-surface">
          Findings / risk ({findings.length})
        </h3>
        {findings.length === 0 ? (
          <p className="mt-space-xs font-body-sm text-body-sm text-secondary">
            {analysis?.available && analysis.outputCounts.findings === 0
              ? 'AI2 đã chạy nhưng không tạo finding so sánh/xung đột cho lần phân tích này. Nếu hồ sơ chỉ có một tài liệu, đây là trạng thái hợp lệ; context findings và evidence issues nằm ở phần trạng thái phía trên.'
              : 'Chưa có finding so sánh hoặc xung đột.'}
          </p>
        ) : (
          <div className="mt-space-sm space-y-space-sm">
            {findings.map((finding) => (
              <FindingCard
                key={finding.id}
                finding={finding}
                onOpenEvidence={onOpenEvidence}
              />
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
