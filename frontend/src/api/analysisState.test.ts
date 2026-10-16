import { describe, expect, it } from 'vitest'
import { analysisState } from './structure'

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
})
