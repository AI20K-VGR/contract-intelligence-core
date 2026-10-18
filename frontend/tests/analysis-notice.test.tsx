import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { AnalysisNotice } from '../src/components/AnalysisNotice'

const RETRY_BUTTON = '>Chạy lại</button>'

describe('AnalysisNotice', () => {
  it('offers "Kiểm tra lại", not "Chạy lại", when the analysis is stalled', () => {
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
    expect(html).toContain('sẽ tự mở khi')
    expect(html).toContain('Kiểm tra lại')
    expect(html).not.toContain(RETRY_BUTTON)
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
    expect(html).toContain(
      'Đồ thị và hỏi đáp đang dùng kết quả của lần phân tích trước',
    )
    expect(html).toContain('xung đột cần phân tích lại')
    expect(html).toContain(RETRY_BUTTON)
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

  it('says a cancelled analysis was cancelled and offers one "Chạy lại"', () => {
    const html = renderToStaticMarkup(
      <AnalysisNotice
        errorCode="RUN_CANCELLED"
        state="cancelled"
        waitingFor="Hỏi đáp"
        onRetry={() => {}}
      />,
    )
    expect(html).toContain('Đã huỷ lần phân tích.')
    expect(html).toContain('Hỏi đáp chưa có')
    expect(html).toContain(RETRY_BUTTON)
  })

  it('offers "Chạy lại" for an AI2 code it does not know', () => {
    const html = renderToStaticMarkup(
      <AnalysisNotice
        errorCode="INSUFFICIENT_PAGES"
        state="failed"
        waitingFor="Hỏi đáp"
        onRetry={() => {}}
      />,
    )
    expect(html).toContain(RETRY_BUTTON)
    expect(html).not.toContain('INSUFFICIENT_PAGES')
  })

  it('has no "Chạy lại" for a dossier of the wrong shape (DOSSIER_*)', () => {
    const html = renderToStaticMarkup(
      <AnalysisNotice
        errorCode="DOSSIER_CONTRACT_REQUIRED"
        state="failed"
        waitingFor="Hỏi đáp"
        onRetry={() => {}}
      />,
    )
    expect(html).toContain('Hồ sơ cần đúng một hợp đồng')
    expect(html).not.toContain(RETRY_BUTTON)
  })

  it('shows no button to someone who may not run it again', () => {
    const html = renderToStaticMarkup(
      <AnalysisNotice
        errorCode="AI2_TIMEOUT"
        state="failed"
        waitingFor="Hỏi đáp"
      />,
    )
    expect(html).not.toContain(RETRY_BUTTON)
  })
})

describe('AnalysisNotice cancel (PR #122 review)', () => {
  it('offers "Huỷ phân tích" while running and while stalled', () => {
    for (const stalled of [false, true]) {
      const html = renderToStaticMarkup(
        <AnalysisNotice
          stalled={stalled}
          state="running"
          waitingFor="Hỏi đáp"
          onCancel={() => {}}
          onRecheck={() => {}}
        />,
      )
      expect(html).toContain('Huỷ phân tích')
    }
  })

  it('has no cancel button once stopped or without the right', () => {
    expect(
      renderToStaticMarkup(
        <AnalysisNotice
          errorCode="AI2_TIMEOUT"
          state="failed"
          waitingFor="Hỏi đáp"
          onCancel={() => {}}
        />,
      ),
    ).not.toContain('Huỷ phân tích')
    expect(
      renderToStaticMarkup(
        <AnalysisNotice state="running" waitingFor="Hỏi đáp" />,
      ),
    ).not.toContain('Huỷ phân tích')
  })
})
