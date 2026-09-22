import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { dossiersPath } from '../auth/session'
import { useAuth } from '../auth/useAuth'
import { MaterialIcon } from '../components/icons'
import {
  clauseConflicts,
  conflictDossier,
  type ClauseConflict,
  type ConflictChoice,
  type ConflictSource,
} from '../data/clauseConflicts'
import { usePageTitle } from '../hooks/usePageTitle'

type Decision = 'none' | 'confirm' | 'overlay' | 'reject'
type CompleteState = 'idle' | 'done'

function SourceCard({
  source,
  selected,
  flash,
  onSelect,
}: {
  source: ConflictSource
  selected: boolean
  flash: boolean
  onSelect: () => void
}) {
  return (
    <button
      className={`text-left bg-surface-container-low rounded-lg p-space-md flex flex-col justify-between transition-all group ${
        selected
          ? 'ring-1 ring-primary-container bg-surface-container'
          : 'hover:bg-surface-container-high/60'
      } ${flash ? 'bg-surface-container' : ''}`}
      type="button"
      onClick={onSelect}
    >
      <div className="flex flex-col gap-space-sm">
        <div className="flex items-center justify-between">
          <span className="font-label-sm text-label-sm text-on-surface-variant uppercase font-medium tracking-wide">
            {source.label}
          </span>
          <MaterialIcon
            name="check_circle"
            className={`text-[16px] ${
              selected
                ? 'text-primary'
                : 'text-on-surface-variant/60 group-hover:text-primary'
            }`}
          />
        </div>
        <div className="font-display-lg text-display-lg text-on-surface tracking-tight">
          {source.value}{' '}
          <span className="font-headline-md text-headline-md font-normal text-on-surface-variant">
            {source.unit}
          </span>
        </div>
        <div className="font-body-sm text-body-sm text-on-surface-variant flex items-center gap-space-xs">
          <MaterialIcon name="feed" className="text-[15px] text-secondary" />
          <span>{source.context}</span>
        </div>
        <div className="bg-surface-container-lowest p-space-sm rounded text-on-surface font-body-sm text-body-sm">
          <span className="font-code-sm text-code-sm text-on-surface-variant block mb-1">
            {source.location}
          </span>
          “{source.quoteBefore}
          <strong className="text-error bg-error-container/40 px-1 py-0.5 rounded">
            {source.highlight}
          </strong>
          {source.quoteAfter}”
        </div>
      </div>
      <div className="mt-space-md pt-space-xs flex items-center justify-between">
        <span className="px-space-sm py-0.5 rounded bg-surface-container-lowest text-on-secondary-container font-code-sm text-code-sm font-semibold shadow-xs">
          {source.field}
        </span>
      </div>
    </button>
  )
}

function QueueItem({
  conflict,
  active,
  onSelect,
}: {
  conflict: ClauseConflict
  active: boolean
  onSelect: () => void
}) {
  const resolved = Boolean(conflict.choice)
  return (
    <button
      className={`p-space-md rounded-lg flex flex-col gap-space-xs transition-all text-left ${
        active
          ? 'bg-surface-container-high text-on-surface'
          : 'hover:bg-surface-container'
      }`}
      type="button"
      onClick={onSelect}
    >
      <div className="flex items-center justify-between">
        <span
          className={`font-label-sm text-label-sm font-semibold uppercase tracking-wider ${
            active ? 'text-on-primary-fixed' : 'text-on-surface-variant'
          }`}
        >
          {conflict.code} {active ? '· Đang chọn' : ''}
        </span>
        {resolved ? (
          <span className="px-1.5 py-0.5 rounded bg-surface-container text-on-secondary-container font-code-sm text-code-sm font-semibold flex items-center gap-1">
            <MaterialIcon name="check" className="text-[13px]" /> Đã giải quyết
          </span>
        ) : (
          <span className="px-1.5 py-0.5 rounded bg-error-container text-on-error-container font-code-sm text-code-sm font-semibold">
            {conflict.badge}
          </span>
        )}
      </div>
      <span className="font-title-sm text-title-sm font-semibold text-on-surface">
        {conflict.title}
      </span>
      <div
        className={`font-code-sm text-code-sm ${
          active ? 'text-on-secondary-container' : 'text-on-surface-variant'
        }`}
      >
        {conflict.comparison}
      </div>
      <div className="mt-1 flex items-center justify-between text-on-surface-variant font-label-sm text-label-sm">
        <span>{conflict.location}</span>
        {active ? (
          <MaterialIcon
            name="arrow_forward"
            className="text-[16px] text-on-surface"
          />
        ) : (
          <span className="text-on-secondary-container font-code-sm text-code-sm">
            {conflict.choice === 'source1'
              ? 'Chọn Nguồn 1'
              : conflict.choice === 'source2'
                ? 'Chọn Nguồn 2'
                : conflict.choice === 'rejected'
                  ? 'Đã từ chối'
                  : conflict.choice === 'skipped'
                    ? 'Đã bỏ qua'
                    : conflict.choice === 'overlay'
                      ? 'Đã sửa overlay'
                      : 'Chờ duyệt'}
          </span>
        )}
      </div>
    </button>
  )
}

