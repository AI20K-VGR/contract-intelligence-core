import { describe, expect, it } from 'vitest'
import { analysisState, needsStepStatuses } from './structure'

const OCR_DONE = {
  S2: { status: 'succeeded' },
  S3: { status: 'succeeded' },
  S8: { status: 'succeeded' },
}

describe('analysisState', () => {
  it('chưa có trạng thái phân tích khi OCR chưa xong', () => {
    expect(analysisState('uploaded', null)).toBeNull()
    expect(analysisState('processing', null)).toBeNull()
  })

  it('job đứng ở extracted là AI2 đang chạy', () => {
    expect(analysisState('extracted', null)).toBe('running')
  })

  it('job tới bước rà soát là AI2 đã xong', () => {
    expect(analysisState('pending_review', null)).toBe('done')
    expect(analysisState('approved', null)).toBe('done')
  })

  it('chỉ coi là lỗi phân tích khi mã lỗi thuộc AI2', () => {
    expect(analysisState('failed', 'AI2_TIMEOUT')).toBe('failed')
    expect(analysisState('failed', 'OCR_FAILED')).toBeNull()
    expect(analysisState('failed', null)).toBeNull()
  })

  it('mã AI2 lạ vẫn là lỗi phân tích khi OCR đã xong (S8 xong)', () => {
    // Cùng kết luận với trang tiến trình (isAi2Failure xét các bước).
    expect(analysisState('failed', 'INSUFFICIENT_PAGES', OCR_DONE)).toBe(
      'failed',
    )
    expect(analysisState('failed', 'INSUFFICIENT_PAGES')).toBeNull()
  })

  it('bước AI2 lỗi (S4) là lỗi phân tích dù mã lỗi là gì', () => {
    expect(analysisState('failed', null, { S4: { status: 'failed' } })).toBe(
      'failed',
    )
  })

  it('huỷ khi AI2 đang chạy là đã huỷ phân tích; huỷ lúc OCR thì không', () => {
    expect(analysisState('failed', 'RUN_CANCELLED', OCR_DONE)).toBe('cancelled')
    expect(analysisState('cancelled', null, OCR_DONE)).toBe('cancelled')
    expect(
      analysisState('failed', 'RUN_CANCELLED', { S2: { status: 'running' } }),
    ).toBeNull()
  })

  it('hồ sơ sai cấu trúc (DOSSIER_*) là lỗi phân tích', () => {
    expect(analysisState('failed', 'DOSSIER_CONTRACT_REQUIRED')).toBe('failed')
  })

  it('chỉ cần tải các bước khi job đã dừng', () => {
    expect(needsStepStatuses('failed')).toBe(true)
    expect(needsStepStatuses('cancelled')).toBe(true)
    expect(needsStepStatuses('extracted')).toBe(false)
    expect(needsStepStatuses('pending_review')).toBe(false)
  })
})
