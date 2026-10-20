import { useEffect, useState } from 'react'
import {
  fetchSemanticSource,
  getSemanticResults,
  type SemanticEvidence,
  type SemanticResults,
  type SemanticSlot,
} from '../api/semanticResults'
import {
  certaintyLabel,
  conflictKindLabel,
  dateRoleLabel,
  dispositionLabel,
  familyLabel,
  isSystemCode,
  issueLabel,
  linesLabel,
  relationLabel,
  reviewStateLabel,
  slotStateLabel,
  tableCellLabel,
  validationLabel,
} from '../structure/displayLabels'
import { TechnicalDetail } from './TechnicalDetail'
import { userErrorMessage } from '../api/errorMessage'

const OUTPUT_LABELS: Record<string, string> = {
  rows: 'Điều khoản',
  pairs: 'Cặp nghi vấn',
  timeline: 'Dòng thời gian',
}

/** Câu chữ thì giữ; mã hệ thống thì dịch, không hiện nguyên văn. */
function readable(text: unknown) {
  const value = String(text ?? '').trim()
  return isSystemCode(value) ? issueLabel(value) : value
}

const SLOT_LABELS: Record<string, string> = {
  actor: 'Bên thực hiện',
  beneficiary: 'Bên hưởng quyền',
  action: 'Hành động',
  qualifier: 'Loại vi phạm',
  modality_negation: 'Quyền/nghĩa vụ/phủ định',
  object_scope: 'Phạm vi',
  condition: 'Điều kiện',
  exception: 'Ngoại lệ',
  temporal_trigger: 'Mốc kích hoạt',
  deadline: 'Hạn',
  amount: 'Giá trị',
  currency: 'Tiền tệ',
  unit: 'Đơn vị',
  base: 'Cơ sở',
  period: 'Kỳ',
  parameter: 'Tham số',
  definition: 'Định nghĩa',
}

