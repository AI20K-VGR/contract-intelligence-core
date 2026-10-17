import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { AnalysisNotice } from '../src/components/AnalysisNotice'

describe('AnalysisNotice', () => {
  it('offers "Kiểm tra lại", not "Phân tích lại", when the analysis is stalled', () => {
    const html = renderToStaticMarkup(
      <AnalysisNotice
        stalled
        state="running"
        waitingFor="Hỏi đáp"
        onRecheck={() => {}}
        onRetry={() => {}}
      />,
    )
    expect(html).toContain('quá 10 phút')
    expect(html).toContain('Kiểm tra lại')
    expect(html).not.toContain('Phân tích lại')
  })

  it('says the previous result is shown when a re-run failed', () => {
    const html = renderToStaticMarkup(
      <AnalysisNotice
        showingPrevious
        errorCode="AI2_PROCESSING_FAILED"
        state="failed"
        waitingFor="Hỏi đáp"
        onRetry={() => {}}
      />,
    )
    expect(html).toContain('Lần phân tích mới bị lỗi')
    expect(html).toContain('Đang hiện kết quả của lần phân tích trước')
    expect(html).toContain('Phân tích lại')
    expect(html).not.toContain('chưa có')
  })

  it('still says the AI2 parts are missing when there is no previous result', () => {
    const html = renderToStaticMarkup(
      <AnalysisNotice
        errorCode="AI2_PROCESSING_FAILED"
        state="failed"
        waitingFor="Hỏi đáp"
      />,
    )
    expect(html).toContain('Hỏi đáp chưa có')
  })
})
