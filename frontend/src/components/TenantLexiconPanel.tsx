import { useEffect, useRef, useState } from 'react'
import {
  getTenantLexicon,
  LexiconConflictError,
  submitLexiconCommand,
  type LexiconAction,
  type LexiconCommand,
  type LexiconModel,
} from '../api/tenantLexicon'

const ACTION_SYMBOLS = [
  'PAY',
  'DELIVER',
  'ACCEPT',
  'NOTIFY',
  'TERMINATE',
  'COMPENSATE',
  'PENALTY',
  'DISCLOSE',
  'KEEP_CONFIDENTIAL',
  'RETURN',
  'REPAIR',
  'PERFORM',
]
const QUALIFIERS = [
  'BREACH',
  'DELAY',
  'NONPAYMENT',
  'DAMAGE',
  'CONFIDENTIALITY',
]

export function TenantLexiconPanel({
  tenantId,
  actorId,
  initial,
}: {
  tenantId: string
  actorId: string
  initial?: LexiconModel
}) {
  const [model, setModel] = useState<LexiconModel | null>(initial ?? null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [historical, setHistorical] = useState(false)
  const [source, setSource] = useState('')
  const [kind, setKind] = useState<'action' | 'qualifier'>('action')
  const [symbol, setSymbol] = useState('PAY')
  const [sourceRef, setSourceRef] = useState('')
  const [consentRef, setConsentRef] = useState('')
  const [expertId, setExpertId] = useState('')
  const [expertiseRef, setExpertiseRef] = useState('')
  const [expiry, setExpiry] = useState('')
  const [errors, setErrors] = useState('0')
  const [denominator, setDenominator] = useState('')
  const [labelsRef, setLabelsRef] = useState('')
  const pending = useRef<{ signature: string; command: LexiconCommand } | null>(
    null,
  )
  useEffect(() => {
    if (initial) {
      setModel(initial)
      return
    }
    const controller = new AbortController()
    setModel(null)
    setMessage(null)
    getTenantLexicon(tenantId, controller.signal)
      .then((next) => {
        if (!controller.signal.aborted) setModel(next)
      })
      .catch((cause: unknown) => {
        if (!controller.signal.aborted)
          setMessage(
            cause instanceof Error ? cause.message : 'Không đọc được lexicon.',
          )
      })
    return () => controller.abort()
  }, [tenantId, initial])
  async function loadVersion(version?: number) {
    setBusy(true)
    setMessage(null)
    try {
      setModel(await getTenantLexicon(tenantId, undefined, version))
      setHistorical(version !== undefined)
    } catch (cause) {
      setMessage(
        cause instanceof Error ? cause.message : 'Không tải được phiên bản.',
      )
    } finally {
      setBusy(false)
    }
  }
  async function send(action: LexiconAction, payload: Record<string, unknown>) {
    if (!model || busy || historical) return
    const signature = JSON.stringify({
      action,
      payload,
      version: model.profile.version,
    })
    if (pending.current?.signature !== signature)
      pending.current = {
        signature,
        command: {
          action,
          payload,
          base_version: model.profile.version,
          idempotency_key: crypto.randomUUID(),
        },
      }
    setBusy(true)
    setMessage(null)
    try {
      const receipt = await submitLexiconCommand(
        tenantId,
        pending.current.command,
      )
      pending.current = null
      setModel(await getTenantLexicon(tenantId))
      setHistorical(false)
      setMessage(
        `Đã lưu phiên bản ${receipt.version}: ${receipt.activation_state}. Alias chỉ áp dụng ở lần chạy mới theo policy đã duyệt.`,
      )
    } catch (cause) {
      if (cause instanceof LexiconConflictError) {
        if (cause.current) {
          setModel(cause.current)
          setHistorical(false)
        }
        pending.current = null
      }
      setMessage(
        cause instanceof Error ? cause.message : 'Không lưu được quyết định.',
      )
    } finally {
      setBusy(false)
    }
  }
  if (!model) return <p role="status">{message ?? 'Đang tải lexicon…'}</p>
  if (model.profile.tenant_id !== tenantId)
    return <p role="alert">Profile thuộc tenant khác.</p>
  const { profile, permissions, assignment } = model
  const disabled = busy || historical
  return (
    <section
      aria-label="Alias của tenant"
      className="space-y-3 rounded-xl border border-outline-variant/40 bg-surface-container-lowest p-4 text-sm"
    >
      <h2 className="font-semibold">
        Alias của tenant · Phiên bản {profile.version}
      </h2>
      <p>
        {profile.activation_state} · {profile.activation_blockers.join('; ')}
      </p>
      <p>
        Alias đã duyệt: {profile.aliases.length} · Đang áp dụng:{' '}
        {profile.active_aliases.length}. Thay đổi cần lần chạy mới; kết quả cũ
        được giữ nguyên.
      </p>
      <p className="break-all">
        Chuyên viên hợp đồng: {assignment?.expert_id ?? 'Chưa chỉ định'} ·{' '}
        {assignment?.expertise_ref} · hết hạn {assignment?.expires_at ?? '—'}
      </p>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy || profile.version <= 1}
          onClick={() => void loadVersion(profile.version - 1)}
        >
          Phiên bản trước
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => void loadVersion()}
        >
          Tải phiên bản hiện tại
        </button>
      </div>
      {historical ? (
        <p role="status">
          Đang xem lịch sử. Tải phiên bản hiện tại để ra quyết định.
        </p>
      ) : null}
      {message ? <p role="status">{message}</p> : null}
      {permissions.can_assign ? (
        <form
          onSubmit={(e) => {
            e.preventDefault()
            const date = new Date(expiry)
            if (Number.isNaN(date.getTime())) {
              setMessage('Nhập thời hạn chỉ định hợp lệ.')
              return
            }
            void send('ASSIGN', {
              expert_id: expertId,
              expertise_ref: expertiseRef,
              expires_at: date.toISOString(),
            })
          }}
          className="grid gap-2"
        >
          <h3>Chỉ định chuyên viên hợp đồng</h3>
          <label>
            Expert ID
            <input
              required
              value={expertId}
              onChange={(e) => setExpertId(e.target.value)}
            />
          </label>
          <label>
            Chứng cứ chuyên môn
            <input
              required
              value={expertiseRef}
              onChange={(e) => setExpertiseRef(e.target.value)}
            />
          </label>
          <label>
            Hết hạn
            <input
              required
              type="datetime-local"
              value={expiry}
              onChange={(e) => setExpiry(e.target.value)}
            />
          </label>
          <button disabled={disabled} type="submit">
            Chỉ định
          </button>
        </form>
      ) : null}
      {permissions.can_propose ? (
        <form
          onSubmit={(e) => {
            e.preventDefault()
            void send('PROPOSE', {
              source,
              kind,
              symbol,
              source_ref: sourceRef,
            })
          }}
          className="grid gap-2"
        >
          <h3>Đề xuất alias trừu tượng</h3>
          <label>
            Cụm từ
            <input
              required
              minLength={4}
              maxLength={120}
              value={source}
              onChange={(e) => setSource(e.target.value)}
            />
          </label>
          <label>
            Loại
            <select
              value={kind}
              onChange={(e) => {
                const next = e.target.value as 'action' | 'qualifier'
                setKind(next)
                setSymbol(next === 'action' ? 'PAY' : 'BREACH')
              }}
            >
              <option value="action">Hành động</option>
              <option value="qualifier">Loại vi phạm</option>
            </select>
          </label>
          <label>
            Symbol
            <select value={symbol} onChange={(e) => setSymbol(e.target.value)}>
              {(kind === 'action' ? ACTION_SYMBOLS : QUALIFIERS).map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <label>
            Source ref
            <input
              required
              value={sourceRef}
              onChange={(e) => setSourceRef(e.target.value)}
            />
          </label>
          <button type="submit" disabled={disabled}>
            Gửi nháp
          </button>
        </form>
      ) : null}
      <div className="space-y-2">
        {profile.proposals.map((proposal) => {
          const state = profile.decisions[proposal.proposal_id]
          const own = proposal.producer_id === actorId
          const approvedBy = profile.aliases.find(
            (a) => a.proposal_id === proposal.proposal_id,
          )?.approved_by
          return (
            <article key={proposal.proposal_id} className="rounded border p-2">
              <h3>
                {proposal.source} → {proposal.symbol} · {proposal.kind}
              </h3>
              <p>
                {state} · {proposal.source_ref}
              </p>
              <p>Người đề xuất: {proposal.producer_id}</p>
              <div className="flex flex-wrap gap-2">
                {permissions.can_approve && state === 'PROPOSED' ? (
                  <button
                    type="button"
                    disabled={disabled || own}
                    onClick={() =>
                      void send('APPROVE', {
                        proposal_id: proposal.proposal_id,
                      })
                    }
                  >
                    Duyệt
                  </button>
                ) : null}
                {permissions.can_reject && state === 'PROPOSED' ? (
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() =>
                      void send('REJECT', { proposal_id: proposal.proposal_id })
                    }
                  >
                    Từ chối
                  </button>
                ) : null}
                {permissions.can_revoke && state === 'APPROVED_DRAFT' ? (
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() =>
                      void send('REVOKE', { proposal_id: proposal.proposal_id })
                    }
                  >
                    Thu hồi
                  </button>
                ) : null}
                {permissions.can_promote ? (
                  <button
                    type="button"
                    disabled={disabled}
                    onClick={() =>
                      void send('PROMOTE', {
                        proposal_id: proposal.proposal_id,
                      })
                    }
                  >
                    Đề nghị dùng chung alias trừu tượng
                  </button>
                ) : null}
              </div>
              {own ? <p>Người đề xuất không tự duyệt nhãn của mình.</p> : null}
              <details>
                <summary>Đo lỗi độc lập</summary>
                <pre className="max-w-full overflow-auto whitespace-pre-wrap">
                  {JSON.stringify(
                    profile.measurements[proposal.proposal_id] ??
                      'NOT_MEASURED',
                    null,
                    2,
                  )}
                </pre>
                {permissions.can_measure && !own && approvedBy !== actorId ? (
                  <form
                    className="grid gap-1"
                    onSubmit={(e) => {
                      e.preventDefault()
                      void send('MEASURE', {
                        proposal_id: proposal.proposal_id,
                        errors: Number(errors),
                        denominator: Number(denominator),
                        labels_ref: labelsRef,
                      })
                    }}
                  >
                    <label>
                      Số lỗi
                      <input
                        type="number"
                        min={0}
                        required
                        value={errors}
                        onChange={(e) => setErrors(e.target.value)}
                      />
                    </label>
                    <label>
                      Denominator
                      <input
                        type="number"
                        min={1}
                        required
                        value={denominator}
                        onChange={(e) => setDenominator(e.target.value)}
                      />
                    </label>
                    <label>
                      Nhãn đã duyệt
                      <input
                        required
                        value={labelsRef}
                        onChange={(e) => setLabelsRef(e.target.value)}
                      />
                    </label>
                    <button disabled={disabled} type="submit">
                      Ghi đo lỗi
                    </button>
                  </form>
                ) : null}
              </details>
            </article>
          )
        })}
      </div>
      {permissions.can_opt_in ? (
        <form
          onSubmit={(e) => {
            e.preventDefault()
            void send('OPT_IN', {
              enabled: !profile.opt_in,
              consent_ref: consentRef,
            })
          }}
        >
          <label>
            Receipt đồng ý chia sẻ alias trừu tượng
            <input
              required
              value={consentRef}
              onChange={(e) => setConsentRef(e.target.value)}
            />
          </label>
          <button type="submit" disabled={disabled}>
            {profile.opt_in ? 'Tắt opt-in' : 'Xác nhận opt-in'}
          </button>
        </form>
      ) : (
        <p>Opt-in: {profile.opt_in ? 'Có' : 'Chưa'}</p>
      )}
    </section>
  )
}