function Source({ source }: { source: SemanticEvidence }) {
  const [url, setUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  useEffect(
    () => () => {
      if (url) URL.revokeObjectURL(url)
    },
    [url],
  )
  async function open() {
    setLoading(true)
    setError(null)
    try {
      setUrl(URL.createObjectURL(await fetchSemanticSource(source)))
    } catch (cause) {
      setError(userErrorMessage(cause, 'Không tải được nguồn.'))
    } finally {
      setLoading(false)
    }
  }
  return (
    <div className="min-w-0 rounded border border-outline-variant/40 p-2">
      <TechnicalDetail
        text={`${source.document_id} · ${source.snapshot_id} · ${source.source_ref}`}
      />
      <blockquote className="whitespace-pre-wrap">{source.raw}</blockquote>
      <p>
        {[
          source.citation.page
            ? `Trang ${source.citation.page}`
            : 'Chưa rõ trang',
          linesLabel(source.citation.line_ids),
        ]
          .filter(Boolean)
          .join(', ')}
      </p>
      <p>{validationLabel(source.citation.validation_status)}</p>
      <button
        type="button"
        onClick={() => void open()}
        disabled={
          loading ||
          source.citation.validation_status !== 'VALID' ||
          !source.citation.page
        }
        className="rounded border px-2 py-1 disabled:opacity-50"
      >
        {loading ? 'Đang mở nguồn…' : 'Mở nguồn đã xác minh'}
      </button>
      {url ? (
        <a
          href={url}
          target="_blank"
          rel="noreferrer"
          className="ml-2 underline"
        >
          Xem trang nguồn
        </a>
      ) : null}
      {error ? <p role="alert">{error}</p> : null}
    </div>
  )
}
function Slot({ name, value }: { name: string; value: SemanticSlot }) {
  return (
    <div>
      <dt className="font-semibold">{SLOT_LABELS[name] ?? name}</dt>
      <dd className="break-words">
        {value.value ?? 'Chưa xác định'} · {slotStateLabel(value.state)}
        <TechnicalDetail text={value.reason} />
      </dd>
      <details>
        <summary>Nguồn của giá trị</summary>
        {value.evidence.map((e, i) => (
          <Source key={`${e.source_ref}-${i}`} source={e} />
        ))}
      </details>
    </div>
  )
}
export function ClauseFrameResults({
  dossierId,
  initial,
  expectedRun,
}: {
  dossierId: string
  initial?: SemanticResults
  expectedRun?: string
}) {
  const [model, setModel] = useState<SemanticResults | null>(initial ?? null)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState('ALL')
  useEffect(() => {
    if (initial) {
      setModel(initial)
      return
    }
    const controller = new AbortController()
    setModel(null)
    setError(null)
    getSemanticResults(dossierId, controller.signal, expectedRun)
      .then((next) => {
        if (!controller.signal.aborted) setModel(next)
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted)
          setError(userErrorMessage(cause, 'Không đọc được kết quả.'))
      })
    return () => controller.abort()
  }, [dossierId, initial, expectedRun])
  if (error) return <p role="alert">{error}</p>
  if (!model) return <p role="status">Đang tải kết quả điều khoản…</p>
  if (model.dossierId !== dossierId)
    return <p role="alert">Kết quả thuộc hồ sơ khác, hãy tải lại.</p>
  if (expectedRun && model.runId !== expectedRun)
    return (
      <p role="alert">Lần chạy đã đổi. Tải lại hồ sơ trước khi thẩm định.</p>
    )
  const extension = model.extension
  const typedTableProjections = model.typedTableProjections ?? {
    payment_schedules: [],
    boq_checks: [],
  }
  return (
    <section
      aria-label="Kết quả điều khoản"
      className="max-w-full space-y-3 rounded border border-outline-variant/40 bg-surface-container-lowest p-3 text-sm"
    >
      <p>Trạng thái: {reviewStateLabel(model.state)}</p>
      <TechnicalDetail
        text={`Lần chạy ${model.runId ?? '—'} · ${model.state} · ${model.reason ?? ''}`}
      />
      {!extension ? (
        <p>
          Ba đầu ra chưa được đo cho lần chạy này. Không có kết luận từ việc
          thiếu dữ liệu.
        </p>
      ) : (
        <>
          <TechnicalDetail
            text={`Profile ${extension.profile_digest} · Alias v${extension.alias_version} · ${extension.alias_digest ?? '—'}`}
          />
          <nav
            aria-label="Ba đầu ra điều khoản"
            className="flex flex-wrap gap-3"
          >
            <a href="#semantic-rows" className="underline">
              Điều khoản
            </a>
            <a href="#semantic-pairs" className="underline">
              Cặp nghi vấn
            </a>
            <a href="#semantic-timeline" className="underline">
              Dòng thời gian
            </a>
          </nav>
          <details>
            <summary>
              Mức độ phân tích · {reviewStateLabel(extension.coverage.state)}
            </summary>
            <p>
              Đã xét {extension.coverage.attempted_nodes} điều khoản · Khung{' '}
              {extension.coverage.frames} · Có căn cứ{' '}
              {extension.coverage.grounded_slots} · Chưa xác định{' '}
              {extension.coverage.unresolved_slots} · Căn cứ không hợp lệ{' '}
              {extension.coverage.invalid_evidence} · Lượt tra ngữ cảnh{' '}
              {extension.coverage.context_calls}
            </p>
            <TechnicalDetail text={extension.coverage.reasons.join('; ')} />
            {(
              [
                [
                  'Theo loại điều khoản',
                  extension.coverage.by_family,
                  familyLabel,
                ],
                [
                  'Theo trường dữ liệu',
                  extension.coverage.by_slot,
                  (name: string) => SLOT_LABELS[name] ?? 'Trường khác',
                ],
                [
                  'Theo kết quả',
                  extension.coverage.by_output,
                  (name: string) => OUTPUT_LABELS[name] ?? 'Kết quả khác',
                ],
              ] as const
            ).map(([label, groups, nameOf]) => (
              <div key={label}>
                <h3>{label}</h3>
                {Object.entries(groups).map(([name, count]) => (
                  <p key={name}>
                    {nameOf(name)}: đã xét {count.attempted} · có kết quả{' '}
                    {count.covered} · cần rà soát {count.review} · còn thiếu{' '}
                    {count.missing}
                  </p>
                ))}
              </div>
            ))}
          </details>
          {typedTableProjections.payment_schedules.length ||
          typedTableProjections.boq_checks.length ? (
            <section
              id="typed-table-projections"
              aria-label="Kết quả bảng định lượng"
              className="rounded border p-2"
            >
              <h2 className="font-semibold">Kiểm tra bảng định lượng</h2>
              {typedTableProjections.payment_schedules.map(
                (projection, index) => (
                  <article
                    key={`payment-${index}`}
                    className="my-2 rounded border p-2"
                  >
                    <h3>
                      Lịch thanh toán ·{' '}
                      {reviewStateLabel(
                        String(projection.review_state ?? 'NEEDS_REVIEW'),
                      )}
                    </h3>
                    <p>
                      {tableCellLabel(String(projection.table_id ?? ''), null)}{' '}
                      · Tổng tỷ lệ{' '}
                      {projection.total_percent != null
                        ? `${String(projection.total_percent)}%`
                        : 'chưa đủ dữ liệu'}
                    </p>
                    {Array.isArray(projection.issues) &&
                      projection.issues.map((issue, issueIndex) => (
                        <p key={issueIndex}>{readable(issue)}</p>
                      ))}
                    <p>
                      Phạm vi:{' '}
                      {readable(
                        (
                          projection.coverage as
                            Record<string, unknown> | undefined
                        )?.reason ?? 'Đã đọc theo phạm vi nguồn',
                      )}
                    </p>
                  </article>
                ),
              )}
              {typedTableProjections.boq_checks.map((projection, index) => (
                <article
                  key={`boq-${index}`}
                  className="my-2 rounded border p-2"
                >
                  <h3>
                    Kiểm tra số học bảng khối lượng ·{' '}
                    {reviewStateLabel(
                      String(projection.review_state ?? 'NEEDS_REVIEW'),
                    )}
                  </h3>
                  <p>
                    {tableCellLabel(String(projection.table_id ?? ''), null)} ·
                    Tổng cộng {String(projection.grand_total ?? 'chưa rõ')}
                  </p>
                  {Array.isArray(projection.issues) &&
                    projection.issues.map((issue, issueIndex) => (
                      <p key={issueIndex}>{readable(issue)}</p>
                    ))}
                  <p>
                    Phạm vi:{' '}
                    {readable(
                      (
                        projection.coverage as
                          Record<string, unknown> | undefined
                      )?.reason ?? 'Đã đọc theo phạm vi nguồn',
                    )}
                  </p>
                </article>
              ))}
            </section>
          ) : null}
          <section id="semantic-rows">
            <h2 className="font-semibold">Điều khoản</h2>
            <div className="grid gap-2 md:grid-cols-2">
              {extension.rows.map((id) => {
                const frame = extension.frames.find((f) => f.frame_id === id)!
                return (
                  <article key={id} className="min-w-0 rounded border p-2">
                    <h3>{familyLabel(frame.family)}</h3>
                    <p>{certaintyLabel(frame.key.certainty)}</p>
                    <TechnicalDetail
                      text={`${frame.frame_id} · ${frame.profile} · ${frame.key.method} · ${frame.key.reason}`}
                    />
                    <dl className="space-y-2">
                      {Object.entries(frame.slots).map(([name, value]) => (
                        <Slot key={name} name={name} value={value} />
                      ))}
                    </dl>
                    <details>
                      <summary>Nguồn điều khoản</summary>
                      {frame.evidence.map((e, i) => (
                        <Source key={i} source={e} />
                      ))}
                    </details>
                  </article>
                )
              })}
            </div>
          </section>
          <section id="semantic-pairs">
            <h2 className="font-semibold">Cặp nghi vấn</h2>
            <label>
              Lọc trạng thái{' '}
              <select
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
              >
                <option value="ALL">Tất cả</option>
                {Array.from(
                  new Set(extension.pairs.map((p) => p.disposition)),
                ).map((d) => (
                  <option key={d} value={d}>
                    {dispositionLabel(d)}
                  </option>
                ))}
              </select>
            </label>
            {extension.pairs
              .filter((p) => filter === 'ALL' || p.disposition === filter)
              .map((p) => (
                <article key={p.pair_id} className="my-2 rounded border p-2">
                  <h3>
                    {dispositionLabel(p.disposition)} ·{' '}
                    {reviewStateLabel(p.review_state)}
                  </h3>
                  <TechnicalDetail
                    text={`${p.reason} · ${p.method} · ${p.candidate_sources.join(', ')}`}
                  />
                  {p.conflict_kind ||
                  p.alignment_key?.length ||
                  p.slots_in_difference?.length ? (
                    <p>
                      Loại: {conflictKindLabel(p.conflict_kind)} · Khác nhau ở:{' '}
                      {p.slots_in_difference
                        ?.map((slot) => SLOT_LABELS[slot] ?? 'trường khác')
                        .join(', ') || 'chưa rõ'}
                    </p>
                  ) : null}
                  <div className="grid gap-2 md:grid-cols-2">
                    <div aria-label="Nguồn bên trái">
                      {p.left_evidence.map((e, i) => (
                        <Source key={i} source={e} />
                      ))}
                    </div>
                    <div aria-label="Nguồn bên phải">
                      {p.right_evidence.map((e, i) => (
                        <Source key={i} source={e} />
                      ))}
                    </div>
                  </div>
                </article>
              ))}
            {!extension.pairs.length ? (
              <p>Chưa có cặp nào; xem phần Mức độ phân tích.</p>
            ) : null}
          </section>
          <section id="semantic-timeline">
            <h2 className="font-semibold">Dòng thời gian</h2>
            {extension.timeline.map((edge) => (
              <article key={edge.edge_id} className="my-2 rounded border p-2">
                <h3>
                  {relationLabel(edge.relation)} ·{' '}
                  {reviewStateLabel(edge.review_state)}
                </h3>
                <p>
                  {dateRoleLabel(edge.date_role)}:{' '}
                  {edge.date_value ?? 'chưa xác định'}
                </p>
                <TechnicalDetail
                  text={`${edge.source_id} → ${edge.target_id ?? '—'} · ${edge.reasons.join('; ')}`}
                />
                {edge.acceptance ? (
                  <dl>
                    <Slot name="acceptance" value={edge.acceptance} />
                  </dl>
                ) : (
                  <p>Chấp thuận: chưa rõ</p>
                )}
                {edge.proposed_value ? (
                  <dl>
                    <Slot
                      name={edge.value_slot ?? 'proposed_value'}
                      value={edge.proposed_value}
                    />
                  </dl>
                ) : (
                  <p>Chưa đủ chứng cứ cho giá trị đề xuất.</p>
                )}
                {edge.evidence.map((e, i) => (
                  <Source key={i} source={e} />
                ))}
              </article>
            ))}
            {!extension.timeline.length ? (
              <p>Chưa dựng được dòng thời gian; xem phần Mức độ phân tích.</p>
            ) : null}
          </section>
          {extension.alias_drafts.length ? (
            <details>
              <summary>Tên gọi khác đang chờ chuyên viên duyệt</summary>
              {extension.alias_drafts.map((a, i) => (
                <p key={i}>
                  {a.source} → {a.symbol} ·{' '}
                  {a.kind === 'action' ? 'Hành động' : 'Loại vi phạm'} · Bản
                  nháp
                </p>
              ))}
            </details>
          ) : null}
        </>
      )}
      <p>
        Giữ nghi vấn để người duyệt kiểm tra. Thẩm định không tự thay quy tắc
        tên gọi khác hoặc lịch sử lần chạy.
      </p>
    </section>
  )
}
