import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  confirmManifest,
  documentRoles,
  getManifest,
  isDocumentRole,
  isRelationType,
  manifestErrorMessage,
  relationTypes,
  type DocumentRole,
  type Manifest,
  type ManifestConfirmInput,
  type ManifestMember,
  type RelationConfirmation,
  type RelationType,
} from '../api/manifest'
import { ApiError } from '../api/client'
import { dossiersLabel, dossiersPath } from '../auth/session'
import { useAuth } from '../auth/useAuth'
import { MaterialIcon } from '../components/icons'
import { useHeaderShowsPageTitle, usePageTitle } from '../hooks/usePageTitle'

type MemberFilter = 'all' | 'included' | 'excluded'
type RoleFilter = 'all' | DocumentRole
type ConfirmationFilter = 'all' | RelationConfirmation

type DraftRelation = {
  clientKey: string
  id: string | null
  local: boolean
  source_document_id: string
  target_document_id: string
  relation_type: string
  confirmation: RelationConfirmation
}

type Draft = {
  dossier_id: string
  status: 'pending' | 'confirmed'
  version: number
  latest_job_status: string | null
  confirmed_at: string | null
  members: ManifestMember[]
  relations: DraftRelation[]
}

const roleOptions: { value: DocumentRole; label: string }[] = [
  { value: 'contract', label: 'Hợp đồng chính' },
  { value: 'annex', label: 'Phụ lục' },
]

const relationOptions: { value: RelationType; label: string }[] = [
  { value: 'annex_of', label: 'Là phụ lục của' },
  { value: 'amends', label: 'Sửa đổi' },
  { value: 'supersedes', label: 'Thay thế' },
  { value: 'supplements', label: 'Bổ sung' },
]

