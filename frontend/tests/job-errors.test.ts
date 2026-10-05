import { describe, expect, it } from 'vitest'
import { normalizeAi2SearchResult } from '../src/api/ai2'
import { isAi2Failure, jobErrorInfo } from '../src/api/jobErrors'

describe('jobErrorInfo', () => {
  it('routes AI2 retryable codes to the AI2 retry', () => {
    expect(jobErrorInfo('AI2_TIMEOUT').retry).toBe('ai2')
    expect(jobErrorInfo('AI2_PROCESSING_FAILED').retry).toBe('ai2')
  })

  it('does not offer a retry for permanent errors', () => {
    expect(jobErrorInfo('DOSSIER_TOO_MANY_DOCUMENTS').retry).toBe('none')
    expect(jobErrorInfo('dossier_deleted').retry).toBe('none')
  })

  it('tells the user a cancelled run can resume through the OCR retry', () => {
    const info = jobErrorInfo('RUN_CANCELLED')
    expect(info.retry).toBe('ocr')
    expect(info.message).toContain('hủy')
  })

  it('falls back to the OCR retry for a missing or unknown code', () => {
    expect(jobErrorInfo(null).retry).toBe('ocr')
    expect(jobErrorInfo('SOMETHING_NEW').retry).toBe('ocr')
  })
})

describe('citation validation fields', () => {
  it('keeps UNVERIFIED, table_id and cell_id from the hit', () => {
    const result = normalizeAi2SearchResult(
      {
        hits: [
          {
            text: 'Ô phụ lục',
            citation: {
              source_file_id: 'doc_1',
              line_id: 'l1',
              validation_status: 'UNVERIFIED',
              table_id: 'tbl_1',
              cell_id: 'c_2',
            },
          },
        ],
      },
      'dos_1',
    )
    const citation = result.hits[0].citation
    expect(citation.unverified).toBe(true)
    expect(citation.tableId).toBe('tbl_1')
    expect(citation.cellId).toBe('c_2')
  })
})

describe('isAi2Failure', () => {
  it('flags AI2 error codes so the page does not say OCR failed', () => {
    expect(isAi2Failure('AI2_PROCESSING_FAILED')).toBe(true)
    expect(isAi2Failure('AI2_TIMEOUT')).toBe(true)
    expect(isAi2Failure(' AI2_UNAVAILABLE ')).toBe(true)
  })

  it('leaves OCR, cancelled and missing codes alone', () => {
    expect(isAi2Failure('DISPATCH_FAILED')).toBe(false)
    expect(isAi2Failure('RUN_CANCELLED')).toBe(false)
    expect(isAi2Failure(null)).toBe(false)
    expect(isAi2Failure(undefined)).toBe(false)
  })
})
