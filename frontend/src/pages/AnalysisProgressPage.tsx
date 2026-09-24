import { useEffect, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { dossiersLabel, dossiersPath } from '../auth/session'
import { useAuth } from '../auth/useAuth'
import { MaterialIcon } from '../components/icons'
import {
  initialProgressLogs,
  pipelinePhases,
  progressFiles,
  upcomingProgressLogs,
  type PipelinePhase,
  type ProgressFile,
  type ProgressLog,
} from '../data/analysisProgress'
import { useHeaderShowsPageTitle, usePageTitle } from '../hooks/usePageTitle'

type LocationState = {
  name?: string
}

function PhaseCard({ phase }: { phase: PipelinePhase }) {
  const shell =
    phase.status === 'done'
      ? 'bg-surface-container-low'
      : phase.status === 'active'
        ? 'bg-surface-container-high'
        : 'bg-surface-container-lowest opacity-75'

  return (
    <div
      className={`flex flex-col p-space-md rounded-lg transition-all ${shell}`}
    >
      <div className="flex items-center justify-between mb-space-xs">
        <span className="font-title-sm text-title-sm text-on-surface font-bold">
          {phase.title}
        </span>
        {phase.status === 'done' ? (
          <div className="w-5 h-5 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-700">
            <MaterialIcon name="check" className="text-[14px]" />
          </div>
        ) : null}
        {phase.status === 'active' ? (
          <div className="w-5 h-5 rounded-full bg-primary-container flex items-center justify-center text-primary-fixed">
            <MaterialIcon
              name="progress_activity"
              className="text-[14px] animate-spin"
            />
          </div>
        ) : null}
        {phase.status === 'waiting' ? (
          <div className="w-5 h-5 rounded-full bg-surface-container flex items-center justify-center text-on-surface-variant">
            <MaterialIcon
              name={phase.id === 4 ? 'folder_check' : 'hourglass_empty'}
              className="text-[14px]"
            />
          </div>
        ) : null}
      </div>
      {phase.status === 'done' ? (
        <div className="mt-auto flex items-center gap-space-xs">
          <span className="font-label-sm text-label-sm text-emerald-700 font-semibold">
            {phase.detail}
          </span>
        </div>
      ) : null}
      {phase.status === 'active' ? (
        <div className="mt-auto flex items-center justify-between">
          <span className="font-label-sm text-label-sm text-on-tertiary-container font-semibold">
            {phase.detail}
          </span>
          <span className="font-label-sm text-label-sm text-on-surface-variant font-medium">
            {phase.extra}
          </span>
        </div>
      ) : null}
      {phase.status === 'waiting' ? (
        <div className="mt-auto flex items-center">
          <span className="font-label-sm text-label-sm text-on-secondary-container">
            {phase.detail}
          </span>
        </div>
      ) : null}
    </div>
  )
}

function FileRow({ file }: { file: ProgressFile }) {
  const rowClass =
    file.status === 'reading'
      ? 'bg-surface-container-high'
      : file.status === 'waiting'
        ? 'bg-surface-container-low opacity-80'
        : 'bg-surface-container-low'

  return (
    <div
      className={`flex items-center justify-between p-space-md rounded-lg ${rowClass}`}
    >
      <div className="flex items-center gap-space-sm min-w-0">
        {file.status === 'done' ? (
          <MaterialIcon
            name="check_circle"
            className="text-emerald-700 text-[20px] shrink-0"
          />
        ) : null}
        {file.status === 'reading' ? (
          <MaterialIcon
            name="progress_activity"
            className="text-on-tertiary-container text-[20px] animate-spin shrink-0"
          />
        ) : null}
        {file.status === 'waiting' ? (
          <MaterialIcon
            name="schedule"
            className="text-on-surface-variant text-[20px] shrink-0"
          />
        ) : null}
        <span className="font-title-sm text-title-sm text-on-surface truncate font-semibold">
          {file.name}
        </span>
        <span className="text-body-sm text-on-surface-variant">
          {file.meta}
        </span>
      </div>
      {file.status === 'done' ? (
        <span className="font-body-sm text-body-sm text-emerald-800 font-semibold px-space-sm py-0.5 bg-emerald-100 rounded shrink-0">
          {file.label}
        </span>
      ) : file.status === 'reading' ? (
        <span className="font-body-sm text-body-sm text-on-tertiary-container font-semibold px-space-sm py-0.5 bg-surface-container rounded shrink-0">
          {file.label}
        </span>
      ) : (
        <span className="font-body-sm text-body-sm text-on-secondary-container font-semibold px-space-sm py-0.5 bg-surface-container rounded shrink-0">
          {file.label}
        </span>
      )}
    </div>
  )
}

function LogRow({ log }: { log: ProgressLog }) {
  const active = log.status === 'active'
  return (
    <div
      className={`flex items-center gap-space-sm p-space-sm rounded-lg ${
        active ? 'bg-surface-container-high' : 'bg-surface-container-low'
      }`}
    >
      {log.status === 'done' ||
      log.status === 'success' ||
      log.status === 'finish' ? (
        <MaterialIcon
          name="check_circle"
          className="text-emerald-700 text-[18px] shrink-0"
        />
      ) : log.status === 'active' ? (
        <MaterialIcon
          name="progress_activity"
          className="text-on-tertiary-container text-[18px] shrink-0 animate-spin"
        />
      ) : (
        <MaterialIcon
          name="info"
          className="text-on-tertiary-container text-[18px] shrink-0"
        />
      )}
      <span className="font-body-sm text-body-sm text-on-surface font-semibold">
        {log.time} • {log.text}
      </span>
    </div>
  )
}

export function AnalysisProgressPage() {
  usePageTitle('Tiến trình phân tích')
  const titleInHeader = useHeaderShowsPageTitle()
  const { user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const dossierName =
    (location.state as LocationState | null)?.name ??
    'Hợp đồng Tổng thầu EPC - Dự án Đầm Mây'
  const backTo = user ? dossiersPath(user.role) : '/'
  const backLabel = user ? dossiersLabel(user.role) : 'Hồ sơ'

  const [paused, setPaused] = useState(false)
  const [notify, setNotify] = useState(false)
  const [ready, setReady] = useState(false)
  const [logs, setLogs] = useState(initialProgressLogs)
  const pausedRef = useRef(paused)
  pausedRef.current = paused

  useEffect(() => {
    let index = 0
    const interval = window.setInterval(() => {
      if (pausedRef.current) return
      const next = upcomingProgressLogs[index]
      if (!next) {
        window.clearInterval(interval)
        return
      }
      setLogs((current) => [...current, next])
      if (next.status === 'finish') {
        setReady(true)
        window.clearInterval(interval)
      }
      index += 1
    }, 4500)

    return () => window.clearInterval(interval)
  }, [])

  function handleCancel() {
    const confirmed = window.confirm(
      'Bạn có chắc chắn muốn dừng toàn bộ pipeline nạp tệp này? Các phân tích chưa lập chỉ mục sẽ bị hủy.',
    )
    if (confirmed) {
      navigate(backTo)
    }
  }

  return (
    <div className="flex flex-col w-full pb-margin-lg">
      <div className="flex flex-col gap-space-sm pt-space-md mb-gutter">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-space-xs text-on-surface-variant font-label-sm text-label-sm uppercase tracking-wider">
            <Link className="hover:text-primary transition-colors" to={backTo}>
              {backLabel}
            </Link>
            <MaterialIcon name="chevron_right" className="text-[14px]" />
            <span className="text-on-surface font-semibold">
              Tiến trình nạp & phân tích tự động
            </span>
          </div>
          <div className="flex items-center gap-space-sm bg-surface-container-low px-space-md py-space-xs rounded-lg shadow-sm">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-600" />
            </span>
            <span className="font-body-sm text-body-sm text-on-surface font-medium">
              {ready
                ? 'Đã hoàn tất pipeline'
                : paused
                  ? 'Đã tạm dừng pipeline'
                  : 'Đang xử lý tự động • Còn khoảng 1 phút'}
            </span>
          </div>
        </div>

        <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-space-md mt-space-xs">
          <div className="flex flex-col gap-space-xs">
            {titleInHeader ? null : (
              <h1 className="font-headline-lg text-headline-lg text-primary tracking-tight">
                Tiến trình phân tích hợp đồng
              </h1>
            )}
            <div className="flex flex-wrap items-center gap-x-space-md gap-y-space-xs text-on-surface-variant font-body-sm text-body-sm">
              <span className="font-title-sm text-title-sm text-on-surface font-semibold">
                {dossierName}
              </span>
              <span className="text-outline-variant">•</span>
              <span className="bg-surface-container px-space-sm py-0.5 rounded text-on-surface font-medium">
                3 tài liệu
              </span>
              <span className="text-outline-variant">•</span>
              <span>258 trang tài liệu</span>
            </div>
          </div>
          <div className="flex items-center gap-space-sm shrink-0">
            <button
              className="flex items-center gap-space-xs px-space-md py-space-sm bg-surface-container-lowest text-on-surface rounded-lg shadow-sm hover:bg-surface-container transition-colors font-title-sm text-title-sm"
              type="button"
              onClick={() => setPaused((current) => !current)}
            >
              <MaterialIcon
                name={paused ? 'play_arrow' : 'pause'}
                className="text-[18px]"
              />
              <span>{paused ? 'Tiếp tục' : 'Tạm dừng'}</span>
            </button>
            <button
              className={`flex items-center gap-space-xs px-space-md py-space-sm rounded-lg shadow-sm transition-colors font-title-sm text-title-sm ${
                notify
                  ? 'bg-tertiary-container text-primary-fixed'
                  : 'bg-primary-container text-primary-fixed hover:bg-tertiary-container'
              }`}
              type="button"
              onClick={() => setNotify((current) => !current)}
            >
              <MaterialIcon name="notifications" className="text-[18px]" />
              <span>
                {notify
                  ? 'Sẽ thông báo khi hoàn tất'
                  : 'Thông báo khi hoàn tất'}
              </span>
            </button>
          </div>
        </div>
      </div>

      <div className="w-full bg-surface-container-lowest rounded-lg p-gutter shadow-sm mb-gutter">
        <div className="flex items-center justify-between mb-space-md">
          <div className="flex items-center gap-space-sm">
            <MaterialIcon
              name="checklist"
              className="text-on-tertiary-container text-[20px]"
            />
            <span className="font-title-sm text-title-sm text-on-surface font-semibold">
              Các bước xử lý tự động
            </span>
          </div>
          <span className="font-body-sm text-body-sm text-on-tertiary-container font-medium">
            Tiến độ: Đã hoàn thành {ready ? '100%' : '68%'}
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-space-md">
          {pipelinePhases.map((phase) => (
            <PhaseCard key={phase.id} phase={phase} />
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-gutter">
        <div className="xl:col-span-7 flex flex-col gap-gutter">
          <div className="bg-surface-container-lowest rounded-lg p-space-lg shadow-sm">
            <div className="flex items-center justify-between mb-space-md pb-space-sm">
              <div className="flex items-center gap-space-sm">
                <MaterialIcon
                  name="description"
                  className="text-primary text-[20px]"
                />
                <span className="font-title-sm text-title-sm text-on-surface font-semibold">
                  Tiến độ đọc tài liệu hồ sơ
                </span>
              </div>
              <span className="font-label-sm text-label-sm text-on-surface-variant">
                Tự động cập nhật
              </span>
            </div>
            <div className="flex flex-col gap-space-sm">
              {progressFiles.map((file) => (
                <FileRow key={file.id} file={file} />
              ))}
            </div>
          </div>

          <div className="bg-surface-container-lowest rounded-lg p-space-lg shadow-sm flex flex-col">
            <div className="flex items-center justify-between pb-space-sm mb-space-sm">
              <div className="flex items-center gap-space-sm">
                <MaterialIcon
                  name="history"
                  className="text-on-tertiary-container text-[20px]"
                />
                <span className="font-title-sm text-title-sm text-on-surface font-semibold">
                  Nhật ký xử lý chi tiết
                </span>
              </div>
              <span className="font-body-sm text-body-sm text-on-surface-variant">
                Cập nhật theo thời gian thực
              </span>
            </div>
            <div className="flex flex-col gap-space-sm">
              {logs.map((log) => (
                <LogRow key={log.id} log={log} />
              ))}
            </div>
          </div>
        </div>

        <div className="xl:col-span-5 flex flex-col gap-gutter">
          <div className="bg-surface-container-lowest rounded-lg p-space-lg shadow-sm flex flex-col">
            <div className="flex items-center justify-between mb-space-md pb-space-sm">
              <div className="flex items-center gap-space-sm">
                <MaterialIcon
                  name="insights"
                  className="text-primary text-[20px]"
                />
                <span className="font-title-sm text-title-sm text-on-surface font-semibold">
                  Thông tin ghi nhận sớm
                </span>
              </div>
              <span className="font-label-sm text-label-sm text-on-tertiary-container font-semibold bg-surface-container px-space-sm py-0.5 rounded">
                Xem trước
              </span>
            </div>
            <div className="grid grid-cols-2 gap-space-sm mb-space-md">
              <div className="p-space-md rounded-lg bg-surface-container-low flex flex-col">
                <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-medium">
                  Điều khoản
                </span>
                <span className="font-headline-lg text-headline-lg text-primary font-bold mt-space-xs">
                  14
                </span>
              </div>
              <div className="p-space-md rounded-lg bg-surface-container-low flex flex-col">
                <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-medium">
                  Giá trị tạm tính
                </span>
                <span className="font-headline-md text-headline-md text-primary font-bold mt-space-xs truncate">
                  28,45 tỷ VNĐ
                </span>
              </div>
            </div>
            <div className="flex flex-col gap-space-sm mb-space-md">
              <span className="font-label-sm text-label-sm uppercase tracking-wider text-on-surface-variant font-semibold">
                Các bên ký kết
              </span>
              <div className="flex flex-col gap-space-xs">
                <div className="flex items-center justify-between p-space-sm rounded-lg bg-surface-container-low">
                  <span className="font-title-sm text-title-sm text-on-surface font-semibold">
                    Chủ đầu tư
                  </span>
                  <span className="font-body-sm text-body-sm text-on-surface font-semibold">
                    VNPT
                  </span>
                </div>
                <div className="flex items-center justify-between p-space-sm rounded-lg bg-surface-container-low">
                  <span className="font-title-sm text-title-sm text-on-surface font-semibold">
                    Tổng thầu
                  </span>
                  <span className="font-body-sm text-body-sm text-on-surface font-semibold">
                    ApexCorp
                  </span>
                </div>
              </div>
            </div>
            <div className="p-space-md bg-amber-50/80 rounded-lg mb-space-md">
              <div className="flex items-center gap-space-xs text-amber-900 font-title-sm text-title-sm font-semibold">
                <MaterialIcon name="warning" className="text-[18px]" />
                <span>Điều khoản 18: Phạt vi phạm 12% (chuẩn 8%)</span>
              </div>
            </div>
            <div className="mt-auto p-space-sm bg-surface-container-low rounded-lg flex items-center gap-space-sm">
              <MaterialIcon
                name="verified_user"
                className="text-on-tertiary-container text-[18px] shrink-0"
              />
              <span className="font-label-sm text-label-sm text-on-surface-variant font-medium">
                Mã hóa riêng biệt & Bảo mật tuyệt đối
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-gutter pt-space-md flex flex-col md:flex-row items-center justify-between gap-space-md">
        <div className="flex items-center gap-space-md">
          <button
            className="font-body-sm text-body-sm text-error hover:underline flex items-center gap-space-xs"
            type="button"
            onClick={handleCancel}
          >
            <MaterialIcon name="close" className="text-[16px]" />
            <span>Hủy tiến trình này</span>
          </button>
          <span className="text-outline-variant">•</span>
          <button
            className="font-body-sm text-body-sm text-on-surface-variant hover:text-on-surface flex items-center gap-space-xs"
            type="button"
          >
            <MaterialIcon name="help_outline" className="text-[16px]" />
            <span>Hỗ trợ pháp lý & kỹ thuật</span>
          </button>
        </div>
        <div className="flex items-center gap-space-md">
          <button
            className={`flex items-center gap-space-sm px-gutter py-space-sm bg-primary text-on-primary rounded-lg font-title-sm text-title-sm shadow-sm transition-all ${
              ready
                ? 'hover:bg-primary-container cursor-pointer'
                : 'opacity-50 cursor-not-allowed'
            }`}
            disabled={!ready}
            type="button"
            onClick={() => {
              if (ready) navigate('/ho-so-hop-dong')
            }}
          >
            <span>Xem trước hồ sơ</span>
            <MaterialIcon name="arrow_forward" className="text-[18px]" />
          </button>
        </div>
      </div>
    </div>
  )
}
