import { useEffect, useMemo, useRef, useState } from 'react'
import { useLocation, useNavigate, useParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import {
  findLatestRunId,
  formatStepProgress,
  isAi2Step,
  listRunSteps,
  OCR_RUN_STEP_ORDER,
  RUN_STEP_GROUPS,
  RUN_STEP_LABELS,
  stepFromEvent,
  stepProgressPercent,
  watchRun,
  type RunStep,
} from '../api/runEvents'
import {
  deleteDossier,
  loadDocumentOcrPages,
  rerunDossierOcr,
  retryDossierFailed,
  restartOcrErrorMessage,
  type OcrPageRow,
} from '../api/dossiers'
import {
  countClauses,
  getDossierStructure,
  isOcrComplete,
  isRunFinished,
  listClauses,
  structureErrorMessage,
  type DossierStructure,
  type StructureDocument,
} from '../api/structure'
import { isAi2Failure, isCancelledJob, jobErrorInfo } from '../api/jobErrors'
import {
  cancelRun,
  isCancellableRun,
  latestDossierRun,
  runActionErrorMessage,
} from '../api/runs'
import { dossiersPath } from '../auth/session'
import { useAuth } from '../auth/useAuth'
import { TechnicalDetail } from '../components/TechnicalDetail'
import { useDossierPermissions } from '../auth/dossierPermissions'
import { MaterialIcon } from '../components/icons'
import { structurePath } from '../data/dossiers'
import { usePageTitle } from '../hooks/usePageTitle'
import { parseStructureMode, type StructureMode } from '../structure'

const POLL_INTERVAL_MS = 2000
// BE phát lại step.changed khi chỉ `progress` đổi (khoảng 20 lần mỗi bước):
// tin đó tự cập nhật vòng tiến độ, chỉ tải lại hồ sơ cách nhau ít nhất chừng này.
const PROGRESS_RELOAD_INTERVAL_MS = 10000

// Job đã dừng hẳn: lỗi, hoặc bị hủy (hủy run đưa job về failed/RUN_CANCELLED).
function isStoppedJob(status: string | null | undefined) {
  return status === 'failed' || status === 'cancelled'
}

type FileStatus = 'done' | 'reading' | 'waiting' | 'failed'

type FileRowModel = {
  id: string
  name: string
  meta: string
  status: FileStatus
  label: string
}

type LogRowModel = {
  id: string
  text: string
  status: 'done' | 'active' | 'failed'
  step?: string
}

// Một danh sách liền, theo thứ tự chạy thật. Chỉ phần đọc tài liệu: AI2 chạy
// ngầm sau OCR, tiến độ của nó hiện trên trang cấu trúc.
const RUN_STEPS = RUN_STEP_GROUPS.flatMap((group) =>
  group.id === 'ai2'
    ? []
    : group.steps.map((code) => ({ code, ocr: group.id === 'ai1' })),
)

function pageDone(page: OcrPageRow) {
  return page.status === 'SUCCESS' || page.status === 'PARTIAL'
}

function pageFailed(page: OcrPageRow) {
  return page.status === 'FAILED' || Boolean(page.error)
}

function fileModel(
  document: StructureDocument,
  pages: OcrPageRow[],
  jobStatus: string | null,
  current: boolean,
  ocrFailed: boolean,
): FileRowModel {
  const total = Math.max(document.pageCount, pages.length)
  const done = pages.filter(pageDone).length
  const failed = pages.filter(pageFailed).length
  const meta = total > 0 ? `• ${total} trang` : '• PDF'
  if (failed > 0 && ocrFailed) {
    return {
      id: document.id,
      name: document.filename,
      meta,
      status: 'failed',
      label: 'Đọc lỗi',
    }
  }
  if (total > 0 && done >= total && isOcrComplete(jobStatus)) {
    return {
      id: document.id,
      name: document.filename,
      meta,
      status: 'done',
      label: 'Hoàn thành',
    }
  }
  if (isOcrComplete(jobStatus)) {
    return {
      id: document.id,
      name: document.filename,
      meta,
      status: 'done',
      label: 'Hoàn thành',
    }
  }
  if (
    current &&
    (jobStatus === 'processing' || jobStatus === 'uploaded' || done > 0)
  ) {
    const percent = total > 0 ? Math.round((done / total) * 100) : null
    return {
      id: document.id,
      name: document.filename,
      meta,
      status: 'reading',
      label: percent === null ? 'Đang đọc' : `Đang đọc ${percent}%`,
    }
  }
  return {
    id: document.id,
    name: document.filename,
    meta,
    status: 'waiting',
    label: 'Chờ xử lý',
  }
}

function stateStructureMode(state: unknown): StructureMode | null {
  if (!state || typeof state !== 'object') return null
  return parseStructureMode(
    (state as { structureMode?: unknown }).structureMode,
  )
}

export function AnalysisProgressPage() {
  const { dossierId = '' } = useParams()
  const location = useLocation()
  const navigate = useNavigate()
  const { user } = useAuth()
  const backTo = user ? dossiersPath(user.role) : '/ho-so'
  // Hủy, chạy lại là DOSSIER_EDIT; xóa là DOSSIER_MANAGE (chủ hồ sơ hoặc Quản trị).
  const permissions = useDossierPermissions(dossierId)
  const canManageRun = permissions.canEdit
  const canDelete = permissions.canManage
  const [detail, setDetail] = useState<DossierStructure | null>(null)
  const [pagesByDoc, setPagesByDoc] = useState<Record<string, OcrPageRow[]>>({})
  const [clauseCount, setClauseCount] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const [steps, setSteps] = useState<Record<string, RunStep>>({})
  const [liveLog, setLiveLog] = useState<LogRowModel[]>([])
  const passedName = (location.state as { name?: string } | null)?.name

  usePageTitle(detail?.name ?? passedName ?? 'Tiến trình phân tích')

  useEffect(() => {
    if (dossierId) return
    navigate(backTo, { replace: true })
  }, [backTo, dossierId, navigate])

  // Một lần điều hướng chỉ gửi một lệnh chạy lại. StrictMode chạy effect hai
  // lần khi mở trang, và state.restart chưa kịp xóa ở lần thứ hai: không có cờ
  // này thì hai run OCR cùng một hồ sơ, run sau thay run trước.
  const restartSentFor = useRef<string | null>(null)
  useEffect(() => {
    const restart = Boolean(
      (location.state as { restart?: boolean } | null)?.restart,
    )
    if (!restart || !dossierId) return
    if (restartSentFor.current === location.key) return
    restartSentFor.current = location.key
    navigate(location.pathname, { replace: true, state: null })
    setBusy(true)
    setError(null)
    void rerunDossierOcr(dossierId)
      .then(() => setAttempt((value) => value + 1))
      .catch((cause: unknown) => setError(restartOcrErrorMessage(cause)))
      .finally(() => setBusy(false))
  }, [dossierId, location.key, location.pathname, location.state, navigate])

  useEffect(() => {
    if (!dossierId) return
    const controller = new AbortController()
    let timer: number | undefined
    let stopped = false
    let notFoundTries = 0
    let watching = false
    let loading = false
    let reloadQueued = false
    let finishedRunId: string | null = null
    let polling = false
    // Trang OCR và điều khoản không đổi khi job đã 'extracted': tải một lần.
    let settled = false
    // Trạng thái đã nhận của từng bước: tin chỉ đổi tiến độ không thêm dòng nhật ký.
    const seenStatus: Record<string, string> = {}
    let lastProgressReload = 0
    setSteps({})
    setLiveLog([])

    // SSE bị từ chối hoặc không thấy run: quay lại hỏi định kỳ cho tới khi job kết thúc.
    function startPolling() {
      if (stopped || polling) return
      polling = true
      schedulePoll()
    }

    function schedulePoll() {
      if (stopped) return
      if (timer !== undefined) window.clearTimeout(timer)
      timer = window.setTimeout(requestReload, POLL_INTERVAL_MS)
    }

    // Server đẩy tin xuống thì chỉ tải lại số liệu; không hẹn giờ hỏi định kỳ.
    function requestReload() {
      if (loading) {
        reloadQueued = true
        return
      }
      void load()
    }

    // Lấy trạng thái bước đã lưu: dùng khi mở trang lúc run đã chạy xong,
    // hoặc để chốt lại sau khi stream kết thúc.
    async function syncSteps(knownRunId?: string | null) {
      try {
        const runId =
          knownRunId ?? (await findLatestRunId(dossierId, controller.signal))
        if (!runId || stopped) return
        const rows = await listRunSteps(runId, controller.signal)
        if (stopped || rows.length === 0) return
        setSteps((current) => ({
          ...current,
          ...Object.fromEntries(rows.map((row) => [row.step, row])),
        }))
      } catch {
        // Không có số liệu bước: panel vẫn hiện theo tin đã nhận.
      }
    }

    async function watch() {
      if (watching) return
      watching = true
      try {
        let runId: string | null = null
        // Run có thể chưa được tạo ngay sau khi tải lên.
        for (let tries = 0; tries < 15 && !runId; tries += 1) {
          runId = await findLatestRunId(dossierId, controller.signal)
          if (!runId) {
            await new Promise((resolve) => window.setTimeout(resolve, 1000))
            if (stopped) return
          }
        }
        if (stopped) return
        if (!runId) {
          startPolling()
          return
        }
        if (runId === finishedRunId) {
          // Stream đã đóng mà job chưa kết thúc: hỏi định kỳ, không thì trang đứng im.
          startPolling()
          return
        }
        await watchRun(
          runId,
          {
            onEvent: (event) => {
              const step = stepFromEvent(event)
              // Bước AI2 không hiện ở đây và không đổi gì trên trang này.
              if (step && isAi2Step(step.step)) return
              if (step) {
                setSteps((current) => ({ ...current, [step.step]: step }))
                const statusChanged = seenStatus[step.step] !== step.status
                seenStatus[step.step] = step.status
                if (!statusChanged) {
                  // Chỉ đổi tiến độ: vòng tiến độ đã cập nhật ở trên. Vẫn tải lại
                  // thưa thớt để danh sách tệp thấy tài liệu vừa đọc xong.
                  const now = Date.now()
                  if (now - lastProgressReload >= PROGRESS_RELOAD_INTERVAL_MS) {
                    lastProgressReload = now
                    requestReload()
                  }
                  return
                }
                const label = RUN_STEP_LABELS[step.step] ?? step.step
                const text =
                  step.status === 'succeeded'
                    ? `${step.step} · ${label}: xong${
                        step.durationMs !== null
                          ? ` (${(step.durationMs / 1000).toFixed(1)}s)`
                          : ''
                      }`
                    : step.status === 'running'
                      ? `${step.step} · ${label}: đang chạy`
                      : step.status === 'failed'
                        ? `${step.step} · ${label}: lỗi`
                        : null
                if (text) {
                  setLiveLog((rows) => [
                    ...rows,
                    {
                      id: `${event.id ?? rows.length}-${step.step}-${step.status}`,
                      step: step.step,
                      status:
                        step.status === 'succeeded'
                          ? 'done'
                          : step.status === 'failed'
                            ? 'failed'
                            : 'active',
                      text: `${new Date().toLocaleTimeString('vi-VN')} — ${text}`,
                    },
                  ])
                }
              }
              if (event.event !== 'run.started') requestReload()
            },
            onLost: requestReload,
            onRejected: () => {
              setError('Không nhận được tiến độ trực tiếp từ máy chủ.')
              startPolling()
            },
          },
          controller.signal,
        )
        if (stopped) return
        // Bị từ chối thì không có run.completed: không đánh dấu run đã xong.
        if (!polling) finishedRunId = runId
        await syncSteps(runId)
        requestReload()
      } catch {
        // Không lấy được run: hỏi định kỳ để vẫn thấy job kết thúc.
        startPolling()
      } finally {
        watching = false
      }
    }

    async function load() {
      loading = true
      try {
        const next = await getDossierStructure(dossierId, controller.signal)
        if (stopped) return
        const pages = settled
          ? null
          : await Promise.all(
              next.documents.map(async (document) => {
                try {
                  const rows = await loadDocumentOcrPages(
                    document.id,
                    controller.signal,
                  )
                  return [document.id, rows] as const
                } catch {
                  return [document.id, [] as OcrPageRow[]] as const
                }
              }),
            )
        if (stopped) return
        setDetail(next)
        if (pages) setPagesByDoc(Object.fromEntries(pages))
        setError(null)
        notFoundTries = 0
        if (isOcrComplete(next.latestJobStatus)) {
          const finishedRun = isRunFinished(next.latestJobStatus)
          if (!settled || polling || finishedRun) void syncSteps()
          if (!settled) {
            settled = true
            const contract =
              next.documents.find(
                (document) => document.role.toLowerCase() === 'contract',
              ) ?? next.documents[0]
            if (contract) {
              try {
                const tree = await listClauses(contract.id, controller.signal)
                if (!stopped) setClauseCount(countClauses(tree))
              } catch {
                if (!stopped) setClauseCount(null)
              }
            }
          }
          // OCR xong là trang này xong: AI2 chạy ngầm, không theo dõi tiếp.
          return
        }
        if (isStoppedJob(next.latestJobStatus)) {
          void syncSteps()
          return
        }
        setClauseCount(null)
        if (polling) schedulePoll()
        else void watch()
      } catch (cause) {
        if (controller.signal.aborted || stopped) return
        const message = structureErrorMessage(cause)
        if (!message) return
        // POST commits just as this page opens. A 404 in that window is not final.
        if (
          cause instanceof ApiError &&
          cause.status === 404 &&
          notFoundTries < 10
        ) {
          notFoundTries += 1
          timer = window.setTimeout(() => {
            void load()
          }, 400)
          return
        }
        setError(message)
      } finally {
        loading = false
        if (reloadQueued && !stopped) {
          reloadQueued = false
          void load()
        }
      }
    }

    void load()
    return () => {
      stopped = true
      controller.abort()
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [attempt, dossierId])

  const documents = useMemo(() => detail?.documents ?? [], [detail])
  const jobStatus = detail?.latestJobStatus ?? null
  const stopped = isStoppedJob(jobStatus)
  const failure = useMemo(
    () => jobErrorInfo(detail?.latestJobErrorCode),
    [detail?.latestJobErrorCode],
  )
  // Job dừng sau khi OCR đã xong (AI2 lỗi) hoặc do người dùng hủy thì không phải lỗi OCR.
  const cancelled = isCancelledJob(jobStatus, detail?.latestJobErrorCode)
  const ai2Failed =
    stopped && !cancelled && isAi2Failure(detail?.latestJobErrorCode, steps)
  const ocrFailed = stopped && !cancelled && !ai2Failed
  // Trang này chỉ theo dõi phần đọc tài liệu: AI2 lỗi vẫn là OCR đã xong,
  // lỗi đó hiện trên trang cấu trúc.
  const ready = isOcrComplete(jobStatus) || ai2Failed
  const failed = stopped && !ai2Failed
  const fileJobStatus = ai2Failed ? 'extracted' : jobStatus
  const files = useMemo(() => {
    const current = documents.find((document) => {
      const pages = pagesByDoc[document.id] ?? []
      const total = Math.max(document.pageCount, pages.length)
      const done = pages.filter(pageDone).length
      return total === 0 || done < total
    })
    return documents.map((document) =>
      fileModel(
        document,
        pagesByDoc[document.id] ?? [],
        fileJobStatus,
        current?.id === document.id,
        ocrFailed,
      ),
    )
  }, [documents, fileJobStatus, ocrFailed, pagesByDoc])

  const pageTotals = documents.reduce(
    (totals, document) => {
      const pages = pagesByDoc[document.id] ?? []
      const total = Math.max(document.pageCount, pages.length)
      return {
        total: totals.total + total,
        done: totals.done + pages.filter(pageDone).length,
      }
    },
    { total: 0, done: 0 },
  )
  // BE không báo % của từng bước; bước AI1 lấy theo số trang OCR đã đọc, bước khác chỉ quay.
  const ocrPercent =
    pageTotals.total > 0
      ? Math.min(99, Math.round((pageTotals.done / pageTotals.total) * 100))
      : null
  const stepList = OCR_RUN_STEP_ORDER.flatMap((code) =>
    steps[code] ? [steps[code]] : [],
  )
  const stepsDone = stepList.filter((row) => row.status === 'succeeded').length
  // Bước đang chạy có `progress` thì góp phần đã xong vào thanh tổng.
  const runningShare = stepList.reduce(
    (sum, row) =>
      row.status === 'running' && row.progress
        ? sum + row.progress.done / row.progress.total
        : sum,
    0,
  )
  // Trang đã OCR chỉ được lưu khi cả tài liệu xong; S2 `progress` (đơn vị trang)
  // đếm theo từng trang AI1 báo về (DOC-05d `ai1.ocr.progress`).
  const ocrProgress = steps.S2?.progress
  const pagesRead =
    ocrProgress?.unit === 'page'
      ? Math.max(pageTotals.done, ocrProgress.done)
      : pageTotals.done
  const pagesTotal =
    pageTotals.total || (ocrProgress?.unit === 'page' ? ocrProgress.total : 0)
  const hasSteps = stepList.length > 0
  const percent = hasSteps
    ? Math.min(
        99,
        Math.round(
          ((stepsDone + runningShare) / OCR_RUN_STEP_ORDER.length) * 100,
        ),
      )
    : pageTotals.total > 0
      ? // Đọc xong mọi trang mới là phần OCR: chưa tới 100 khi AI2 chưa xong.
        Math.min(99, Math.round((pageTotals.done / pageTotals.total) * 100))
      : ready
        ? 100
        : 0

  const logs = useMemo(() => {
    const rows: LogRowModel[] = []
    if (documents.length > 0) {
      rows.push({
        id: 'received',
        status: 'done',
        text: `Đã tiếp nhận ${documents.length} tệp hồ sơ`,
      })
    }
    for (const file of files) {
      if (file.status === 'done') {
        rows.push({
          id: `${file.id}-done`,
          status: 'done',
          text: `Đã đọc xong ${file.name}`,
        })
      } else if (file.status === 'reading') {
        rows.push({
          id: `${file.id}-read`,
          status: 'active',
          text: `${file.label}: ${file.name}`,
        })
      } else if (file.status === 'failed') {
        rows.push({
          id: `${file.id}-fail`,
          status: 'failed',
          text: `Đọc lỗi trên ${file.name}`,
        })
      }
    }
    if (ready) {
      rows.push({
        id: 'finish',
        status: 'done',
        text: 'Đã dựng xong cấu trúc. Có thể mở hồ sơ.',
      })
    }
    if (liveLog.length === 0) return rows
    // Có tin trực tiếp từ BE thì hiện đúng các tin đó, kèm dòng đã tiếp nhận / hoàn tất.
    const received = rows.filter((row) => row.id === 'received')
    const finish = rows.filter((row) => row.id === 'finish')
    // Dòng "đang chạy" chỉ còn xoay khi bước đó vẫn đang chạy.
    const live = liveLog.map((row) =>
      row.status === 'active' &&
      row.step &&
      (ready || failed || steps[row.step]?.status !== 'running')
        ? { ...row, status: 'done' as const }
        : row,
    )
    return [...received, ...live, ...finish]
  }, [documents.length, failed, files, liveLog, ready, steps])

  const mode = detail?.structureMode ?? stateStructureMode(location.state)

  async function cancelJob() {
    if (!dossierId || busy) return
    if (
      !window.confirm(
        'Hủy lần xử lý đang chạy? Hồ sơ và tệp đã tải vẫn được giữ.',
      )
    ) {
      return
    }
    setBusy(true)
    setError(null)
    try {
      const run = await latestDossierRun(dossierId)
      if (!run || !isCancellableRun(run.status)) {
        setError('Không có lần xử lý nào đang chạy để hủy.')
        return
      }
      await cancelRun(run.runId)
      setAttempt((value) => value + 1)
    } catch (cause) {
      setError(runActionErrorMessage(cause))
    } finally {
      setBusy(false)
    }
  }

  async function deleteJob() {
    if (!dossierId || busy) return
    if (!window.confirm('Xóa hồ sơ này? Tệp đã tải sẽ bị gỡ.')) return
    setBusy(true)
    try {
      await deleteDossier(dossierId)
      const name = (detail?.name ?? passedName)?.trim()
      navigate(backTo, {
        state: {
          notice: name ? `Đã xóa hồ sơ “${name}”.` : 'Đã xóa hồ sơ.',
        },
      })
    } catch {
      setError('Không xóa được hồ sơ.')
      setBusy(false)
    }
  }

  async function retry() {
    if (!dossierId || busy) return
    setBusy(true)
    setError(null)
    try {
      if (failure.retry === 'none') {
        setBusy(false)
        return
      }
      await retryDossierFailed(dossierId, failure.retry)
      setAttempt((value) => value + 1)
      setBusy(false)
    } catch (cause) {
      setError(restartOcrErrorMessage(cause))
      setBusy(false)
    }
  }

  const failedLabel = cancelled ? 'Đã hủy lần xử lý' : 'Đọc tài liệu thất bại'
  const finished = ready || failed
  const runningStep = finished
    ? undefined
    : stepList.find((row) => row.status === 'running')
  const activeLabel = failed
    ? failedLabel
    : ready
      ? 'Đã đọc xong tài liệu. Có thể mở hồ sơ.'
      : runningStep
        ? `Đang chạy: ${runningStep.step} · ${RUN_STEP_LABELS[runningStep.step] ?? ''}`
        : 'Đang chờ máy chủ nhận tệp'

  return (
    <div className="flex flex-col w-full pt-space-md pb-margin-lg">
      {error ? (
        <p
          className="mb-gutter rounded-lg bg-error-container px-space-md py-space-sm font-body-sm text-body-sm text-on-error-container"
          role="alert"
        >
          {error}
        </p>
      ) : null}

      {failed ? (
        <p
          className="mb-gutter rounded-lg bg-error-container px-space-md py-space-sm font-body-sm text-body-sm text-on-error-container"
          role="alert"
        >
          {failure.message}
          <TechnicalDetail text={failure.code && `Mã ${failure.code}`} />
        </p>
      ) : null}

      <section className="bg-surface-container-lowest rounded-lg p-space-lg shadow-sm mb-gutter">
        <div className="flex flex-col lg:flex-row lg:items-center gap-space-lg">
          <div className="flex-1 min-w-0">
            <div className="flex items-baseline justify-between gap-space-md mb-space-sm">
              <span
                className={`font-title-sm text-title-sm font-semibold ${
                  failed ? 'text-error' : 'text-on-surface'
                }`}
              >
                {activeLabel}
              </span>
              <span className="font-headline-md text-headline-md text-primary font-bold">
                {ready ? '100%' : `${percent}%`}
              </span>
            </div>
            <div className="h-2 w-full rounded-full bg-surface-container overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  failed ? 'bg-error' : 'bg-primary'
                }`}
                style={{ width: `${ready ? 100 : percent}%` }}
              />
            </div>
            <span className="font-label-sm text-label-sm text-on-surface-variant mt-space-xs block">
              {finished
                ? 'Đã kết thúc'
                : `${stepsDone}/${OCR_RUN_STEP_ORDER.length} bước hoàn thành`}{' '}
              · cập nhật trực tiếp từ máy chủ
            </span>
          </div>
          <div className="grid grid-cols-3 gap-space-sm lg:w-[420px] shrink-0">
            <Stat label="Tài liệu" value={String(documents.length)} />
            <Stat
              label="Trang đã đọc"
              value={`${pagesRead}/${pagesTotal || '—'}`}
            />
            <Stat label="Điều khoản" value={String(clauseCount ?? '—')} />
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-gutter">
        <section className="xl:col-span-7 bg-surface-container-lowest rounded-lg p-space-lg shadow-sm">
          <div className="flex items-center gap-space-sm mb-space-md">
            <MaterialIcon
              name="checklist"
              className="text-on-tertiary-container text-[20px]"
            />
            <span className="font-title-sm text-title-sm text-on-surface font-semibold">
              Các bước xử lý
            </span>
          </div>
          <ol className="flex flex-col">
            {RUN_STEPS.map(({ code, ocr }, index) => {
              const row = steps[code]
              const rawStatus = row?.status ?? 'queued'
              // Run đã kết thúc mà BE không ghi nhận bước này thì không để xoay/chờ mãi.
              const status =
                finished && rawStatus !== 'succeeded' && rawStatus !== 'failed'
                  ? 'unrecorded'
                  : rawStatus
              const last = index === RUN_STEPS.length - 1
              return (
                <li key={code} className="flex gap-space-md">
                  <div className="flex flex-col items-center">
                    <StepDot status={status} />
                    {last ? null : (
                      <div
                        className={`w-px flex-1 min-h-4 ${
                          status === 'succeeded'
                            ? 'bg-emerald-300'
                            : 'bg-outline-variant'
                        }`}
                      />
                    )}
                  </div>
                  <div className="flex flex-1 items-start justify-between gap-space-sm pb-space-md">
                    <div className="flex flex-col">
                      <span
                        className={`font-body-sm text-body-sm ${
                          status === 'queued'
                            ? 'text-on-surface-variant'
                            : 'text-on-surface font-semibold'
                        }`}
                      >
                        {RUN_STEP_LABELS[code]}
                      </span>
                      <span className="font-label-sm text-label-sm text-on-surface-variant">
                        {code}
                        {row?.pages != null ? ` · ${row.pages} trang` : ''}
                      </span>
                    </div>
                    <span
                      className={`font-label-sm text-label-sm font-semibold shrink-0 ${
                        status === 'succeeded'
                          ? 'text-emerald-700'
                          : status === 'failed'
                            ? 'text-error'
                            : status === 'running'
                              ? 'text-on-tertiary-container'
                              : 'text-on-surface-variant'
                      }`}
                    >
                      {status === 'succeeded' ? (
                        row?.durationMs != null ? (
                          `Xong · ${(row.durationMs / 1000).toFixed(1)}s`
                        ) : (
                          'Xong'
                        )
                      ) : status === 'running' ? (
                        <StepProgress
                          percent={
                            row?.progress
                              ? stepProgressPercent(row.progress)
                              : ocr
                                ? ocrPercent
                                : null
                          }
                          detail={
                            row?.progress
                              ? formatStepProgress(row.progress)
                              : null
                          }
                        />
                      ) : status === 'failed' ? (
                        'Lỗi'
                      ) : status === 'unrecorded' ? (
                        'Không ghi nhận'
                      ) : (
                        'Chờ'
                      )}
                    </span>
                  </div>
                </li>
              )
            })}
          </ol>
        </section>

        <div className="xl:col-span-5 flex flex-col gap-gutter">
          <section className="bg-surface-container-lowest rounded-lg p-space-lg shadow-sm">
            <div className="flex items-center gap-space-sm mb-space-md">
              <MaterialIcon
                name="history"
                className="text-on-tertiary-container text-[20px]"
              />
              <span className="font-title-sm text-title-sm text-on-surface font-semibold">
                Nhật ký xử lý
              </span>
              <span className="ml-auto font-label-sm text-label-sm text-on-surface-variant">
                Mới nhất ở trên
              </span>
            </div>
            <div className="flex flex-col gap-space-xs max-h-80 overflow-y-auto">
              {logs.length === 0 ? (
                <p className="font-body-sm text-body-sm text-on-surface-variant">
                  Chưa có bước nào được ghi nhận.
                </p>
              ) : (
                [...logs]
                  .reverse()
                  .map((log) => <LogRow key={log.id} log={log} />)
              )}
            </div>
          </section>
        </div>
      </div>

      <div className="mt-gutter pt-space-md flex flex-col md:flex-row items-center justify-between gap-space-md">
        <div className="flex items-center gap-space-md">
          {finished || !canManageRun ? null : (
            <button
              className="font-body-sm text-body-sm text-error hover:underline flex items-center gap-space-xs disabled:opacity-60"
              disabled={busy || !dossierId}
              type="button"
              onClick={() => {
                void cancelJob()
              }}
            >
              <MaterialIcon name="close" className="text-[16px]" />
              <span>Hủy tiến trình này</span>
            </button>
          )}
          {canManageRun && failed && failure.retry !== 'none' ? (
            <button
              className="font-body-sm text-body-sm text-primary hover:underline flex items-center gap-space-xs disabled:opacity-60"
              disabled={busy}
              type="button"
              onClick={() => {
                void retry()
              }}
            >
              <MaterialIcon name="refresh" className="text-[16px]" />
              <span>
                {failure.retry === 'ai2'
                  ? 'Chạy lại phân tích'
                  : 'Đọc lại phần bị lỗi'}
              </span>
            </button>
          ) : null}
        </div>
        <div className="flex items-center gap-space-sm">
          {canDelete ? (
            <button
              className="flex items-center gap-space-sm px-gutter py-space-sm bg-white text-on-surface border border-error/70 rounded-lg font-title-sm text-title-sm shadow-sm transition-all hover:bg-error/5 disabled:opacity-50 disabled:cursor-not-allowed"
              disabled={busy || !dossierId}
              type="button"
              onClick={() => {
                void deleteJob()
              }}
            >
              <MaterialIcon name="delete" className="text-[18px] text-error" />
              <span>Xóa hồ sơ</span>
            </button>
          ) : null}
          <button
            className={`flex items-center gap-space-sm px-gutter py-space-sm bg-white text-on-surface border border-brand-500/70 rounded-lg font-title-sm text-title-sm shadow-sm transition-all ${
              ready
                ? 'hover:bg-brand-500/5 cursor-pointer'
                : 'opacity-50 cursor-not-allowed'
            }`}
            disabled={!ready || !dossierId}
            type="button"
            onClick={() => {
              if (!ready || !dossierId) return
              navigate(structurePath(dossierId), {
                state: mode ? { structureMode: mode } : undefined,
              })
            }}
          >
            <span>Xem hồ sơ</span>
            <MaterialIcon
              name="arrow_forward"
              className="text-[18px] text-brand-700"
            />
          </button>
        </div>
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="p-space-md rounded-lg bg-surface-container-low flex flex-col">
      <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-medium">
        {label}
      </span>
      <span className="font-headline-md text-headline-md text-primary font-bold mt-space-xs">
        {value}
      </span>
    </div>
  )
}

/** Vòng tiến độ của bước đang chạy; không có số % thì vòng quay liên tục. */
function StepProgress({
  percent,
  detail = null,
}: {
  percent: number | null
  detail?: string | null
}) {
  const radius = 9
  const circumference = 2 * Math.PI * radius
  const known = percent !== null
  const filled = known ? percent / 100 : 0.25
  return (
    <span
      aria-label={known ? `Đang chạy ${percent}%` : 'Đang chạy'}
      className="inline-flex items-center gap-1.5"
      role="progressbar"
      aria-valuemax={100}
      aria-valuemin={0}
      aria-valuenow={known ? percent : undefined}
      title={
        detail ??
        (known
          ? `Đã đọc ${percent}% số trang`
          : 'Đang chạy, chưa có số tiến độ')
      }
    >
      <svg
        className={`h-6 w-6 -rotate-90 ${known ? '' : 'animate-spin'}`}
        viewBox="0 0 24 24"
      >
        <circle
          className="text-brand-100"
          cx="12"
          cy="12"
          fill="none"
          r={radius}
          stroke="currentColor"
          strokeWidth="3"
        />
        <circle
          className="text-brand-600 transition-[stroke-dashoffset] duration-500"
          cx="12"
          cy="12"
          fill="none"
          r={radius}
          stroke="currentColor"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - filled)}
          strokeLinecap="round"
          strokeWidth="3"
        />
      </svg>
      {known ? (
        <span className="tabular-nums text-brand-700">{percent}%</span>
      ) : null}
    </span>
  )
}

function StepDot({ status }: { status: string }) {
  if (status === 'succeeded') {
    return (
      <div className="w-6 h-6 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-700 shrink-0">
        <MaterialIcon name="check" className="text-[16px]" />
      </div>
    )
  }
  if (status === 'running') {
    return (
      <div className="w-6 h-6 rounded-full bg-brand-100 flex items-center justify-center text-brand-700 ring-1 ring-brand-200 shrink-0">
        <MaterialIcon
          name="progress_activity"
          className="text-[16px] animate-spin"
        />
      </div>
    )
  }
  if (status === 'failed') {
    return (
      <div className="w-6 h-6 rounded-full bg-error-container flex items-center justify-center text-error shrink-0">
        <MaterialIcon name="error" className="text-[16px]" />
      </div>
    )
  }
  return (
    <div className="w-6 h-6 rounded-full bg-surface-container flex items-center justify-center shrink-0">
      <span className="w-2 h-2 rounded-full bg-outline-variant" />
    </div>
  )
}

function LogRow({ log }: { log: LogRowModel }) {
  return (
    <div
      className={`flex items-center gap-space-sm p-space-sm rounded-lg ${
        log.status === 'active'
          ? 'bg-surface-container-high'
          : 'bg-surface-container-low'
      }`}
    >
      {log.status === 'done' ? (
        <MaterialIcon
          name="check_circle"
          className="text-emerald-700 text-[18px] shrink-0"
        />
      ) : log.status === 'failed' ? (
        <MaterialIcon
          name="error"
          className="text-error text-[18px] shrink-0"
        />
      ) : (
        <MaterialIcon
          name="progress_activity"
          className="text-on-tertiary-container text-[18px] shrink-0 animate-spin"
        />
      )}
      <span className="font-body-sm text-body-sm text-on-surface font-semibold">
        {log.text}
      </span>
    </div>
  )
}
