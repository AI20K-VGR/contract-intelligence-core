import { useEffect, useState } from 'react'
import {
  fetchSemanticSource,
  getSemanticResults,
  type SemanticEvidence,
  type SemanticResults,
  type SemanticSlot,
} from '../api/semanticResults'

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
      setError(cause instanceof Error ? cause.message : 'Không tải được nguồn.')
    } finally {
      setLoading(false)
    }
  }
  return (
    <div className="min-w-0 rounded border border-outline-variant/40 p-2">
      <p className="break-all">
        {source.document_id} · {source.snapshot_id} · {source.source_ref}
      </p>
      <blockquote className="whitespace-pre-wrap">{source.raw}</blockquote>
      <p>
        Trang {source.citation.page ?? 'UNKNOWN'} ·{' '}
        {source.citation.line_ids.join(', ')} · ký tự{' '}
        {source.citation.char_start ?? '?'}–{source.citation.char_end ?? '?'}
      </p>
      <p>{source.citation.validation_status}</p>
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
        {value.value ?? 'Chưa xác định'} · {value.value_type} · {value.state}
        {value.reason ? ` · ${value.reason}` : ''}
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
          setError(
            cause instanceof Error ? cause.message : 'Không đọc được kết quả.',
          )
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
  const typedTableProjections = model.typedTableProjections ?? { payment_schedules: [], boq_checks: [] }
  return (
    <section
      aria-label="Kết quả điều khoản AI2"
      className="max-w-full space-y-3 rounded border border-outline-variant/40 bg-surface-container-lowest p-3 text-sm"
    >
      <p className="break-all">
        Lần chạy: {model.runId ?? 'Chưa có'} · {model.state} · {model.reason}
      </p>
      {!extension ? (
        <p>
          Ba đầu ra chưa được đo cho lần chạy này. Không có kết luận từ việc
          thiếu dữ liệu.
        </p>
      ) : (
        <>
          <p className="break-all">
            Profile {extension.profile_digest} · Alias v
            {extension.alias_version} ·{' '}
            {extension.alias_digest ?? 'Chưa có alias'}
          </p>
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
            <summary>Coverage · {extension.coverage.state}</summary>
            <p>
              Attempted {extension.coverage.attempted_nodes} · Frames{' '}
              {extension.coverage.frames} · Grounded{' '}
              {extension.coverage.grounded_slots} · Unresolved{' '}
              {extension.coverage.unresolved_slots} · Invalid evidence{' '}
              {extension.coverage.invalid_evidence} · Context calls{' '}
              {extension.coverage.context_calls}
            </p>
            <p>{extension.coverage.reasons.join('; ')}</p>
            {[
              ['Family', extension.coverage.by_family],
              ['Slot', extension.coverage.by_slot],
              ['Output', extension.coverage.by_output],
            ].map(([label, groups]) => (
              <div key={String(label)}>
                <h3>{String(label)}</h3>
                {Object.entries(groups).map(([name, count]) => (
                  <p key={name}>
                    {name}: attempted {count.attempted} / covered{' '}
                    {count.covered} / review {count.review} / missing{' '}
                    {count.missing}
                  </p>
                ))}
              </div>
            ))}
          </details>
          {(typedTableProjections.payment_schedules.length || typedTableProjections.boq_checks.length) ? (
            <section id="typed-table-projections" aria-label="K?t qu? b?ng ??nh l??ng" className="rounded border p-2">
              <h2 className="font-semibold">Ki?m tra b?ng ??nh l??ng</h2>
              {typedTableProjections.payment_schedules.map((projection, index) => (
                <article key={`payment-${index}`} className="my-2 rounded border p-2">
                  <h3>L?ch thanh to?n ? {String(projection.review_state ?? 'NEEDS_REVIEW')}</h3>
                  <p>{String(projection.table_id ?? '')} ? {String(projection.total_percent ?? 'Ch?a ?? d? li?u')}</p>
                  {Array.isArray(projection.issues) && projection.issues.map((issue, issueIndex) => <p key={issueIndex}>{String(issue)}</p>)}
                  <p>Coverage: {String((projection.coverage as Record<string, unknown> | undefined)?.reason ?? '?? ??c theo ph?m vi ngu?n')}</p>
                </article>
              ))}
              {typedTableProjections.boq_checks.map((projection, index) => (
                <article key={`boq-${index}`} className="my-2 rounded border p-2">
                  <h3>Ki?m tra s? h?c BOQ ? {String(projection.review_state ?? 'NEEDS_REVIEW')}</h3>
                  <p>{String(projection.table_id ?? '')} ? T?ng c?ng {String(projection.grand_total ?? 'UNKNOWN')}</p>
                  {Array.isArray(projection.issues) && projection.issues.map((issue, issueIndex) => <p key={issueIndex}>{String(issue)}</p>)}
                  <p>Coverage: {String((projection.coverage as Record<string, unknown> | undefined)?.reason ?? '?? ??c theo ph?m vi ngu?n')}</p>
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
                    <h3>
                      {frame.family} · {frame.profile}
                    </h3>
                    <p className="break-all">
                      {frame.frame_id} · {frame.key.certainty} ·{' '}
                      {frame.key.method} · {frame.key.reason}
                    </p>
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
                    {d}
                  </option>
                ))}
              </select>
            </label>
            {extension.pairs
              .filter((p) => filter === 'ALL' || p.disposition === filter)
              .map((p) => (
                <article key={p.pair_id} className="my-2 rounded border p-2">
                  <h3>
                    {p.disposition} · {p.review_state}
                  </h3>
                  <p>
                    {p.reason} · {p.method} · {p.candidate_sources.join(', ')}
                  </p>
                  {p.conflict_kind || p.alignment_key?.length || p.slots_in_difference?.length ? (
                    <p>
                      Kind: {p.conflict_kind ?? 'COMPARABLE_DIFFERENCE'} · Alignment:{' '}
                      {p.alignment_key?.join(' / ') ?? 'UNKNOWN'} · Different slots:{' '}
                      {p.slots_in_difference?.join(', ') || 'UNKNOWN'}
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
              <p>Chưa có cặp; xem coverage và lý do.</p>
            ) : null}
          </section>
          <section id="semantic-timeline">
            <h2 className="font-semibold">Dòng thời gian</h2>
            {extension.timeline.map((edge) => (
              <article key={edge.edge_id} className="my-2 rounded border p-2">
                <h3>
                  {edge.relation} · {edge.review_state}
                </h3>
                <p className="break-all">
                  {edge.source_id} → {edge.target_id ?? 'Thiếu đích'}
                </p>
                <p>
                  {edge.date_role} · {edge.date_value ?? 'Chưa xác định ngày'} ·{' '}
                  {edge.reasons.join('; ')}
                </p>
                {edge.acceptance ? (
                  <dl>
                    <Slot name="acceptance" value={edge.acceptance} />
                  </dl>
                ) : (
                  <p>Chấp thuận: UNKNOWN</p>
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
              <p>Chuỗi chưa được dựng; xem lý do trong coverage.</p>
            ) : null}
          </section>
          {extension.alias_drafts.length ? (
            <details>
              <summary>Alias nháp cần chuyên viên tenant duyệt</summary>
              {extension.alias_drafts.map((a, i) => (
                <p key={i}>
                  {a.source} → {a.symbol} · {a.kind} · {a.status} ·{' '}
                  {a.source_ref}
                </p>
              ))}
            </details>
          ) : null}
        </>
      )}
      <p>
        Giữ nghi vấn để người duyệt kiểm tra. Thẩm định không tự thay quy tắc
        alias hoặc lịch sử lần chạy.
      </p>
    </section>
  )
}
