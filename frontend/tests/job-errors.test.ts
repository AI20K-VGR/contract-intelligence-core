import { describe, expect, it } from 'vitest'
import { normalizeAi2SearchResult } from '../src/api/ai2'
import {
  analysisRetryKind,
  isAi2Failure,
  isCancelledJob,
  jobErrorInfo,
} from '../src/api/jobErrors'

describe('analysisRetryKind (một nút "Chạy lại")', () => {
  it('chỉ phân tích lại với lỗi tạm của AI2', () => {
    expect(analysisRetryKind('failed', 'AI2_PROCESSING_FAILED')).toBe('ai2')
    expect(analysisRetryKind('failed', 'AI2_TIMEOUT')).toBe('ai2')
  })

  it('chạy tiếp, giữ phần OCR đã đọc, khi phân tích bị huỷ', () => {
    expect(analysisRetryKind('cancelled', 'RUN_CANCELLED')).toBe('resume')
  })

  it('chạy lại toàn bộ với lỗi AI2 khác', () => {
    expect(analysisRetryKind('failed', 'AI2_BLOCKED')).toBe('reprocess')
    expect(analysisRetryKind('failed', 'AI2_UNAVAILABLE')).toBe('reprocess')
    expect(analysisRetryKind('failed', 'INSUFFICIENT_PAGES')).toBe('reprocess')
  })

  it('không có nút với hồ sơ sai cấu trúc, hay khi chưa dừng', () => {
    expect(analysisRetryKind('failed', 'DOSSIER_CONTRACT_REQUIRED')).toBe(
      'none',
    )
    expect(analysisRetryKind('failed', 'DOSSIER_TOO_MANY_DOCUMENTS')).toBe(
      'none',
    )
    expect(analysisRetryKind('running', null)).toBe('none')
    expect(analysisRetryKind('done', null)).toBe('none')
  })

  it('giải thích hồ sơ sai cấu trúc bằng câu tiếng Việt, không hiện mã', () => {
    const info = jobErrorInfo('DOSSIER_SOMETHING_NEW')
    expect(info.retry).toBe('none')
    expect(info.message).toContain('không đúng cấu trúc')
  })
})

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

  it('explains AI1_NO_READABLE_PAGE and offers the OCR retry', () => {
    const info = jobErrorInfo('AI1_NO_READABLE_PAGE')
    expect(info.retry).toBe('ocr')
    expect(info.message).toContain('không đọc được trang nào')
    // S2, S3, S8 failed and nothing reached AI2: an OCR failure, not AI2.
    expect(
      isAi2Failure('AI1_NO_READABLE_PAGE', {
        S2: { status: 'failed' },
        S3: { status: 'failed' },
        S8: { status: 'failed' },
      }),
    ).toBe(false)
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
    expect(isAi2Failure('AI2_BLOCKED')).toBe(true)
    expect(isAi2Failure('DOSSIER_CONTRACT_NOT_UNIQUE')).toBe(true)
  })

  it('treats a job that failed after OCR finished as an AI2 failure', () => {
    // AI2 returns its own errors[0].code, so no code list can cover it.
    expect(isAi2Failure('SOME_AI2_CODE', { S8: { status: 'succeeded' } })).toBe(
      true,
    )
    expect(isAi2Failure(null, { S4: { status: 'failed' } })).toBe(true)
  })

  it('keeps OCR failures as OCR failures', () => {
    expect(isAi2Failure('DISPATCH_FAILED')).toBe(false)
    expect(isAi2Failure(null)).toBe(false)
    expect(isAi2Failure(undefined)).toBe(false)
    expect(
      isAi2Failure('DISPATCH_FAILED', {
        S2: { status: 'succeeded' },
        S8: { status: 'running' },
      }),
    ).toBe(false)
  })
})

describe('isCancelledJob', () => {
  it('recognises a cancelled job by status or by RUN_CANCELLED', () => {
    expect(isCancelledJob('cancelled', null)).toBe(true)
    expect(isCancelledJob('failed', 'RUN_CANCELLED')).toBe(true)
    expect(isCancelledJob('failed', 'AI2_TIMEOUT')).toBe(false)
    expect(isCancelledJob(null, undefined)).toBe(false)
  })
})
