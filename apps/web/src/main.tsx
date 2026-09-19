import React, {useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';

type Dossier = {id: string; title: string; status: string; active_job_id: string | null};
type Confidence = {score: number | null; calibrated: boolean; review_priority: string; signals: Record<string, boolean>};
type Fact = {id: string; type: string; raw: string; normalized: unknown; citation_ids: string[]; confidence: Confidence};
type Finding = {id: string; topic: string; disposition: string; rationale: string; citations_a: string[]; citations_b: string[]};
type Citation = {id: string; quote: string; page_number: number; bbox: number[]; page_url: string};
type DocumentInfo = {id: string; role: 'contract' | 'appendix'; page_count: number; sha256: string};
type PageLine = {id: string; text: string; bbox: number[]};
type PageText = {engine: string; status: string; issue: string | null; lines: PageLine[]};
type AuditEvent = {id: string; actor: string; action: string; object_type: string; object_id: string;
  request_id: string | null; result: string; detail: Record<string, unknown>; created_at: number};
type TableSource = {table_id: string; document_id: string; page_number: number;
  row_index: number; col_index: number; bbox: number[]; text: string};
type TableCell = {col_index: number; text: string; bbox: number[]; sources: TableSource[]};
type TableInfo = {id: string; document_id: string; page_start: number; page_end: number;
  col_count: number; fragment_ids: string[]; status: 'RECONSTRUCTED' | 'NEEDS_REVIEW' | 'STANDALONE';
  rows: {kind: string; cells: TableCell[]}[]};

type ClauseNode = {id: string; type: 'article' | 'clause' | 'point' | 'fragment'; label: string;
  parent_id: string | null; document_id: string; citation_ids: string[]};

const CLAUSE_TYPE_LABEL: Record<ClauseNode['type'], string> = {
  article: 'Điều', clause: 'Khoản', point: 'Điểm', fragment: '',
};
// Beyond this many characters a node's text collapses behind "…", since a merged
// fragment (structure.py joins wrapped-line sentences back together) or a long
// clause body otherwise dominates the tree and buries its siblings.
const CLAUSE_TEXT_COLLAPSE_LENGTH = 160;

// Renders one level of the Điều → Khoản → Điểm tree and recurses into children,
// like a folder browser: a node with children starts collapsed and only renders
// its own subtree once `openIds` marks it open, so opening "Điều 5" doesn't dump
// every Khoản/Điểm underneath every other Điều onto the screen at once. Long text
// collapses behind "…" (toggle with the "expandedIds" set, independent of the
// open/closed tree state) so a single long clause doesn't push its siblings out of
// view; a node merged from more than one source line (structure.py's
// fragment-wrap merge) gets one "Nguồn N" link per contributing line.
function renderClauseTree(
  nodes: ClauseNode[], parentId: string | null, activeCitationId: string | undefined,
  onSelect: (citationId: string) => void,
  expandedIds: Set<string>, onToggleExpand: (id: string) => void,
  openIds: Set<string>, onToggleOpen: (id: string) => void,
): React.ReactNode {
  const children = nodes.filter(n => n.parent_id === parentId);
  if (children.length === 0) return null;
  return <ul className={parentId === null ? 'clause-tree' : undefined}>{children.map(n => {
    const citationId = n.citation_ids[0];
    const expanded = expandedIds.has(n.id);
    const collapsible = n.label.length > CLAUSE_TEXT_COLLAPSE_LENGTH;
    const shownLabel = collapsible && !expanded ? `${n.label.slice(0, CLAUSE_TEXT_COLLAPSE_LENGTH).trimEnd()}…` : n.label;
    const nodeChildren = nodes.filter(c => c.parent_id === n.id);
    const hasChildren = nodeChildren.length > 0;
    const open = openIds.has(n.id);
    return <li key={n.id} className={n.type}>
      <div className="clause-row">
        {hasChildren && <button type="button" className="clause-toggle" aria-expanded={open}
          aria-label={open ? 'Thu gọn mục này' : 'Mở rộng để xem bên trong'}
          onClick={() => onToggleOpen(n.id)}>{open ? '▾' : '▸'}</button>}
        <button type="button" className={`clause-label ${citationId === activeCitationId ? 'active' : ''}`}
          onClick={() => onSelect(citationId)}>
          {CLAUSE_TYPE_LABEL[n.type] && <b>{CLAUSE_TYPE_LABEL[n.type]}</b>} {shownLabel}
          {hasChildren && <span className="child-count">{nodeChildren.length}</span>}
        </button>
      </div>
      <div className="clause-meta">
        {collapsible && <button type="button" className="link small" onClick={() => onToggleExpand(n.id)}>{expanded ? 'Thu gọn' : 'Xem đầy đủ'}</button>}
        {n.citation_ids.length > 1 && n.citation_ids.map((id, i) =>
          <button type="button" className="link small" key={id} onClick={() => onSelect(id)}>Nguồn {i + 1}</button>)}
      </div>
      {hasChildren && open && renderClauseTree(nodes, n.id, activeCitationId, onSelect, expandedIds, onToggleExpand, openIds, onToggleOpen)}
    </li>;
  })}</ul>;
}

// Mirrors the 11-stage pipeline in docs/architecture.md. `group` maps to the coarse
// job.status values the backend actually exposes — the API doesn't track finer-grained
// per-stage progress, so rows within a group always share one state (done/active/pending).
const PIPELINE: {no: string; name: string; does: string; invariant: string; group: 'A' | 'B' | 'C' | 'D' | 'E'}[] = [
  {no: '01', name: 'Ingest', does: 'PDF → tài liệu bất biến + manifest', invariant: 'Đúng một hợp đồng; MIME/header/parser hợp lệ', group: 'A'},
  {no: '02', name: 'Inspect', does: 'Tài liệu → metadata/loại trang', invariant: 'Trang mã hoá/hỏng bị báo lỗi có mã', group: 'B'},
  {no: '03', name: 'Render', does: 'Trang → ảnh canonical + transform', invariant: 'Giới hạn timeout & pixel; không tải cả tài liệu vào RAM', group: 'B'},
  {no: '04', name: 'Extract', does: 'Native/scan/mixed → text + ứng viên word/line', invariant: 'Policy AI, quota, schema, độ đầy đủ', group: 'B'},
  {no: '05', name: 'Align', does: 'Text + hình học → evidence anchors', invariant: 'Không khớp phải giữ cảnh báo/ứng viên chưa neo', group: 'B'},
  {no: '06', name: 'Structure', does: 'Anchors → điều khoản/bảng/ô', invariant: 'Parent/trang/span hợp lệ; giữ fragment qua trang', group: 'B'},
  {no: '07', name: 'Facts', does: 'Node → fact có kiểu + ngữ cảnh + trích dẫn', invariant: 'Kiểm tra chuẩn hoá, nguồn và tính mơ hồ', group: 'C'},
  {no: '08', name: 'Link', does: 'Manifest + metadata → quan hệ phụ lục', invariant: 'Quan hệ mơ hồ cần reviewer xác nhận', group: 'C'},
  {no: '09', name: 'Compare', does: 'Ứng viên fact/điều khoản → phát hiện', invariant: 'Đủ phạm vi/ngữ cảnh/bằng chứng cả hai phía', group: 'C'},
  {no: '10', name: 'Validate', does: 'Kết quả run → cờ coverage/chất lượng', invariant: 'Không publish bằng chứng giả hoặc bỏ trang âm thầm', group: 'D'},
  {no: '11', name: 'Publish', does: 'Run đã staged → kết quả bất biến', invariant: 'Transaction atomic; trạng thái review rõ ràng', group: 'E'},
];

const DISPOSITION_LABEL: Record<string, string> = {
  comparable_match: 'Khớp',
  comparable_difference: 'Khác biệt',
  candidate_amendment: 'Nghi ngờ sửa đổi',
  not_comparable: 'Không so sánh được',
  insufficient_evidence: 'Chưa đủ evidence',
};

// Translates the backend's raw job-status enum into a short Vietnamese label plus a
// visual "tone" so the sidebar and detail header never show a bare technical word
// like "pending_review" to someone who isn't reading the source code.
type StatusTone = 'pending' | 'active' | 'done' | 'failed';
const DOSSIER_STATUS_LABEL: Record<string, {label: string; tone: StatusTone}> = {
  uploaded: {label: 'Đã tải lên', tone: 'pending'},
  processing: {label: 'Đang xử lý', tone: 'active'},
  extracted: {label: 'Đã trích xuất', tone: 'active'},
  pending_review: {label: 'Chờ review', tone: 'pending'},
  reviewed: {label: 'Đã review', tone: 'done'},
  approved: {label: 'Đã phê duyệt', tone: 'done'},
  failed: {label: 'Lỗi xử lý', tone: 'failed'},
};
function StatusBadge({status}: {status: string}) {
  const info = DOSSIER_STATUS_LABEL[status] ?? {label: status, tone: 'pending' as StatusTone};
  return <span className={`status-badge ${info.tone}`}>{info.label}</span>;
}

function stageState(status: string | undefined, group: 'A' | 'B' | 'C' | 'D' | 'E'): 'done' | 'active' | 'failed' | 'pending' {
  if (!status) return 'pending';
  if (status === 'failed') return group === 'A' ? 'done' : group === 'B' ? 'failed' : 'pending';
  const rank: Record<string, number> = {uploaded: 1, processing: 2, extracted: 3, pending_review: 4, reviewed: 5, approved: 6};
  const thresholds: Record<'A' | 'B' | 'C' | 'D' | 'E', [number, number]> = {A: [0, 1], B: [2, 3], C: [3, 4], D: [4, 5], E: [6, 6]};
  const current = rank[status] ?? 0;
  const [activeAt, doneAt] = thresholds[group];
  if (current >= doneAt) return 'done';
  if (current === activeAt) return 'active';
  return 'pending';
}
type Result = {
  status: string; review_version: number;
  effective: Result['machine'];
  machine: {run_id: string; is_partial: boolean; facts: Fact[]; findings: Finding[];
    issues: {code: string; page_number: number}[]; coverage: {expected_pages: number; completed_pages: number; failed_pages: number}};
  review: {blocked: boolean; stale: boolean; unresolved: string[];
    history: {id: string; target_id: string; action: string; actor: string; reason: string; correction: unknown; version: number}[]};
};

type JobProgress = {id: string; status: string; failure_code: string | null; attempts: number;
  progress: {total: number; completed: number; failed: number}};

type DetailTab = 'facts' | 'findings' | 'history';
type SourceTab = 'overview' | 'structure' | 'fulltext' | 'tables' | 'evidence';

function App() {
  const [dossiers, setDossiers] = useState<Dossier[]>([]);
  const [selected, setSelected] = useState<Dossier | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [jobProgress, setJobProgress] = useState<JobProgress | null>(null);
  const [jobError, setJobError] = useState('');
  const [view, setView] = useState<'effective' | 'machine'>('effective');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [title, setTitle] = useState('');
  const [contract, setContract] = useState<File | null>(null);
  const [annexes, setAnnexes] = useState<File[]>([]);
  const [citation, setCitation] = useState<Citation | null>(null);
  const [image, setImage] = useState('');
  const [reviewTarget, setReviewTarget] = useState('');
  const [action, setAction] = useState('confirm');
  const [reason, setReason] = useState('');
  const [correction, setCorrection] = useState('');
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [activeDocId, setActiveDocId] = useState('');
  const [originalFile, setOriginalFile] = useState('');
  const [pageNum, setPageNum] = useState(1);
  const [pageText, setPageText] = useState<PageText | null>(null);
  const [pageLoading, setPageLoading] = useState(false);
  const [pageError, setPageError] = useState('');
  const [auditTrail, setAuditTrail] = useState<AuditEvent[]>([]);
  const [tables, setTables] = useState<TableInfo[]>([]);
  const [clauseTree, setClauseTree] = useState<ClauseNode[]>([]);
  const [expandedClauseIds, setExpandedClauseIds] = useState<Set<string>>(new Set());
  const [openClauseIds, setOpenClauseIds] = useState<Set<string>>(new Set());
  const [activeTableCellKey, setActiveTableCellKey] = useState('');
  const [detailTab, setDetailTab] = useState<DetailTab>('facts');
  const [sourceTab, setSourceTab] = useState<SourceTab>('overview');
  function toggleClauseExpanded(id: string) {
    setExpandedClauseIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }
  function toggleClauseOpen(id: string) {
    setOpenClauseIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  async function api(path: string, method = 'GET', body?: unknown) {
    const headers: Record<string, string> = {};
    if (method !== 'GET') headers['Idempotency-Key'] = crypto.randomUUID();
    if (body && !(body instanceof FormData)) headers['Content-Type'] = 'application/json';
    const response = await fetch(`/api/v1${path}`, {method, headers,
      body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error?.code ?? `HTTP ${response.status}`);
    return data;
  }
  async function apiBlob(path: string) {
    const response = await fetch(`/api/v1${path}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return URL.createObjectURL(await response.blob());
  }
  async function perform(task: () => Promise<void>) {
    setBusy(true); setError('');
    try {await task();} catch (e) {setError(e instanceof Error ? e.message : String(e));}
    finally {setBusy(false);}
  }
  async function refresh() {
    setDossiers((await api('/dossiers')).items);
  }
  async function open(dossier: Dossier) {
    setSelected(dossier); setResult(null); setCitation(null); setImage(''); setReviewTarget('');
    setTables([]); setClauseTree([]); setPageText(null); setJobProgress(null); setJobError('');
    setDetailTab('facts'); setSourceTab('overview'); setOpenClauseIds(new Set());
    const docs = (await api(`/dossiers/${dossier.id}/documents`)).items as DocumentInfo[];
    setDocuments(docs);
    setActiveDocId((docs.find(d => d.role === 'contract') ?? docs[0])?.id ?? '');
    setAuditTrail((await api(`/dossiers/${dossier.id}/audit`)).items);
    if (['pending_review', 'reviewed', 'approved', 'failed'].includes(dossier.status)) {
      try {setResult(await api(`/dossiers/${dossier.id}/results`));}
      catch (e) {if (!(e instanceof Error) || e.message !== 'RESULT_NOT_READY') throw e;}
    }
  }
  useEffect(() => {perform(refresh);}, []);
  useEffect(() => {
    const timer = setInterval(() => {
      api('/dossiers').then(data => {
        setDossiers(data.items);
        const current = data.items.find((d: Dossier) => d.id === selected?.id);
        if (current && (current.status !== selected?.status || current.active_job_id !== selected?.active_job_id)) {
          open(current).catch(e => setError(e.message));
        }
      }).catch(e => setError(e.message));
    }, 3000);
    return () => clearInterval(timer);
  }, [selected]);
  useEffect(() => {
    let cancelled = false;
    const jobId = selected?.active_job_id;
    if (!jobId) return;
    async function pollProgress() {
      try {
        const progress = await api(`/jobs/${jobId}`) as JobProgress;
        if (!cancelled) {setJobProgress(progress); setJobError('');}
      } catch (e) {
        if (!cancelled) setJobError(e instanceof Error ? e.message : String(e));
      }
    }
    pollProgress();
    const timer = setInterval(pollProgress, 3000);
    return () => {cancelled = true; clearInterval(timer);};
  }, [selected?.active_job_id, selected?.status]);
  useEffect(() => {
    // Selecting a citation (e.g. from a fact's "Nguồn" link) should reveal that
    // clause in the tree even if its ancestor "Điều"/"Khoản" is currently collapsed —
    // otherwise the newly active row is invisible and looks like nothing happened.
    if (!citation) return;
    const node = clauseTree.find(n => n.citation_ids.includes(citation.id));
    if (!node) return;
    setOpenClauseIds(prev => {
      const next = new Set(prev);
      let current: ClauseNode | undefined = node;
      while (current?.parent_id) {
        next.add(current.parent_id);
        current = clauseTree.find(n => n.id === current!.parent_id);
      }
      return next;
    });
  }, [citation, clauseTree]);
  useEffect(() => () => {if (image) URL.revokeObjectURL(image);}, [image]);
  useEffect(() => () => {if (originalFile) URL.revokeObjectURL(originalFile);}, [originalFile]);
  useEffect(() => {
    setPageNum(1); setPageText(null); setPageError('');
    if (!activeDocId) {setOriginalFile(''); return;}
    apiBlob(`/documents/${activeDocId}/file`).then(setOriginalFile).catch(e => setError(e.message));
  }, [activeDocId]);
  useEffect(() => {
    if (!result || !activeDocId || !selected) return;
    loadPageText(1);
    api(`/dossiers/${selected.id}/tables`).then(d => setTables(d.logical_items ?? [])).catch(e => setError(e.message));
    api(`/dossiers/${selected.id}/clauses`).then(d => setClauseTree(d.items)).catch(e => setError(e.message));
  }, [result?.machine.run_id, activeDocId]);

  async function upload() {
    if (!contract || !title.trim()) throw new Error('Nhập tên hồ sơ và chọn PDF hợp đồng.');
    const dossier = await api('/dossiers', 'POST', {title});
    for (const [file, role] of [[contract, 'contract'], ...annexes.map(f => [f, 'appendix'])] as [File, string][]) {
      const form = new FormData(); form.append('file', file); form.append('role', role);
      await api(`/dossiers/${dossier.id}/documents`, 'POST', form);
    }
    const job = await api(`/dossiers/${dossier.id}/jobs`, 'POST');
    setTitle(''); setContract(null); setAnnexes([]); await refresh();
    await open({...dossier, active_job_id: job.id, status: job.status});
  }
  async function showCitation(id: string) {
    const cit = await api(`/citations/${encodeURIComponent(id)}/resolve`) as Citation;
    const response = await fetch(cit.page_url);
    if (!response.ok) throw new Error('Không tải được trang nguồn.');
    setCitation(cit); setImage(URL.createObjectURL(await response.blob()));
    setActiveTableCellKey(''); setSourceTab('evidence');
  }
  // Table cells have no citation_id (evidence.py only builds citations from OCR lines),
  // but each cell already carries its own document_id/page_number/bbox — enough to fetch
  // the page image and highlight it directly, the same way showCitation does for facts.
  async function showTableCell(documentId: string, pageNumber: number, bbox: number[], quote: string, key: string) {
    if (!result) return;
    const pageUrl = `/api/v1/documents/${documentId}/pages/${pageNumber}?run_id=${result.machine.run_id}`;
    const response = await fetch(pageUrl);
    if (!response.ok) throw new Error('Không tải được trang nguồn.');
    setCitation({id: '', quote, page_number: pageNumber, bbox, page_url: pageUrl});
    setImage(URL.createObjectURL(await response.blob()));
    setActiveTableCellKey(key); setSourceTab('evidence');
  }
  async function loadPageText(n: number) {
    if (!result || !activeDocId) return;
    setPageLoading(true); setPageError('');
    try {
      setPageText(await api(`/documents/${activeDocId}/pages/${n}/text?run_id=${result.machine.run_id}`));
      setPageNum(n);
    } catch (e) {
      setPageError(e instanceof Error ? e.message : String(e));
    } finally {
      setPageLoading(false);
    }
  }
  async function submitReview() {
    if (!result || !selected) return;
    await api('/review-events', 'POST', {job_id: result.machine.run_id, target_id: reviewTarget,
      action, reason, expected_revision: result.review_version,
      correction: action === 'correct' ? JSON.parse(correction) : null});
    setResult(await api(`/dossiers/${selected.id}/results`));
    setAuditTrail((await api(`/dossiers/${selected.id}/audit`)).items);
    setReviewTarget(''); setReason(''); setCorrection(''); await refresh();
  }
  const refs = (ids: string[]) => ids.map((id, i) => <button className="link" key={id} onClick={() => perform(() => showCitation(id))}>Nguồn {i + 1}</button>);
  const shown = result?.[view];
  const confidenceBadge = (c: Confidence) => <span className={`confidence ${c.review_priority}`}>{c.calibrated && c.score != null ? `Độ tin cậy ${Math.round(c.score * 100)}%` : `Chưa hiệu chỉnh · ưu tiên review: ${c.review_priority}`}</span>;
  const activeDoc = documents.find(d => d.id === activeDocId);
  const activeTables = tables.filter(t => t.document_id === activeDocId);
  const activeClauses = clauseTree.filter(c => c.document_id === activeDocId);

  return <>
    <header>
      <div><span className="eyebrow">LOCAL WORKSPACE</span><h1>Contract Intelligence</h1></div>
      <span className="badge">Local baseline · v0.1</span>
    </header>
    <main>
      {busy && <div className="busy-indicator" role="status">Đang xử lý…</div>}
      {error && <div role="alert" className="error">{error}</div>}

      <section className="upload">
        <h2>Tạo hồ sơ mới</h2>
        <p className="hint">Tải lên hợp đồng PDF để bắt đầu xử lý tự động — có thể thêm phụ lục sau.</p>
        <div className="fields">
          <label>Tên hồ sơ<input value={title} onChange={e => setTitle(e.target.value)}/></label>
          <label>Hợp đồng PDF (bắt buộc)<input type="file" accept="application/pdf" onChange={e => setContract(e.target.files?.[0] ?? null)}/></label>
          <label>Phụ lục (tuỳ chọn)<input type="file" multiple accept="application/pdf" onChange={e => setAnnexes(Array.from(e.target.files ?? []))}/></label>
          <button disabled={busy || !contract} onClick={() => perform(upload)}>Tải lên &amp; xử lý</button>
        </div>
      </section>

      <div className="workspace">
        <aside>
          <h2>Hồ sơ</h2>
          {dossiers.length === 0 && <p className="empty">Chưa có hồ sơ. Tải PDF đầu tiên để bắt đầu.</p>}
          {dossiers.map(d => <button className={`dossier ${selected?.id === d.id ? 'active' : ''}`} key={d.id} onClick={() => perform(() => open(d))}>
            <strong>{d.title}</strong>
            <StatusBadge status={d.status}/>
          </button>)}
        </aside>

        <section className="detail">
          <div className="panel-title"><h2>{selected?.title ?? 'Chọn hồ sơ để xem kết quả'}</h2>{selected && <StatusBadge status={selected.status}/>}</div>
          {selected && !result && <div className="notice" role="status">
            {!selected.active_job_id ? <p>Tài liệu đã tải lên nhưng chưa bắt đầu xử lý.</p>
              : jobProgress?.status === 'failed' ? <p>Xử lý thất bại: {jobProgress.failure_code ?? 'chưa có kết quả'}. Có thể thử lại các trang lỗi.</p>
              : jobProgress?.attempts === 0 ? <p>Đã tải lên và xếp hàng, nhưng bộ xử lý chưa nhận trang nào. OCR, cấu trúc và bằng chứng chưa được tạo. Nếu chờ lâu, kiểm tra worker đang chạy cùng backend.</p>
              : <p>Đang xử lý tài liệu. Văn bản, cấu trúc điều khoản và bằng chứng sẽ hiển thị khi kết quả sẵn sàng.</p>}
            {jobProgress && <p>{jobProgress.progress.completed}/{jobProgress.progress.total} trang hoàn tất · {jobProgress.progress.failed} trang lỗi</p>}
            {jobError && <p className="error">Không tải được tiến độ: {jobError}</p>}
          </div>}
          {selected?.status === 'failed' && <button disabled={busy} onClick={() => perform(async () => {await api(`/jobs/${selected.active_job_id}/retry`, 'POST'); await refresh();})}>Thử lại trang lỗi</button>}

          {result && <>
            <p className={result.machine.is_partial ? 'error' : 'notice'}>{result.machine.is_partial ? 'Kết quả chưa đầy đủ — còn trang cần xử lý.' : 'Đã xử lý máy — cần người kiểm tra nội dung và độ đầy đủ.'}</p>
            <p>{result.machine.coverage.completed_pages}/{result.machine.coverage.expected_pages} trang · {result.machine.facts.length} fact · {result.machine.findings.length} finding</p>
            {result.machine.issues.map((issue, i) => <p key={i} className="error">Trang {issue.page_number}: {issue.code}</p>)}

            <label className="segmented-label">Phiên bản hiển thị</label>
            <div className="segmented" role="tablist" aria-label="Phiên bản hiển thị">
              <button type="button" className={view === 'effective' ? 'active' : ''} onClick={() => setView('effective')}>Effective — gồm giá trị đã sửa</button>
              <button type="button" className={view === 'machine' ? 'active' : ''} onClick={() => setView('machine')}>Machine — kết quả gốc</button>
            </div>

            {result.review.unresolved.length > 0 ? <div className="todo-panel">
              <h3>Cần bạn xử lý ({result.review.unresolved.length})</h3>
              {result.review.unresolved.map(id => <button key={id} className="target" onClick={() => setReviewTarget(id)}>{id === 'completeness' ? 'Kiểm tra độ đầy đủ của hồ sơ' : id.startsWith('relation:') ? 'Xác nhận phụ lục thuộc hợp đồng' : id}</button>)}
            </div> : <p className="notice">Không còn mục nào bắt buộc phải xử lý.</p>}

            {reviewTarget && result.status !== 'approved' && <form onSubmit={e => {e.preventDefault(); perform(submitReview);}}>
              <h3>Review: {reviewTarget}</h3>
              <select value={action} onChange={e => setAction(e.target.value)}>
                <option value="confirm">Xác nhận</option>
                <option value="correct">Sửa fact (JSON)</option>
                <option value="reject">Từ chối</option>
                <option value="needs_more_evidence">Cần thêm bằng chứng</option>
              </select>
              <label>Lý do<textarea value={reason} onChange={e => setReason(e.target.value)}/></label>
              {action === 'correct' && <label>Giá trị sửa (JSON)<textarea value={correction} onChange={e => setCorrection(e.target.value)} placeholder='{"amount":"120000000","currency":"VND"}'/></label>}
              <div className="form-actions"><button disabled={busy}>Lưu review</button><button type="button" className="link" onClick={() => setReviewTarget('')}>Huỷ</button></div>
            </form>}
            {result.review.stale && <p className="error">Có correction: kết quả dẫn xuất cần phân tích lại trước khi phê duyệt.</p>}
            <button disabled={busy || result.review.blocked || result.status !== 'reviewed'} onClick={() => perform(async () => {await api(`/dossiers/${selected!.id}/approve`, 'POST', {expected_revision: result.review_version}); await open(selected!); await refresh();})}>Phê duyệt hồ sơ</button>

            <div className="tabs" role="tablist">
              <button type="button" className={detailTab === 'facts' ? 'tab active' : 'tab'} onClick={() => setDetailTab('facts')}>Thông tin trích xuất ({shown?.facts.length ?? 0})</button>
              <button type="button" className={detailTab === 'findings' ? 'tab active' : 'tab'} onClick={() => setDetailTab('findings')}>So sánh hai nguồn ({shown?.findings.length ?? 0})</button>
              <button type="button" className={detailTab === 'history' ? 'tab active' : 'tab'} onClick={() => setDetailTab('history')}>Lịch sử review ({result.review.history.length})</button>
            </div>

            {detailTab === 'facts' && <div className="tab-panel">
              {shown?.facts.length === 0 && <p className="empty">Chưa trích xuất được thông tin nào.</p>}
              {shown?.facts.map(f => <article key={f.id}>
                <strong>{f.type}</strong> {confidenceBadge(f.confidence)}
                <p>Nguồn gốc: {f.raw}</p>
                <code>{JSON.stringify(f.normalized)}</code>
                <div>{refs(f.citation_ids)}<button className="link" disabled={view === 'machine'} onClick={() => {setReviewTarget(f.id); setCorrection(JSON.stringify(f.normalized));}}>Review</button></div>
              </article>)}
            </div>}

            {detailTab === 'findings' && <div className="tab-panel">
              {shown?.findings.length === 0 && <p className="empty">Không có cặp ứng viên trong phạm vi rule hiện tại; không có nghĩa là đã chứng minh không có xung đột.</p>}
              {shown?.findings.map(f => <article key={f.id}>
                <strong>{f.topic}</strong> <span className={`disposition ${f.disposition}`}>{DISPOSITION_LABEL[f.disposition] ?? f.disposition}</span>
                <p>{f.rationale}</p>
                <div>A: {refs(f.citations_a)} B: {refs(f.citations_b)}<button className="link" disabled={view === 'machine'} onClick={() => setReviewTarget(f.id)}>Review</button></div>
              </article>)}
            </div>}

            {detailTab === 'history' && <div className="tab-panel">
              {result.review.history.length === 0 && <p className="empty">Chưa có lượt review nào.</p>}
              {result.review.history.map(e => <article key={e.id}>
                <strong>#{e.version} · {e.action} · {e.actor}</strong>
                <p>{e.target_id}</p>
                <p>{e.reason}</p>
                {e.correction != null && <code>{JSON.stringify(e.correction)}</code>}
              </article>)}
            </div>}
          </>}

          {selected && <details className="audit-details">
            <summary>Nhật ký audit — toàn bộ hồ sơ ({auditTrail.length})</summary>
            <ol className="audit">{auditTrail.map(e => <li key={e.id} className={e.result}>
              <time>{new Date(e.created_at * 1000).toLocaleString('vi-VN')}</time>
              <strong>{e.action}</strong>
              <span>{e.actor} · {e.object_type}:{e.object_id.slice(0, 8)}</span>
              {Object.keys(e.detail).length > 0 && <code>{JSON.stringify(e.detail)}</code>}
            </li>)}</ol>
          </details>}
        </section>

        <section className="source">
          <h2>Tài liệu &amp; cấu trúc</h2>
          {documents.length === 0 && <p className="empty">Chưa có tài liệu nào được tải lên.</p>}
          {documents.length > 1 && <label>Xem tài liệu<select value={activeDocId} onChange={e => setActiveDocId(e.target.value)}>{documents.map(d => <option key={d.id} value={d.id}>{d.role === 'contract' ? 'Hợp đồng' : 'Phụ lục'} · {d.page_count} trang</option>)}</select></label>}

          {selected && <div className="tabs" role="tablist">
            <button type="button" className={sourceTab === 'overview' ? 'tab active' : 'tab'} onClick={() => setSourceTab('overview')}>Tổng quan</button>
            <button type="button" className={sourceTab === 'structure' ? 'tab active' : 'tab'} onClick={() => setSourceTab('structure')}>Cấu trúc điều khoản</button>
            <button type="button" className={sourceTab === 'fulltext' ? 'tab active' : 'tab'} onClick={() => setSourceTab('fulltext')}>Toàn văn theo trang</button>
            <button type="button" className={sourceTab === 'tables' ? 'tab active' : 'tab'} onClick={() => setSourceTab('tables')}>Bảng ({activeTables.length})</button>
            <button type="button" className={sourceTab === 'evidence' ? 'tab active' : 'tab'} onClick={() => setSourceTab('evidence')}>Bằng chứng</button>
          </div>}

          {sourceTab === 'overview' && <div className="tab-panel">
            {activeDoc && originalFile && <iframe className="original-doc" src={originalFile} title="Tài liệu gốc"/>}
            <h3>Quy trình xử lý (11 bước)</h3>
            <ol className="pipeline">{PIPELINE.map(stage => <li key={stage.no} className={stageState(selected?.status, stage.group)}><strong>{stage.no} {stage.name}</strong><span>{stage.does}</span><small>{stage.invariant}</small></li>)}</ol>
            {selected?.status === 'failed' && result?.machine.issues.length ? <p className="error">Dừng ở bước xử lý trang: {result.machine.issues.map(i => i.code).join(', ')}</p> : null}
          </div>}

          {sourceTab === 'structure' && <div className="tab-panel">
            {!result && <p className="empty">Cấu trúc điều khoản sẽ xuất hiện sau khi xử lý trang hoàn tất. Xem tiến độ trong phần hồ sơ.</p>}
            {result && activeDoc && activeClauses.length === 0 &&
              <p className="empty">Không nhận diện được Điều/Khoản/Điểm nào — có thể tài liệu không dùng đúng dạng số ở đầu dòng, cần review thủ công.</p>}
            {result && activeDoc && renderClauseTree(
              activeClauses, null, citation?.id,
              id => perform(() => showCitation(id)), expandedClauseIds, toggleClauseExpanded,
              openClauseIds, toggleClauseOpen,
            )}
          </div>}

          {sourceTab === 'fulltext' && <div className="tab-panel">
            {!result && <p className="empty">Văn bản/OCR sẽ xuất hiện sau khi xử lý trang hoàn tất. Xem tiến độ trong phần hồ sơ.</p>}
            {result && activeDoc && <>
              <div className="pager">
                <button disabled={pageLoading || pageNum <= 1} onClick={() => perform(() => loadPageText(pageNum - 1))}>← Trang trước</button>
                <span>Trang {pageNum}/{activeDoc.page_count}</span>
                <button disabled={pageLoading || pageNum >= activeDoc.page_count} onClick={() => perform(() => loadPageText(pageNum + 1))}>Trang sau →</button>
              </div>
              {pageLoading && <p className="empty">Đang tải văn bản trang…</p>}
              {pageError && <p className="error">{pageError}</p>}
              {pageText && <>
                {pageText.engine && <p className="notice">Công cụ: {pageText.engine}{pageText.issue ? ` · ${pageText.issue}` : ''}</p>}
                {pageText.lines.length === 0 && <p className="empty">Không có chữ nào được nhận dạng trên trang này — không có nghĩa là trang trống.</p>}
                <div className="lines">{pageText.lines.map(l => <p key={l.id}>{l.text}</p>)}</div>
              </>}
            </>}
          </div>}

          {sourceTab === 'tables' && <div className="tab-panel">
            {activeTables.length === 0 && <p className="empty">Không phát hiện bảng nào trên tài liệu này.</p>}
            {activeTables.map(table => {
              const pageLabel = table.page_start === table.page_end ? `Trang ${table.page_start}`
                : `Trang ${table.page_start}–${table.page_end}`;
              return <div key={table.id} className="table-wrap">
                <small>{pageLabel} · {table.rows.filter(r => r.kind === 'data').length} dòng dữ liệu × {table.col_count} cột</small>
                {table.status === 'RECONSTRUCTED' && <p className="notice">
                  Đã nối {table.fragment_ids.length} phần thành một bảng. Chọn nguồn trong ô để xem vị trí gốc.
                </p>}
                {table.status === 'NEEDS_REVIEW' && <p className="error">
                  Chưa đủ bằng chứng ghép phần này vào bảng trước. Giữ nguyên dữ liệu để rà soát.
                </p>}
                <table><tbody>{table.rows.map((row, i) => <tr key={i} className={row.kind}>
                  {Array.from({length: table.col_count}, (_, column) => {
                    const cell = row.cells.find(c => c.col_index === column);
                    if (!cell) return <td key={column} />;
                    const key = `${table.id}:${i}:${column}`;
                    const text = row.kind === 'header' ? cell.text.replace(/\s+/g, ' ').trim() : cell.text;
                    return <td key={column} className={activeTableCellKey.startsWith(key + ':') ? 'active' : ''}>
                      {row.kind === 'header' ? <strong>{text}</strong> : text}
                      {cell.sources.filter(source => source.text.trim()).map((source, j) =>
                        <button type="button" key={j} className="table-source"
                          aria-label={`Xem nguồn trang ${source.page_number}: ${source.text}`}
                          onClick={() => perform(() => showTableCell(source.document_id, source.page_number,
                            source.bbox, source.text, `${key}:${j}`))}>
                          Trang {source.page_number}{cell.sources.length > 1 ? ` · phần ${j + 1}` : ''}
                        </button>)}
                    </td>;
                  })}
                </tr>)}</tbody></table>
              </div>;
            })}
          </div>}

          {sourceTab === 'evidence' && <div className="tab-panel">
            {citation && image ? <>
              <p>Trang {citation.page_number} · vùng dòng</p>
              <div className="page"><img src={image} alt={`Trang nguồn ${citation.page_number}`}/><div className="bbox" style={{left: `${citation.bbox[0] * 100}%`, top: `${citation.bbox[1] * 100}%`, width: `${(citation.bbox[2] - citation.bbox[0]) * 100}%`, height: `${(citation.bbox[3] - citation.bbox[1]) * 100}%`}}/></div>
              <blockquote>{citation.quote}</blockquote>
            </> : <p className="empty">Chọn "Nguồn" tại fact hoặc finding để mở trang và vùng bằng chứng.</p>}
          </div>}
        </section>
      </div>
      <footer>Ứng viên từ rule local cần review. Chưa có benchmark accuracy; trích bảng từ trang scan dựa vào hình học OCR, có thể sai với bố cục phức tạp — chưa hỗ trợ suy luận pháp lý.</footer>
    </main>
  </>;
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
