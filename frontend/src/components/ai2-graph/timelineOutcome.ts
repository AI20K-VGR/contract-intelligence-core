import type { ProcessingTrace } from '../../api/contractGraph'

export function processingTimelineOutcome(trace: ProcessingTrace) {
  if (trace.job_status === 'FAILED') return 'job-failed'
  if (trace.job_status === 'CANCELLED') return 'job-cancelled'
  if (trace.job_status === 'QUEUED' || trace.job_status === 'RUNNING') {
    return 'job-running'
  }
  const hasFailedStage = trace.stages.some((stage) => stage.status === 'FAILED')
  if (trace.job_status === 'SUCCEEDED' && hasFailedStage) {
    return 'job-succeeded-with-stage-failure'
  }
  if (hasFailedStage) return 'stage-failed-job-unknown'
  if (trace.job_status === 'SUCCEEDED') return 'job-succeeded'
  return trace.status
}

/**
 * Câu giải thích cho người dùng theo mã trạng thái của bước (AI2 idp.py,
 * pair_builder.gate). Mã lạ thì không hiện gì; mã gốc chỉ ghi ra Console.
 */
export function stageReasonText(code: string | null): string | null {
  if (!code) return null
  const ruleOnly =
    'nên hệ thống chỉ dùng quy tắc có sẵn để tìm quan hệ. Kết quả có thể thiếu một số quan hệ.'
  switch (code) {
    case 'RULE_ONLY_NO_CONSENT':
      return `Hồ sơ chưa cho phép AI đọc nội dung, ${ruleOnly} Bật "Cho phép AI phân tích nội dung hồ sơ" rồi phân tích lại để có kết quả đầy đủ hơn.`
    case 'RULE_ONLY_EGRESS_DENIED':
      return `Chính sách hệ thống không cho gửi nội dung tới dịch vụ AI, ${ruleOnly}`
    case 'RULE_ONLY_LLM_UNAVAILABLE':
    case 'RULE_ONLY_MODEL_UNSET':
      return `Dịch vụ AI tạm thời chưa sẵn sàng, ${ruleOnly}`
    case 'RULE_ONLY_BUDGET_EXHAUSTED':
      return `Đã dùng hết hạn mức AI cho lần phân tích này, ${ruleOnly}`
    case 'RULE_ONLY_DEADLINE':
      return `Hết thời gian dành cho AI ở lần phân tích này, ${ruleOnly}`
    case 'RULE_ONLY':
      return `AI không tham gia bước này, ${ruleOnly}`
    case 'GRAPH_BUILD_FAILED':
    case 'PAIR_BUILD_FAILED':
      return 'Bước này gặp lỗi nên chưa có kết quả. Bạn có thể chạy lại phân tích.'
    case 'SKIPPED_GRAPH_FAILED':
      return 'Bỏ qua vì bước trước bị lỗi.'
    case 'TERMINAL_WITH_OPEN_STAGE':
      return 'Phân tích đã dừng nhưng bước này chưa ghi nhận kết thúc.'
    default:
      return null
  }
}
