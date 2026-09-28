import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { normalizeAi2SearchResult } from '../src/api/ai2'
import {
  ContextFindingsPanel,
  type ContextFindingsPanelModel,
} from '../src/components/ContextFindingsPanel'
import {
  DynamicCitationViewer,
  normalizeCitationViewerModel,
} from '../src/components/DynamicCitationViewer'
import {
  FindingQueue,
  type FindingQueueEntry,
} from '../src/components/FindingQueue'

const DOSSIER_ID = 'dossier-vsf-ai2'

describe('AI2 review-fixes composition', () => {
  it('keeps BLOCKED state, context and evidence visible when the answer is present', () => {
    const result = normalizeAi2SearchResult(
      {
        state: 'BLOCKED',
        answer: 'A transport answer is not an approved answer.',
        connected: true,
        hits: [
          {
            text: 'Payment term is pending review.',
            source_file_id: 'document-vsf-body',
            document_role: 'CONTRACT',
            page_no: 1,
            line_id: 'line-citation-body',
          },
        ],
        context_findings: [
          {
            finding_id: 'context-party',
            reason: 'Context retained.',
            subject_key: 'seller',
            review_state: 'PASS',
          },
        ],
        evidence_issues: [
          { issue_id: 'evidence-gap-001', reason: 'Annex page needs review.' },
        ],
        coverage: { pages: 2, covered: 1, status: 'NEEDS_REVIEW' },
        reasoning_trace: [{ code: 'EVIDENCE_GAP' }],
      },
      DOSSIER_ID,
    )

    expect(result.reviewState).toBe('BLOCKED')
    expect(result.answer).toContain('transport answer')
    expect(result.hits[0].citation.status).toBe('LOCATABLE')
    expect(result.hits[0].citation.scope).toBe('body')

    const model: ContextFindingsPanelModel = {
      facts: [],
      findings: [],
      contextFindings: [
        {
          id: 'context-party',
          reasonCode: 'CONTEXT_RETAINED',
          subject: 'seller',
          reviewState: 'PASS',
        },
      ],
      evidenceIssues: [
        { code: 'evidence-gap-001', message: 'Annex page needs review.' },
      ],
      coverage: { pages: 2, covered: 1, status: 'NEEDS_REVIEW' },
      trace: [{ code: 'EVIDENCE_GAP' }],
      reviewState: result.reviewState,
    }
    const html = renderToStaticMarkup(<ContextFindingsPanel model={model} />)

    expect(html).toContain('BLOCKED')
    expect(html).toContain('0 facts')
    expect(html).toContain('0 findings')
    expect(html).toContain('CONTEXT_RETAINED')
    expect(html).toContain('evidence-gap-001')
    expect(html).toContain('EVIDENCE_GAP')
  })

  it('renders dynamic citation scope and finding evidence with review version', () => {
    const citation = normalizeCitationViewerModel(
      {
        dossier_id: DOSSIER_ID,
        document_id: 'document-vsf-annex',
        source_file_id: 'document-vsf-annex',
        citation_id: 'citation-annex',
        scope: 'annex',
        status: 'LOCATABLE',
        quote: 'Annex payment term.',
        page_no: 1,
        line_id: 'line-citation-annex',
        bbox: [1, 2, 30, 40],
        document_name: 'annex.pdf',
        document_role: 'ANNEX',
      },
      DOSSIER_ID,
    )
    expect(citation?.scope).toBe('annex')
    expect(citation?.status).toBe('LOCATABLE')

    const finding: FindingQueueEntry = {
      item: {
        id: 'review-finding-001',
        dossierId: DOSSIER_ID,
        runId: 'run-vsf-ai2-review',
        targetType: 'finding',
        targetId: 'finding-term-mismatch',
        reason: 'Body and annex terms differ.',
        priority: 'P1',
        status: 'open',
        version: 2,
        sourceTraceId: 'trace-vsf-ai2',
        sourceObservationId: null,
        targetSnapshot: null,
        createdAt: '2026-09-25T00:00:00Z',
      },
      severity: 'HIGH',
      topic: 'Payment term',
      leftEvidence: 'Body: 30 days',
      rightEvidence: 'Annex: 15 days',
      revisions: [],
    }

    const citationHtml = renderToStaticMarkup(
      <DynamicCitationViewer citation={citation} />,
    )
    const findingHtml = renderToStaticMarkup(
      <FindingQueue
        entries={[finding]}
        onAction={async () => undefined}
        onReload={async () => undefined}
      />,
    )

    expect(citationHtml).toContain('data-citation-status="LOCATABLE"')
    expect(citationHtml).toContain('annex.pdf')
    expect(citationHtml).toContain('citation-annex')
    expect(findingHtml).toContain('Body: 30 days')
    expect(findingHtml).toContain('Annex: 15 days')
    expect(findingHtml).toContain('base_version: 2')
  })
})