export function ClauseConflictPage() {
  usePageTitle('Đối soát xung đột điều khoản')
  const navigate = useNavigate()
  const { user } = useAuth()
  const [items, setItems] = useState(clauseConflicts)
  const [activeId, setActiveId] = useState(clauseConflicts[0].id)
  const [selectedSource, setSelectedSource] = useState<
    'source1' | 'source2' | null
  >(null)
  const [flash, setFlash] = useState<'source1' | 'source2' | null>(null)
  const [decision, setDecision] = useState<Decision>('none')
  const [overlay, setOverlay] = useState('')
  const [complete, setComplete] = useState<CompleteState>('idle')

  const active = items.find((item) => item.id === activeId) ?? items[0]
  const resolvedCount = items.filter((item) => item.choice).length
  const pendingCount = items.length - resolvedCount
  const progress = Math.round((resolvedCount / items.length) * 100)
  const queueIndex = items.findIndex((item) => item.id === activeId) + 1

  const diagnosis = useMemo(() => {
    if (!active) return ''
    if (selectedSource === 'source1') {
      return `Ưu tiên Nguồn 1: ${active.source1.value}. Nguồn 2 (${active.source2.value}) sẽ bị ghi đè.`
    }
    if (selectedSource === 'source2') {
      return `Ưu tiên Nguồn 2: ${active.source2.value}. Nguồn 1 (${active.source1.value}) sẽ bị ghi đè.`
    }
    return active.diagnosis
  }, [active, selectedSource])

  useEffect(() => {
    function handleKey(event: KeyboardEvent) {
      const tag = (event.target as HTMLElement | null)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA') return
      if (event.key === '1') {
        setSelectedSource('source1')
        setFlash('source1')
        window.setTimeout(() => setFlash(null), 250)
      }
      if (event.key === '2') {
        setSelectedSource('source2')
        setFlash('source2')
        window.setTimeout(() => setFlash(null), 250)
      }
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [])

  function applyChoice(choice: ConflictChoice) {
    const updated = items.map((item) =>
      item.id === activeId ? { ...item, choice } : item,
    )
    setItems(updated)
    setDecision('none')
    setOverlay('')
    const next = updated.find((item) => item.id !== activeId && !item.choice)
    if (next) {
      setActiveId(next.id)
      setSelectedSource(null)
    }
  }

  function handleConfirm() {
    if (!selectedSource) {
      setDecision('confirm')
      return
    }
    applyChoice(selectedSource)
  }

  function handleSkip() {
    applyChoice('skipped')
  }

  function handleReject() {
    applyChoice('rejected')
  }

  function handleSaveOverlay() {
    applyChoice('overlay')
  }

  function handleComplete() {
    setComplete('done')
    window.setTimeout(() => navigate(user ? dossiersPath(user.role) : '/'), 900)
  }

  function selectItem(conflict: ClauseConflict) {
    setActiveId(conflict.id)
    setSelectedSource(
      conflict.choice === 'source1' || conflict.choice === 'source2'
        ? conflict.choice
        : null,
    )
    setDecision('none')
  }

  return (
    <div className="flex flex-col w-full">
      <header className="py-space-lg flex flex-col md:flex-row md:items-center justify-between gap-space-md">
        <div className="flex flex-col gap-space-xs">
          <div className="flex items-center gap-space-sm flex-wrap">
            <span className="font-headline-lg text-headline-lg text-on-surface">
              Đối soát xung đột điều khoản
            </span>
            <span className="px-space-sm py-0.5 rounded bg-surface-container-high text-on-secondary-fixed font-code-sm text-code-sm font-semibold">
              {queueIndex} / {items.length} xung đột
            </span>
          </div>
          <p className="font-body-sm text-body-sm text-on-surface-variant flex items-center gap-space-xs flex-wrap">
            <MaterialIcon
              name="description"
              className="text-[15px] text-secondary"
            />
            <span>Hồ sơ: {conflictDossier.title}</span>
            <span className="text-outline">/</span>
            <span className="font-code-sm text-code-sm text-on-secondary-container">
              {conflictDossier.code}
            </span>
          </p>
        </div>
        <div className="flex items-center gap-space-sm self-start md:self-auto">
          <button
            className="h-9 px-space-md bg-surface-container-low hover:bg-surface-container text-on-surface-variant hover:text-on-surface rounded-lg font-body-sm text-body-sm font-medium transition-colors flex items-center gap-space-xs shadow-sm"
            type="button"
            onClick={handleSkip}
          >
            <MaterialIcon name="redo" className="text-[17px]" />
            <span>Bỏ qua mục này</span>
          </button>
          <button
            className="h-9 px-space-md bg-primary hover:bg-primary-container text-on-primary rounded-lg font-body-sm text-body-sm font-semibold transition-colors flex items-center gap-space-xs shadow-sm"
            type="button"
            onClick={handleComplete}
          >
            <MaterialIcon name="check_circle" className="text-[17px]" />
            <span>
              {complete === 'done' ? 'Đã hoàn tất' : 'Hoàn tất đối soát'}
            </span>
          </button>
        </div>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-gutter-lg pb-margin-lg items-start">
        <div className="lg:col-span-8 flex flex-col gap-gutter">
          <div className="bg-surface-container-lowest rounded-xl p-gutter shadow-[0_1px_3px_rgba(15,23,42,0.06)] flex flex-col gap-space-lg">
            <div className="flex flex-col gap-space-xs">
              <div>
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-surface-container-high text-on-primary-fixed-variant font-label-sm text-label-sm font-semibold uppercase tracking-wider">
                  <span className="w-1.5 h-1.5 rounded-[9999px] bg-error" />
                  Khác biệt so được
                </span>
              </div>
              <div className="flex items-center justify-between gap-space-sm flex-wrap">
                <h2 className="font-title-sm text-title-sm text-on-surface font-semibold flex items-center gap-space-xs">
                  <span>Trong cùng tài liệu</span>
                  <span className="text-outline">·</span>
                  <span className="font-code-sm text-code-sm text-on-secondary-container">
                    {active.field}
                  </span>
                </h2>
                <span className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">
                  Mã xung đột: #{active.id}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-space-md">
              <SourceCard
                source={active.source1}
                selected={selectedSource === 'source1'}
                flash={flash === 'source1'}
                onSelect={() => setSelectedSource('source1')}
              />
              <SourceCard
                source={active.source2}
                selected={selectedSource === 'source2'}
                flash={flash === 'source2'}
                onSelect={() => setSelectedSource('source2')}
              />
            </div>

            <div className="bg-surface-container-low rounded-lg p-space-md flex items-start gap-space-md">
              <MaterialIcon
                name="balance"
                className="text-[20px] text-secondary mt-0.5 flex-shrink-0"
              />
              <div className="flex flex-col gap-space-xs">
                <span className="font-label-sm text-label-sm uppercase tracking-wider font-semibold text-on-secondary-container">
                  Nhận định hệ thống
                </span>
                <p className="font-body-md text-body-md text-on-surface leading-relaxed">
                  {diagnosis}
                </p>
              </div>
            </div>

            <div className="pt-space-xs flex flex-wrap items-center gap-space-sm">
              <button
                className="h-9 px-space-lg bg-primary hover:bg-primary-container text-on-primary rounded font-body-sm text-body-sm font-semibold transition-colors flex items-center gap-space-xs shadow-sm"
                type="button"
                onClick={handleConfirm}
              >
                <MaterialIcon name="check" className="text-[16px]" />
                <span>Xác nhận</span>
              </button>
              <button
                className={`h-9 px-space-md rounded font-body-sm text-body-sm font-medium transition-colors flex items-center gap-space-xs ${
                  decision === 'overlay'
                    ? 'bg-primary-container text-on-primary'
                    : 'bg-surface-container hover:bg-surface-container-high text-on-surface'
                }`}
                type="button"
                onClick={() =>
                  setDecision((current) =>
                    current === 'overlay' ? 'none' : 'overlay',
                  )
                }
              >
                <MaterialIcon name="edit_note" className="text-[16px]" />
                <span>Sửa overlay</span>
              </button>
              <button
                className="h-9 px-space-md bg-surface-container hover:bg-surface-container-high text-error rounded font-body-sm text-body-sm font-medium transition-colors flex items-center gap-space-xs"
                type="button"
                onClick={handleReject}
              >
                <MaterialIcon name="close" className="text-[16px]" />
                <span>Từ chối</span>
              </button>
              {decision === 'confirm' && !selectedSource ? (
                <span className="font-label-sm text-label-sm text-error">
                  Chọn Nguồn 1 hoặc Nguồn 2 trước khi xác nhận.
                </span>
              ) : null}
            </div>

            {decision === 'overlay' ? (
              <div className="flex flex-col gap-space-xs">
                <label className="font-label-sm text-label-sm text-on-surface font-medium uppercase tracking-wide">
                  Overlay hiệu đính
                </label>
                <textarea
                  className="w-full p-space-sm bg-surface-container-low text-on-surface font-body-sm text-body-sm rounded outline-none focus:bg-surface-container-lowest focus:ring-1 focus:ring-outline-variant resize-none"
                  placeholder="Nhập giá trị hoặc diễn giải ưu tiên để ghi đè cả hai nguồn..."
                  rows={3}
                  value={overlay}
                  onChange={(event) => setOverlay(event.target.value)}
                />
                <div className="flex justify-end">
                  <button
                    className="h-8 px-space-md bg-primary-container text-on-primary rounded font-label-sm text-label-sm font-semibold"
                    type="button"
                    onClick={handleSaveOverlay}
                  >
                    Lưu overlay
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        </div>

        <aside className="lg:col-span-4 flex flex-col gap-space-md">
          <div className="bg-surface-container-lowest rounded-xl p-space-lg shadow-[0_1px_3px_rgba(15,23,42,0.06)] flex flex-col gap-space-md">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-space-xs">
                <MaterialIcon
                  name="view_list"
                  className="text-[18px] text-secondary"
                />
                <span className="font-title-sm text-title-sm text-on-surface font-semibold">
                  Hàng chờ review
                </span>
              </div>
              <span className="font-label-sm text-label-sm px-2 py-0.5 rounded-full bg-surface-container-high text-on-primary-fixed-variant font-semibold">
                {items.length} mục
              </span>
            </div>

            <div className="flex flex-col gap-space-xs">
              {items.map((conflict) => (
                <QueueItem
                  key={conflict.id}
                  conflict={conflict}
                  active={conflict.id === activeId}
                  onSelect={() => selectItem(conflict)}
                />
              ))}
            </div>

            <div className="pt-space-sm flex flex-col gap-space-xs">
              <div className="flex justify-between font-label-sm text-label-sm text-on-surface-variant font-medium">
                <span>Tiến độ đối soát hồ sơ</span>
                <span className="font-code-sm text-code-sm text-on-surface font-semibold">
                  {progress}%
                </span>
              </div>
              <div className="w-full bg-surface-container h-1.5 rounded-full overflow-hidden">
                <div
                  className="bg-primary h-full rounded-full transition-all"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <span className="font-code-sm text-code-sm text-on-surface-variant text-right">
                {resolvedCount} đã xử lý · {pendingCount} còn lại
              </span>
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}