const dateTime = new Intl.DateTimeFormat('vi-VN', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

function roleLabel(role: string) {
  return (
    roleOptions.find((item) => item.value === role)?.label ??
    (role || 'Chưa có vai trò')
  )
}

function relationLabel(relationType: string) {
  return (
    relationOptions.find((item) => item.value === relationType)?.label ??
    (relationType || 'Chưa có loại')
  )
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatWhen(value: string | null) {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return null
  return dateTime.format(date)
}

function memberMeta(member: ManifestMember) {
  const parts: string[] = []
  if (typeof member.page_count === 'number') {
    parts.push(`${member.page_count} trang`)
  }
  if (typeof member.file_size_bytes === 'number') {
    parts.push(formatSize(member.file_size_bytes))
  }
  return parts.join(' · ')
}

function toDraft(manifest: Manifest): Draft {
  return {
    dossier_id: manifest.dossier_id,
    status: manifest.status,
    version: manifest.version,
    latest_job_status: manifest.latest_job_status ?? null,
    confirmed_at: manifest.confirmed_at ?? null,
    members: [...manifest.members].sort(
      (left, right) => left.order_index - right.order_index,
    ),
    relations: manifest.relations.map((relation, index) => ({
      clientKey: relation.id || `relation-${index}`,
      id: relation.id || null,
      local: false,
      source_document_id: relation.source_document_id,
      target_document_id: relation.target_document_id,
      relation_type: relation.relation_type,
      confirmation: relation.confirmation,
    })),
  }
}

function memberName(members: ManifestMember[], documentId: string) {
  const member = members.find((item) => item.document_id === documentId)
  if (!member) return 'Tài liệu không có trong hồ sơ'
  return member.filename || 'Không có tên tệp'
}

function unconfirmedCount(draft: Draft) {
  return draft.relations.filter(
    (relation) => relation.confirmation === 'unconfirmed',
  ).length
}

function submitBlockReason(draft: Draft) {
  const pending = unconfirmedCount(draft)
  if (pending > 0) {
    return pending === 1
      ? 'Còn 1 quan hệ chưa xác nhận.'
      : `Còn ${pending} quan hệ chưa xác nhận.`
  }
  if (draft.relations.some((relation) => !relation.local && !relation.id)) {
    return 'Có quan hệ thiếu mã. Tải lại trang.'
  }
  if (draft.members.some((member) => !isDocumentRole(member.role))) {
    return 'Chọn vai trò hợp đồng chính hoặc phụ lục cho mọi tài liệu.'
  }
  if (
    !draft.members.some(
      (member) => member.included && member.role === 'contract',
    )
  ) {
    return 'Cần ít nhất một hợp đồng chính thuộc hồ sơ.'
  }

  const seen = new Set<string>()
  for (const relation of draft.relations) {
    if (!isRelationType(relation.relation_type)) {
      return 'Chọn loại quan hệ hợp lệ.'
    }
    if (relation.confirmation === 'rejected') continue
    if (relation.source_document_id === relation.target_document_id) {
      return 'Quan hệ phải nối hai tài liệu khác nhau.'
    }
    const source = draft.members.find(
      (member) => member.document_id === relation.source_document_id,
    )
    const target = draft.members.find(
      (member) => member.document_id === relation.target_document_id,
    )
    if (!source?.included || !target?.included) {
      return 'Quan hệ đã xác nhận phải nối hai tài liệu đang thuộc hồ sơ.'
    }
    const key = [
      relation.source_document_id,
      relation.relation_type,
      relation.target_document_id,
    ].join('|')
    if (seen.has(key)) return 'Có quan hệ bị trùng.'
    seen.add(key)
  }
  return null
}

function confirmInput(draft: Draft): ManifestConfirmInput {
  return {
    version: draft.version,
    members: draft.members.map((member) => {
      if (!isDocumentRole(member.role)) {
        throw new Error(
          'Chọn vai trò hợp đồng chính hoặc phụ lục cho mọi tài liệu.',
        )
      }
      return {
        document_id: member.document_id,
        role: member.role,
        included: member.included,
      }
    }),
    relations: draft.relations.map((relation) => {
      if (relation.confirmation === 'unconfirmed') {
        throw new Error('Còn quan hệ chưa xác nhận.')
      }
      if (!isRelationType(relation.relation_type)) {
        throw new Error('Chọn loại quan hệ hợp lệ.')
      }
      return {
        id: relation.id,
        source_document_id: relation.source_document_id,
        target_document_id: relation.target_document_id,
        relation_type: relation.relation_type,
        confirmation: relation.confirmation,
      }
    }),
  }
}

export function ManifestConfirmPage() {
  usePageTitle('Xác nhận vai trò và quan hệ')
  const titleInHeader = useHeaderShowsPageTitle()
  const { dossierId = '' } = useParams()
  const { user } = useAuth()
  const backTo = user ? dossiersPath(user.role) : '/'
  const backLabel = user ? dossiersLabel(user.role) : 'Hồ sơ'
  const canConfirm =
    user?.backendRole === 'OPERATOR' || user?.backendRole === 'ADMINISTRATOR'

  const [reloadKey, setReloadKey] = useState(0)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [draft, setDraft] = useState<Draft | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [memberQuery, setMemberQuery] = useState('')
  const [roleFilter, setRoleFilter] = useState<RoleFilter>('all')
  const [memberFilter, setMemberFilter] = useState<MemberFilter>('all')
  const [relationQuery, setRelationQuery] = useState('')
  const [confirmationFilter, setConfirmationFilter] =
    useState<ConfirmationFilter>('all')
  const [sourceId, setSourceId] = useState('')
  const [targetId, setTargetId] = useState('')
  const [relationType, setRelationType] = useState<RelationType>('annex_of')
  const [addError, setAddError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError(null)
    setNotice(null)
    setDraft(null)
    setAddError(null)

    getManifest(dossierId, controller.signal)
      .then((manifest) => {
        if (controller.signal.aborted) return
        setDraft(toDraft(manifest))
      })
      .catch((cause: unknown) => {
        const message = manifestErrorMessage(cause)
        if (!message || controller.signal.aborted) return
        setDraft(null)
        setError(message)
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })

    return () => controller.abort()
  }, [dossierId, reloadKey])

  const readOnly = !canConfirm || draft?.status === 'confirmed'
  const pendingRelations = draft ? unconfirmedCount(draft) : 0
  const blockReason = draft && !readOnly ? submitBlockReason(draft) : null

  const filteredMembers = useMemo(() => {
    if (!draft) return []
    const needle = memberQuery.trim().toLowerCase()
    return draft.members.filter((member) => {
      const matchesRole = roleFilter === 'all' || member.role === roleFilter
      const matchesMembership =
        memberFilter === 'all' ||
        (memberFilter === 'included' ? member.included : !member.included)
      const matchesQuery =
        needle.length === 0 ||
        member.filename.toLowerCase().includes(needle) ||
        member.document_id.toLowerCase().includes(needle)
      return matchesRole && matchesMembership && matchesQuery
    })
  }, [draft, memberQuery, roleFilter, memberFilter])

  const filteredRelations = useMemo(() => {
    if (!draft) return []
    const needle = relationQuery.trim().toLowerCase()
    return draft.relations
      .map((relation, index) => ({ relation, index }))
      .filter(({ relation }) => {
        const matchesConfirmation =
          confirmationFilter === 'all' ||
          relation.confirmation === confirmationFilter
        const source = memberName(draft.members, relation.source_document_id)
        const target = memberName(draft.members, relation.target_document_id)
        const matchesQuery =
          needle.length === 0 ||
          source.toLowerCase().includes(needle) ||
          target.toLowerCase().includes(needle) ||
          relationLabel(relation.relation_type).toLowerCase().includes(needle)
        return matchesConfirmation && matchesQuery
      })
      .sort((left, right) => {
        const rank: Record<RelationConfirmation, number> = {
          unconfirmed: 0,
          confirmed: 1,
          rejected: 2,
        }
        const byState =
          rank[left.relation.confirmation] - rank[right.relation.confirmation]
        return byState || left.index - right.index
      })
      .map(({ relation }) => relation)
  }, [draft, relationQuery, confirmationFilter])

  const includedMembers =
    draft?.members.filter((member) => member.included) ?? []

  function updateDraft(updater: (current: Draft) => Draft) {
    setDraft((current) => (current ? updater(current) : current))
  }

  function setIncluded(documentId: string, included: boolean) {
    updateDraft((current) => {
      const members = current.members.map((member) =>
        member.document_id === documentId ? { ...member, included } : member,
      )
      const relations = current.relations.map((relation) => {
        if (relation.confirmation !== 'confirmed') return relation
        const source = members.find(
          (member) => member.document_id === relation.source_document_id,
        )
        const target = members.find(
          (member) => member.document_id === relation.target_document_id,
        )
        if (!source?.included || !target?.included) {
          return { ...relation, confirmation: 'unconfirmed' as const }
        }
        return relation
      })
      return { ...current, members, relations }
    })
  }

  function setMemberRole(documentId: string, role: string) {
    updateDraft((current) => ({
      ...current,
      members: current.members.map((member) =>
        member.document_id === documentId ? { ...member, role } : member,
      ),
    }))
  }

  function setRelationKind(clientKey: string, nextType: string) {
    updateDraft((current) => ({
      ...current,
      relations: current.relations.map((relation) => {
        if (relation.clientKey !== clientKey) return relation
        if (relation.relation_type === nextType) return relation
        return {
          ...relation,
          relation_type: nextType,
          confirmation: relation.local
            ? relation.confirmation
            : ('unconfirmed' as const),
        }
      }),
    }))
  }

  function setConfirmation(
    clientKey: string,
    confirmation: 'confirmed' | 'rejected',
  ) {
    if (!draft) return
    const relation = draft.relations.find(
      (item) => item.clientKey === clientKey,
    )
    if (!relation) return
    if (confirmation === 'confirmed') {
      const source = draft.members.find(
        (member) => member.document_id === relation.source_document_id,
      )
      const target = draft.members.find(
        (member) => member.document_id === relation.target_document_id,
      )
      if (!source?.included || !target?.included) {
        setNotice(null)
        setError(
          'Chọn lại tài liệu thuộc hồ sơ trước khi xác nhận quan hệ này.',
        )
        return
      }
    }
    setError(null)
    updateDraft((current) => ({
      ...current,
      relations: current.relations.map((item) =>
        item.clientKey === clientKey ? { ...item, confirmation } : item,
      ),
    }))
  }

  function removeLocal(clientKey: string) {
    updateDraft((current) => ({
      ...current,
      relations: current.relations.filter(
        (relation) => relation.clientKey !== clientKey,
      ),
    }))
  }

  function addRelation() {
    if (!draft || readOnly) return
    setAddError(null)
    if (!sourceId || !targetId) {
      setAddError('Chọn đủ hai tài liệu.')
      return
    }
    if (sourceId === targetId) {
      setAddError('Chọn hai tài liệu khác nhau.')
      return
    }
    const duplicate = draft.relations.some(
      (relation) =>
        relation.confirmation !== 'rejected' &&
        relation.source_document_id === sourceId &&
        relation.target_document_id === targetId &&
        relation.relation_type === relationType,
    )
    if (duplicate) {
      setAddError('Quan hệ này đã có.')
      return
    }
    updateDraft((current) => ({
      ...current,
      relations: [
        ...current.relations,
        {
          clientKey: crypto.randomUUID(),
          id: null,
          local: true,
          source_document_id: sourceId,
          target_document_id: targetId,
          relation_type: relationType,
          confirmation: 'confirmed',
        },
      ],
    }))
    setSourceId('')
    setTargetId('')
  }

  async function handleConfirm() {
    if (!draft || saving || readOnly) return
    const problem = submitBlockReason(draft)
    if (problem) {
      setNotice(null)
      setError(problem)
      return
    }
    setSaving(true)
    setError(null)
    setNotice(null)
    try {
      const saved = await confirmManifest(dossierId, confirmInput(draft))
      setDraft(toDraft(saved))
      if (saved.status !== 'confirmed') {
        setError('Backend chưa ghi nhận manifest đã xác nhận.')
        return
      }
      setNotice('Đã ghi nhận vai trò và quan hệ. Pipeline phân tích chưa chạy.')
    } catch (cause) {
      const message = manifestErrorMessage(cause)
      if (message) setError(message)
      if (cause instanceof ApiError && cause.status === 409) {
        try {
          const next = await getManifest(dossierId)
          setDraft(toDraft(next))
        } catch (reloadCause) {
          const reloadMessage = manifestErrorMessage(reloadCause)
          if (reloadMessage) setError(reloadMessage)
        }
      }
    } finally {
      setSaving(false)
    }
  }

  const confirmedAt = formatWhen(draft?.confirmed_at ?? null)

  return (
    <div className="flex flex-col w-full pb-margin-lg">
      <div className="flex flex-col gap-space-sm pt-space-md mb-space-xl">
        <nav className="flex items-center gap-space-xs font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">
          <Link className="hover:text-primary transition-colors" to={backTo}>
            {backLabel}
          </Link>
          <MaterialIcon name="chevron_right" className="text-[14px]" />
          <Link
            className="hover:text-primary transition-colors"
            to="/tao-ho-so"
          >
            Tải lên
          </Link>
          <MaterialIcon name="chevron_right" className="text-[14px]" />
          <span className="text-on-surface font-semibold">
            Xác nhận vai trò
          </span>
        </nav>
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-space-md">
          <div className="flex flex-col gap-space-xs max-w-3xl">
            <div className="flex items-center gap-space-sm flex-wrap">
              {titleInHeader ? null : (
                <h1 className="font-headline-lg text-headline-lg text-primary tracking-tight">
                  Xác nhận vai trò và quan hệ
                </h1>
              )}
              {draft ? (
                <span
                  className={`inline-flex items-center gap-1 px-2 py-0.5 rounded font-label-sm text-label-sm font-semibold ${
                    draft.status === 'confirmed'
                      ? 'bg-emerald-100 text-emerald-900'
                      : 'bg-amber-100 text-amber-900'
                  }`}
                >
                  {draft.status === 'confirmed' ? (
                    <MaterialIcon name="check_circle" className="text-[14px]" />
                  ) : (
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-600" />
                  )}
                  {draft.status === 'confirmed'
                    ? 'Đã xác nhận'
                    : 'Chờ xác nhận'}
                </span>
              ) : null}
              {draft?.latest_job_status ? (
                <JobBadge status={draft.latest_job_status} />
              ) : null}
            </div>
            <p className="font-body-md text-body-md text-on-surface-variant">
              Sau khi tải lên, kiểm tra tài liệu thuộc hồ sơ, vai trò từng tệp
              và quan hệ giữa chúng. Quan hệ chưa xác nhận được đánh dấu cho đến
              khi bạn xác nhận hoặc bác bỏ.
            </p>
            <p className="font-code-sm text-code-sm text-on-surface-variant break-all">
              {draft?.dossier_id ?? dossierId}
            </p>
          </div>
        </div>
      </div>

      {user?.backendRole === 'REVIEWER' ? (
        <div className="mb-space-lg px-space-md py-space-sm rounded bg-surface-container text-on-surface font-body-sm text-body-sm">
          Tài khoản thẩm định không xác nhận manifest. Chỉ vận hành và quản trị
          gọi được API này.
        </div>
      ) : null}

      {notice ? (
        <div className="mb-space-lg px-space-lg py-space-md rounded bg-surface-container text-on-surface font-body-sm text-body-sm flex items-start justify-between gap-space-md">
          <span>
            {notice}
            {confirmedAt ? ` Lúc ${confirmedAt}.` : ''}
          </span>
          <button
            aria-label="Đóng thông báo"
            className="text-secondary hover:text-on-surface"
            type="button"
            onClick={() => setNotice(null)}
          >
            <MaterialIcon name="close" className="text-[18px]" />
          </button>
        </div>
      ) : null}

      {error ? (
        <div
          className="mb-space-lg px-space-md py-space-sm rounded bg-error-container text-on-error-container font-body-sm text-body-sm"
          role="alert"
        >
          {error}
        </div>
      ) : null}

      {draft && pendingRelations > 0 ? (
        <div
          className="mb-space-lg px-space-lg py-space-md rounded bg-amber-100 text-amber-900 font-body-sm text-body-sm flex items-start gap-space-sm"
          role="alert"
        >
          <MaterialIcon name="warning" className="text-[18px] shrink-0" />
          <span>
            Còn {pendingRelations} quan hệ chưa xác nhận. Xác nhận hoặc bác bỏ
            từng dòng trong bảng quan hệ trước khi gửi.
          </span>
        </div>
      ) : null}

      {loading && !draft ? (
        <section className="bg-surface-container-lowest rounded shadow-sm px-space-lg py-10 text-secondary font-body-sm text-body-sm">
          Đang tải manifest…
        </section>
      ) : null}

      {!loading && !draft ? (
        <section className="bg-surface-container-lowest rounded shadow-sm px-space-lg py-12">
          <div className="flex flex-col items-center gap-space-sm text-center">
            <MaterialIcon
              name="fact_check"
              className="text-secondary text-[28px]"
            />
            <p className="font-title-sm text-title-sm text-on-surface">
              Chưa tải được manifest
            </p>
            <p className="font-body-sm text-body-sm text-secondary max-w-md">
              Màn này hiện khi backend trả thành viên, vai trò và quan hệ của hồ
              sơ.
            </p>
            <button
              className="mt-space-xs h-10 px-space-lg bg-surface-container-lowest text-on-surface hover:bg-surface-container font-body-sm text-body-sm font-semibold rounded-lg shadow-sm"
              type="button"
              onClick={() => setReloadKey((current) => current + 1)}
            >
              Tải lại
            </button>
          </div>
        </section>
      ) : null}

      {draft ? (
        <div className="flex flex-col gap-space-lg">
          <section className="flex flex-col bg-surface-container-lowest rounded shadow-sm overflow-hidden">
            <div className="p-space-lg flex flex-col lg:flex-row lg:items-center justify-between gap-space-md">
              <div className="flex flex-col gap-space-xs">
                <h2 className="font-headline-md text-headline-md text-on-surface font-semibold">
                  Thành viên hồ sơ
                </h2>
                <p className="font-body-sm text-body-sm text-secondary">
                  Bỏ chọn nếu tệp không thuộc bộ hồ sơ này.
                </p>
              </div>
              <div className="flex items-center gap-space-sm flex-wrap">
                <SearchField
                  label="Tìm tài liệu"
                  placeholder="Tìm theo tên tệp..."
                  value={memberQuery}
                  onChange={setMemberQuery}
                />
                <FilterSelect
                  label="Vai trò tài liệu"
                  value={roleFilter}
                  options={[
                    { value: 'all', label: 'Tất cả vai trò' },
                    ...roleOptions.map((role) => ({
                      value: role.value,
                      label: role.label,
                    })),
                  ]}
                  onChange={(value) => setRoleFilter(value as RoleFilter)}
                />
                <FilterSelect
                  label="Thuộc hồ sơ"
                  value={memberFilter}
                  options={[
                    { value: 'all', label: 'Mọi tư cách' },
                    { value: 'included', label: 'Thuộc hồ sơ' },
                    { value: 'excluded', label: 'Không thuộc hồ sơ' },
                  ]}
                  onChange={(value) => setMemberFilter(value as MemberFilter)}
                />
              </div>
            </div>
            <div className="w-full overflow-x-auto">
              <table className="w-full text-left text-on-surface font-body-sm text-body-sm min-w-[720px]">
                <thead>
                  <tr className="bg-surface-container-low text-secondary font-label-sm text-label-sm uppercase tracking-wider">
                    <th className="py-3 px-space-lg" scope="col">
                      Tài liệu
                    </th>
                    <th className="py-3 px-space-md" scope="col">
                      Vai trò
                    </th>
                    <th className="py-3 px-space-md" scope="col">
                      Thuộc hồ sơ
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-container-low">
                  {draft.members.length === 0 ? (
                    <EmptyRow
                      colSpan={3}
                      icon="description"
                      title="Hồ sơ chưa có tài liệu"
                      body="Manifest chưa có thành viên để xác nhận."
                    />
                  ) : null}
                  {draft.members.length > 0 && filteredMembers.length === 0 ? (
                    <EmptyRow
                      colSpan={3}
                      icon="search"
                      title="Không có tài liệu khớp bộ lọc"
                      body="Đổi từ khóa hoặc bộ lọc vai trò."
                    />
                  ) : null}
                  {filteredMembers.map((member) => (
                    <tr
                      key={member.document_id}
                      className="hover:bg-surface-container-low/60 transition-colors"
                    >
                      <td className="py-3.5 px-space-lg">
                        <div className="flex items-start gap-space-md min-w-0">
                          <div className="w-8 h-8 rounded bg-red-50 text-red-700 flex items-center justify-center shrink-0">
                            <MaterialIcon
                              name="picture_as_pdf"
                              className="text-[18px]"
                            />
                          </div>
                          <div className="flex flex-col min-w-0">
                            <span
                              className={`font-title-sm text-title-sm text-on-surface truncate ${
                                member.included ? '' : 'opacity-75'
                              }`}
                            >
                              {member.filename || 'Không có tên tệp'}
                            </span>
                            <span className="font-code-sm text-code-sm text-secondary truncate">
                              {memberMeta(member) || member.document_id}
                            </span>
                          </div>
                        </div>
                      </td>
                      <td className="py-3.5 px-space-md">
                        <RoleSelect
                          disabled={readOnly || saving}
                          label={`Vai trò của ${member.filename || 'tài liệu'}`}
                          value={member.role}
                          onChange={(role) =>
                            setMemberRole(member.document_id, role)
                          }
                        />
                      </td>
                      <td className="py-3.5 px-space-md">
                        <label className="inline-flex items-center gap-space-sm font-body-sm text-body-sm text-on-surface">
                          <input
                            checked={member.included}
                            className="w-4 h-4 accent-primary-container"
                            disabled={readOnly || saving}
                            type="checkbox"
                            onChange={(event) =>
                              setIncluded(
                                member.document_id,
                                event.target.checked,
                              )
                            }
                          />
                          <span>
                            {member.included
                              ? 'Thuộc hồ sơ'
                              : 'Không thuộc hồ sơ'}
                          </span>
                        </label>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="flex flex-col bg-surface-container-lowest rounded shadow-sm overflow-hidden">
            <div className="p-space-lg flex flex-col lg:flex-row lg:items-center justify-between gap-space-md">
              <div className="flex flex-col gap-space-xs">
                <div className="flex items-center gap-space-sm flex-wrap">
                  <h2 className="font-headline-md text-headline-md text-on-surface font-semibold">
                    Quan hệ tài liệu
                  </h2>
                  {pendingRelations > 0 ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded font-label-sm text-label-sm font-semibold bg-amber-100 text-amber-900">
                      <MaterialIcon name="warning" className="text-[14px]" />
                      {pendingRelations} chưa xác nhận
                    </span>
                  ) : null}
                </div>
                <p className="font-body-sm text-body-sm text-secondary">
                  Quan hệ do hệ thống đề xuất ở trạng thái chưa xác nhận cho đến
                  khi bạn xác nhận hoặc bác bỏ.
                </p>
              </div>
              <div className="flex items-center gap-space-sm flex-wrap">
                <SearchField
                  label="Tìm quan hệ"
                  placeholder="Tìm theo tên tệp..."
                  value={relationQuery}
                  onChange={setRelationQuery}
                />
                <FilterSelect
                  label="Trạng thái quan hệ"
                  value={confirmationFilter}
                  options={[
                    { value: 'all', label: 'Tất cả trạng thái' },
                    { value: 'unconfirmed', label: 'Chưa xác nhận' },
                    { value: 'confirmed', label: 'Đã xác nhận' },
                    { value: 'rejected', label: 'Đã bác bỏ' },
                  ]}
                  onChange={(value) =>
                    setConfirmationFilter(value as ConfirmationFilter)
                  }
                />
              </div>
            </div>
            <div className="w-full overflow-x-auto">
              <table className="w-full text-left text-on-surface font-body-sm text-body-sm min-w-[880px]">
                <thead>
                  <tr className="bg-surface-container-low text-secondary font-label-sm text-label-sm uppercase tracking-wider">
                    <th className="py-3 px-space-lg" scope="col">
                      Từ tài liệu
                    </th>
                    <th className="py-3 px-space-md" scope="col">
                      Quan hệ
                    </th>
                    <th className="py-3 px-space-md" scope="col">
                      Đến tài liệu
                    </th>
                    <th className="py-3 px-space-md" scope="col">
                      Trạng thái
                    </th>
                    <th className="py-3 px-space-md text-right" scope="col">
                      Thao tác
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-container-low">
                  {draft.relations.length === 0 ? (
                    <EmptyRow
                      colSpan={5}
                      icon="account_tree"
                      title="Chưa có quan hệ giữa các tài liệu"
                      body="Có thể xác nhận manifest khi vai trò tài liệu đã đúng."
                    />
                  ) : null}
                  {draft.relations.length > 0 &&
                  filteredRelations.length === 0 ? (
                    <EmptyRow
                      colSpan={5}
                      icon="search"
                      title="Không có quan hệ khớp bộ lọc"
                      body="Đổi từ khóa hoặc trạng thái."
                    />
                  ) : null}
                  {filteredRelations.map((relation) => {
                    const sourceName = memberName(
                      draft.members,
                      relation.source_document_id,
                    )
                    const targetName = memberName(
                      draft.members,
                      relation.target_document_id,
                    )
                    const unconfirmed = relation.confirmation === 'unconfirmed'
                    return (
                      <tr
                        key={relation.clientKey}
                        className={
                          unconfirmed
                            ? 'bg-amber-100/50'
                            : 'hover:bg-surface-container-low/60 transition-colors'
                        }
                        data-confirmation={relation.confirmation}
                        data-relation-type={relation.relation_type}
                      >
                        <td className="py-3.5 px-space-lg">
                          <span className="font-title-sm text-title-sm text-on-surface">
                            {sourceName}
                          </span>
                        </td>
                        <td className="py-3.5 px-space-md">
                          <RelationTypeSelect
                            disabled={readOnly || saving}
                            label={`Loại quan hệ từ ${sourceName} tới ${targetName}`}
                            value={relation.relation_type}
                            onChange={(next) =>
                              setRelationKind(relation.clientKey, next)
                            }
                          />
                        </td>
                        <td className="py-3.5 px-space-md">
                          <span className="font-title-sm text-title-sm text-on-surface">
                            {targetName}
                          </span>
                        </td>
                        <td className="py-3.5 px-space-md">
                          <ConfirmationBadge
                            confirmation={relation.confirmation}
                          />
                        </td>
                        <td className="py-3.5 px-space-md">
                          {readOnly ? null : (
                            <div className="flex items-center justify-end gap-space-xs">
                              {relation.local &&
                              relation.confirmation === 'confirmed' ? null : (
                                <button
                                  className={actionClass(
                                    relation.confirmation === 'confirmed',
                                  )}
                                  disabled={saving}
                                  type="button"
                                  onClick={() =>
                                    setConfirmation(
                                      relation.clientKey,
                                      'confirmed',
                                    )
                                  }
                                >
                                  Xác nhận
                                </button>
                              )}
                              {relation.local ? (
                                <button
                                  className="h-8 px-space-sm rounded text-secondary hover:bg-surface-container hover:text-on-surface font-label-sm text-label-sm disabled:opacity-50"
                                  disabled={saving}
                                  type="button"
                                  onClick={() =>
                                    removeLocal(relation.clientKey)
                                  }
                                >
                                  Gỡ
                                </button>
                              ) : (
                                <button
                                  className={actionClass(
                                    relation.confirmation === 'rejected',
                                  )}
                                  disabled={saving}
                                  type="button"
                                  onClick={() =>
                                    setConfirmation(
                                      relation.clientKey,
                                      'rejected',
                                    )
                                  }
                                >
                                  Bác bỏ
                                </button>
                              )}
                            </div>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            {!readOnly ? (
              <div className="p-space-lg flex flex-col gap-space-sm border-t border-surface-container-low">
                {includedMembers.length < 2 ? (
                  <p className="font-body-sm text-body-sm text-secondary">
                    Cần ít nhất hai tài liệu thuộc hồ sơ để thêm quan hệ.
                  </p>
                ) : (
                  <div className="flex flex-col lg:flex-row lg:items-end gap-space-sm">
                    <MemberPick
                      label="Từ tài liệu"
                      members={includedMembers}
                      value={sourceId}
                      onChange={setSourceId}
                    />
                    <div className="flex flex-col gap-space-xs">
                      <span className="font-label-sm text-label-sm text-secondary uppercase tracking-wider">
                        Quan hệ
                      </span>
                      <FilterSelect
                        label="Loại quan hệ mới"
                        value={relationType}
                        options={relationOptions.map((item) => ({
                          value: item.value,
                          label: item.label,
                        }))}
                        onChange={(value) =>
                          setRelationType(value as RelationType)
                        }
                      />
                    </div>
                    <MemberPick
                      label="Đến tài liệu"
                      members={includedMembers}
                      value={targetId}
                      onChange={setTargetId}
                    />
                    <button
                      className="h-9 px-space-md rounded bg-surface-container text-on-surface hover:bg-surface-container-high font-label-sm text-label-sm disabled:opacity-50"
                      disabled={saving}
                      type="button"
                      onClick={addRelation}
                    >
                      Thêm quan hệ
                    </button>
                  </div>
                )}
                {addError ? (
                  <p
                    className="font-body-sm text-body-sm text-error"
                    role="alert"
                  >
                    {addError}
                  </p>
                ) : null}
              </div>
            ) : null}
          </section>

          <div className="sticky bottom-4 p-space-lg bg-surface-container-lowest rounded-xl shadow-xl z-30 flex flex-col md:flex-row md:items-center justify-between gap-space-md">
            <p className="font-body-sm text-body-sm text-on-surface-variant">
              {readOnly
                ? draft.status === 'confirmed'
                  ? 'Manifest đã được ghi nhận. Pipeline phân tích chưa chạy từ màn này.'
                  : 'Chỉ vận hành và quản trị gửi được xác nhận.'
                : (blockReason ??
                  'Gửi xác nhận lên backend. Pipeline phân tích chưa chạy.')}
            </p>
            <div className="flex items-center justify-end gap-space-md">
              <Link
                className="h-10 px-space-lg font-body-sm text-body-sm font-medium text-on-surface-variant hover:text-primary transition-colors rounded-lg hover:bg-surface-container-low flex items-center"
                to={backTo}
              >
                Về {backLabel.toLowerCase()}
              </Link>
              {readOnly ? null : (
                <button
                  className="h-10 px-space-lg bg-primary text-on-primary hover:bg-primary-container active:bg-tertiary transition-all font-body-sm text-body-sm font-semibold rounded-lg shadow-sm flex items-center gap-space-sm disabled:opacity-80"
                  disabled={saving || Boolean(blockReason)}
                  type="button"
                  onClick={() => {
                    void handleConfirm()
                  }}
                >
                  <MaterialIcon name="fact_check" className="text-[18px]" />
                  <span>{saving ? 'Đang gửi…' : 'Xác nhận manifest'}</span>
                </button>
              )}
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}

function JobBadge({ status }: { status: string }) {
  const uploaded = status === 'uploaded'
  const processing = status === 'processing'
  const label = uploaded ? 'UPLOADED' : processing ? 'Đang xử lý' : status
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded font-label-sm text-label-sm font-semibold ${
        uploaded || processing
          ? 'bg-amber-100 text-amber-900'
          : 'bg-surface-container text-on-surface'
      }`}
    >
      {uploaded || processing ? (
        <span className="w-1.5 h-1.5 rounded-full bg-amber-600" />
      ) : null}
      {label}
    </span>
  )
}

function ConfirmationBadge({
  confirmation,
}: {
  confirmation: RelationConfirmation
}) {
  if (confirmation === 'unconfirmed') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded font-label-sm text-label-sm font-semibold bg-amber-100 text-amber-900">
        <MaterialIcon name="warning" className="text-[14px]" />
        Chưa xác nhận
      </span>
    )
  }
  if (confirmation === 'rejected') {
    return (
      <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-surface-container-high text-secondary font-label-sm text-label-sm">
        <span className="w-1.5 h-1.5 rounded-full bg-outline" />
        Đã bác bỏ
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded font-label-sm text-label-sm font-semibold bg-emerald-100 text-emerald-900">
      <MaterialIcon name="check_circle" className="text-[14px]" />
      Đã xác nhận
    </span>
  )
}

function actionClass(active: boolean) {
  return active
    ? 'h-8 px-space-sm rounded bg-primary text-on-primary font-label-sm text-label-sm font-semibold'
    : 'h-8 px-space-sm rounded text-secondary hover:bg-surface-container hover:text-on-surface font-label-sm text-label-sm disabled:opacity-50'
}

function EmptyRow({
  colSpan,
  icon,
  title,
  body,
}: {
  colSpan: number
  icon: string
  title: string
  body: string
}) {
  return (
    <tr>
      <td className="py-12 px-space-lg" colSpan={colSpan}>
        <div className="flex flex-col items-center gap-space-sm text-center">
          <MaterialIcon name={icon} className="text-secondary text-[28px]" />
          <p className="font-title-sm text-title-sm text-on-surface">{title}</p>
          <p className="font-body-sm text-body-sm text-secondary max-w-md">
            {body}
          </p>
        </div>
      </td>
    </tr>
  )
}

function SearchField({
  label,
  placeholder,
  value,
  onChange,
}: {
  label: string
  placeholder: string
  value: string
  onChange: (value: string) => void
}) {
  return (
    <div className="relative flex items-center">
      <MaterialIcon
        name="search"
        className="absolute left-2.5 text-secondary text-[16px]"
      />
      <input
        aria-label={label}
        className="pl-8 pr-space-md py-1.5 bg-surface-container text-on-surface rounded font-body-sm text-body-sm placeholder:text-outline focus:outline-none focus:bg-surface-container-lowest focus:ring-1 focus:ring-secondary w-52 sm:w-64"
        placeholder={placeholder}
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  )
}

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: string
  options: { value: string; label: string }[]
  onChange: (value: string) => void
}) {
  return (
    <div className="relative">
      <select
        aria-label={label}
        className="appearance-none bg-surface-container text-on-surface font-body-sm text-body-sm py-1.5 pl-3 pr-8 rounded focus:outline-none cursor-pointer disabled:opacity-60"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <MaterialIcon
        name="expand_more"
        className="absolute right-2 top-2 pointer-events-none text-secondary text-[16px]"
      />
    </div>
  )
}

function RoleSelect({
  label,
  value,
  disabled,
  onChange,
}: {
  label: string
  value: string
  disabled: boolean
  onChange: (value: string) => void
}) {
  const known = (documentRoles as readonly string[]).includes(value)
  return (
    <div className="relative inline-flex">
      <select
        aria-label={label}
        className="appearance-none bg-surface-container text-on-surface font-body-sm text-body-sm py-1.5 pl-3 pr-8 rounded focus:outline-none focus:ring-1 focus:ring-secondary disabled:opacity-60 disabled:cursor-not-allowed"
        disabled={disabled}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {known ? null : <option value={value}>{roleLabel(value)}</option>}
        {roleOptions.map((role) => (
          <option key={role.value} value={role.value}>
            {role.label}
          </option>
        ))}
      </select>
      <MaterialIcon
        name="expand_more"
        className="absolute right-2 top-2 pointer-events-none text-secondary text-[16px]"
      />
    </div>
  )
}

function RelationTypeSelect({
  label,
  value,
  disabled,
  onChange,
}: {
  label: string
  value: string
  disabled: boolean
  onChange: (value: string) => void
}) {
  const known = (relationTypes as readonly string[]).includes(value)
  return (
    <div className="relative inline-flex">
      <select
        aria-label={label}
        className="appearance-none bg-surface-container text-on-surface font-body-sm text-body-sm py-1.5 pl-3 pr-8 rounded focus:outline-none focus:ring-1 focus:ring-secondary disabled:opacity-60 disabled:cursor-not-allowed"
        disabled={disabled}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      >
        {known ? null : <option value={value}>{relationLabel(value)}</option>}
        {relationOptions.map((item) => (
          <option key={item.value} value={item.value}>
            {item.label}
          </option>
        ))}
      </select>
      <MaterialIcon
        name="expand_more"
        className="absolute right-2 top-2 pointer-events-none text-secondary text-[16px]"
      />
    </div>
  )
}

function MemberPick({
  label,
  members,
  value,
  onChange,
}: {
  label: string
  members: ManifestMember[]
  value: string
  onChange: (value: string) => void
}) {
  const selected = members.some((member) => member.document_id === value)
    ? value
    : ''
  return (
    <div className="flex flex-col gap-space-xs min-w-[220px]">
      <label className="font-label-sm text-label-sm text-secondary uppercase tracking-wider">
        {label}
      </label>
      <div className="relative">
        <select
          aria-label={label}
          className="w-full appearance-none bg-surface-container text-on-surface font-body-sm text-body-sm py-1.5 pl-3 pr-8 rounded focus:outline-none cursor-pointer"
          value={selected}
          onChange={(event) => onChange(event.target.value)}
        >
          <option value="">Chọn tài liệu</option>
          {members.map((member) => (
            <option key={member.document_id} value={member.document_id}>
              {member.filename || member.document_id}
            </option>
          ))}
        </select>
        <MaterialIcon
          name="expand_more"
          className="absolute right-2 top-2 pointer-events-none text-secondary text-[16px]"
        />
      </div>
    </div>
  )
}
