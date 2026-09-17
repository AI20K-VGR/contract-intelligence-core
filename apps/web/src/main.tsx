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

function App() {
  const [token, setToken] = useState('');
  const [connected, setConnected] = useState(false);
  const [dossiers, setDossiers] = useState<Dossier[]>([]);
  const [selected, setSelected] = useState<Dossier | null>(null);
  const [result, setResult] = useState<Result | null>(null);
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

  async function api(path: string, method = 'GET', body?: unknown) {
    const headers: Record<string, string> = {Authorization: `Bearer ${token}`};
    if (method !== 'GET') headers['Idempotency-Key'] = crypto.randomUUID();
    if (body && !(body instanceof FormData)) headers['Content-Type'] = 'application/json';
    const response = await fetch(`/api/v1${path}`, {method, headers,
      body: body instanceof FormData ? body : body ? JSON.stringify(body) : undefined});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error?.code ?? `HTTP ${response.status}`);
    return data;
  }
  async function apiBlob(path: string) {
    const response = await fetch(`/api/v1${path}`, {headers: {Authorization: `Bearer ${token}`}});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return URL.createObjectURL(await response.blob());
  }
  async function perform(task: () => Promise<void>) {
    setBusy(true); setError('');
    try {await task();} catch (e) {setError(e instanceof Error ? e.message : String(e));}
    finally {setBusy(false);}
  }
  async function refresh() {
    const data = await api('/dossiers');
    setDossiers(data.items); setConnected(true);
  }
  async function open(dossier: Dossier) {
    setSelected(dossier); setResult(null); setCitation(null); setImage(''); setReviewTarget('');
    const docs = (await api(`/dossiers/${dossier.id}/documents`)).items as DocumentInfo[];
    setDocuments(docs);
    setActiveDocId((docs.find(d => d.role === 'contract') ?? docs[0])?.id ?? '');
    if (['pending_review', 'reviewed', 'approved', 'failed'].includes(dossier.status)) {
      setResult(await api(`/dossiers/${dossier.id}/results`));
    }
  }
  useEffect(() => {
    if (!connected) return;
    const timer = setInterval(() => {
      api('/dossiers').then(data => {
        setDossiers(data.items);
        const current = data.items.find((d: Dossier) => d.id === selected?.id);
        if (current && current.status !== selected?.status) {
          open(current).catch(e => setError(e.message));
        }
      }).catch(e => setError(e.message));
    }, 3000);
    return () => clearInterval(timer);
  }, [connected, selected, token]);
  useEffect(() => () => {if (image) URL.revokeObjectURL(image);}, [image]);
  useEffect(() => () => {if (originalFile) URL.revokeObjectURL(originalFile);}, [originalFile]);
  useEffect(() => {
    setPageNum(1); setPageText(null); setPageError('');
    if (!activeDocId) {setOriginalFile(''); return;}
    apiBlob(`/documents/${activeDocId}/file`).then(setOriginalFile).catch(e => setError(e.message));
  }, [activeDocId]);
  useEffect(() => {
    if (result && activeDocId) loadPageText(1);
  }, [result?.machine.run_id, activeDocId]);

  async function upload() {
    if (!contract || !title.trim()) throw new Error('Nhập tên hồ sơ và chọn PDF hợp đồng.');
    const dossier = await api('/dossiers', 'POST', {title});
    for (const [file, role] of [[contract, 'contract'], ...annexes.map(f => [f, 'appendix'])] as [File, string][]) {
      const form = new FormData(); form.append('file', file); form.append('role', role);
      await api(`/dossiers/${dossier.id}/documents`, 'POST', form);
    }
    await api(`/dossiers/${dossier.id}/jobs`, 'POST');
    setTitle(''); await refresh();
  }
  async function showCitation(id: string) {
    const cit = await api(`/citations/${encodeURIComponent(id)}/resolve`) as Citation;
    const response = await fetch(cit.page_url, {headers: {Authorization: `Bearer ${token}`}});
    if (!response.ok) throw new Error('Không tải được trang nguồn.');
    setCitation(cit); setImage(URL.createObjectURL(await response.blob()));
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
    setReviewTarget(''); setReason(''); setCorrection(''); await refresh();
  }
  const refs = (ids: string[]) => ids.map((id, i) => <button className="link" key={id} onClick={() => perform(() => showCitation(id))}>Nguồn {i + 1}</button>);
  const shown = result?.[view];
  const confidenceBadge = (c: Confidence) => <span className={`confidence ${c.review_priority}`}>{c.calibrated && c.score != null ? `Độ tin cậy ${Math.round(c.score * 100)}%` : `Chưa hiệu chỉnh · ưu tiên review: ${c.review_priority}`}</span>;
  const activeDoc = documents.find(d => d.id === activeDocId);

  return <><header><div><span className="eyebrow">LOCAL WORKSPACE</span><h1>Contract Intelligence</h1></div><span className="badge">Local baseline · v0.1</span></header>
    <main><section className="access"><label>Token truy cập<input type="password" value={token} onChange={e => {setToken(e.target.value); setConnected(false); setResult(null); setDossiers([]);}} placeholder="Token được cấp trong cấu hình local"/></label><button disabled={busy} onClick={() => perform(refresh)}>Kết nối</button><small>Token chỉ giữ trong bộ nhớ của trang.</small></section>
    {error && <div role="alert" className="error">{error}</div>}
    {connected && <><section className="upload"><h2>Hồ sơ mới</h2><div className="fields"><label>Tên hồ sơ<input value={title} onChange={e => setTitle(e.target.value)}/></label><label>Hợp đồng PDF<input type="file" accept="application/pdf" onChange={e => setContract(e.target.files?.[0] ?? null)}/></label><label>Phụ lục (tuỳ chọn)<input type="file" multiple accept="application/pdf" onChange={e => setAnnexes(Array.from(e.target.files ?? []))}/></label><button disabled={busy || !contract} onClick={() => perform(upload)}>Tải lên & xử lý</button></div></section>
    <div className="workspace"><aside><h2>Hồ sơ</h2>{dossiers.length === 0 && <p>Chưa có hồ sơ. Tải PDF đầu tiên để bắt đầu.</p>}{dossiers.map(d => <button className={`dossier ${selected?.id === d.id ? 'active' : ''}`} key={d.id} onClick={() => perform(() => open(d))}><strong>{d.title}</strong><small>{d.status}</small></button>)}</aside>
    <section className="detail"><h2>{selected?.title ?? 'Chọn hồ sơ để xem kết quả'}</h2>{selected && !result && <p>Trạng thái: {selected.status}. Kết quả sẽ hiển thị sau khi worker xử lý.</p>}
    {selected?.status === 'failed' && <button disabled={busy} onClick={() => perform(async () => {await api(`/jobs/${selected.active_job_id}/retry`, 'POST'); await refresh();})}>Thử lại trang lỗi</button>}
    {result && <><p className={result.machine.is_partial ? 'error' : 'notice'}>{result.machine.is_partial ? 'Kết quả chưa đầy đủ — còn trang cần xử lý.' : 'Đã xử lý máy — cần người kiểm tra nội dung và độ đầy đủ.'}</p><p>{result.machine.coverage.completed_pages}/{result.machine.coverage.expected_pages} trang · {result.machine.facts.length} fact · {result.machine.findings.length} finding</p>
    {result.machine.issues.map((issue, i) => <p key={i} className="error">Trang {issue.page_number}: {issue.code}</p>)}
    <label>Phiên bản hiển thị<select value={view} onChange={e => setView(e.target.value as 'effective' | 'machine')}><option value="effective">Effective — gồm giá trị đã sửa</option><option value="machine">Machine — kết quả gốc</option></select></label>
    <h3>Thông tin trích xuất</h3>{shown?.facts.map(f => <article key={f.id}><strong>{f.type}</strong> {confidenceBadge(f.confidence)}<p>Nguồn gốc: {f.raw}</p><code>{JSON.stringify(f.normalized)}</code><div>{refs(f.citation_ids)}<button className="link" disabled={view === 'machine'} onClick={() => {setReviewTarget(f.id); setCorrection(JSON.stringify(f.normalized));}}>Review</button></div></article>)}
    <h3>So sánh hai nguồn</h3>{shown?.findings.length === 0 && <p>Không có cặp ứng viên trong phạm vi rule hiện tại; không có nghĩa là đã chứng minh không có xung đột.</p>}{shown?.findings.map(f => <article key={f.id}><strong>{f.topic} · {f.disposition}</strong><p>{f.rationale}</p><div>A: {refs(f.citations_a)} B: {refs(f.citations_b)}<button className="link" disabled={view === 'machine'} onClick={() => setReviewTarget(f.id)}>Review</button></div></article>)}
    <h3>Kiểm tra bắt buộc ({result.review.unresolved.length})</h3>{result.review.unresolved.map(id => <button key={id} className="target" onClick={() => setReviewTarget(id)}>{id === 'completeness' ? 'Kiểm tra độ đầy đủ của hồ sơ' : id.startsWith('relation:') ? 'Xác nhận phụ lục thuộc hợp đồng' : id}</button>)}
    {reviewTarget && result.status !== 'approved' && <form onSubmit={e => {e.preventDefault(); perform(submitReview);}}><h3>Review: {reviewTarget}</h3><select value={action} onChange={e => setAction(e.target.value)}><option value="confirm">Xác nhận</option><option value="correct">Sửa fact (JSON)</option><option value="reject">Từ chối</option><option value="needs_more_evidence">Cần thêm bằng chứng</option></select><label>Lý do<textarea value={reason} onChange={e => setReason(e.target.value)}/></label>{action === 'correct' && <label>Giá trị sửa (JSON)<textarea value={correction} onChange={e => setCorrection(e.target.value)} placeholder='{"amount":"120000000","currency":"VND"}'/></label>}<button disabled={busy}>Lưu review</button></form>}
    {result.review.stale && <p className="error">Có correction: kết quả dẫn xuất cần phân tích lại trước khi phê duyệt.</p>}
    <button disabled={busy || result.review.blocked || result.status !== 'reviewed'} onClick={() => perform(async () => {await api(`/dossiers/${selected!.id}/approve`, 'POST', {expected_revision: result.review_version}); await open(selected!); await refresh();})}>Phê duyệt hồ sơ</button>
    <h3>Lịch sử review</h3>{result.review.history.map(e => <article key={e.id}><strong>#{e.version} · {e.action} · {e.actor}</strong><p>{e.target_id}</p><p>{e.reason}</p>{e.correction != null && <code>{JSON.stringify(e.correction)}</code>}</article>)}</>}
    </section><section className="source">
    <h2>Tài liệu gốc của người dùng</h2>
    {documents.length === 0 && <p>Chưa có tài liệu nào được tải lên.</p>}
    {documents.length > 1 && <label>Xem tài liệu<select value={activeDocId} onChange={e => setActiveDocId(e.target.value)}>{documents.map(d => <option key={d.id} value={d.id}>{d.role === 'contract' ? 'Hợp đồng' : 'Phụ lục'} · {d.page_count} trang</option>)}</select></label>}
    {activeDoc && originalFile && <iframe className="original-doc" src={originalFile} title="Tài liệu gốc"/>}

    <h3>Quy trình xử lý (11 bước)</h3>
    <ol className="pipeline">{PIPELINE.map(stage => <li key={stage.no} className={stageState(selected?.status, stage.group)}><strong>{stage.no} {stage.name}</strong><span>{stage.does}</span><small>{stage.invariant}</small></li>)}</ol>
    {selected?.status === 'failed' && result?.machine.issues.length ? <p className="error">Dừng ở bước xử lý trang: {result.machine.issues.map(i => i.code).join(', ')}</p> : null}

    <h3>Toàn văn trích xuất theo trang{activeDoc ? ` · ${activeDoc.page_count} trang` : ''}</h3>
    {!result && <p>Chỉ có sau khi hồ sơ đã qua bước Extract (cần bắt đầu xử lý).</p>}
    {result && activeDoc && <>
      <div className="pager">
        <button disabled={pageLoading || pageNum <= 1} onClick={() => perform(() => loadPageText(pageNum - 1))}>← Trang trước</button>
        <span>Trang {pageNum}/{activeDoc.page_count}</span>
        <button disabled={pageLoading || pageNum >= activeDoc.page_count} onClick={() => perform(() => loadPageText(pageNum + 1))}>Trang sau →</button>
      </div>
      {pageLoading && <p>Đang tải văn bản trang…</p>}
      {pageError && <p className="error">{pageError}</p>}
      {pageText && <>
        {pageText.engine && <p className="notice">Công cụ: {pageText.engine}{pageText.issue ? ` · ${pageText.issue}` : ''}</p>}
        {pageText.lines.length === 0 && <p>Không có chữ nào được nhận dạng trên trang này — không có nghĩa là trang trống.</p>}
        <div className="lines">{pageText.lines.map(l => <p key={l.id}>{l.text}</p>)}</div>
      </>}
    </>}

    <h3>Bằng chứng theo trích dẫn</h3>{citation && image ? <><p>Trang {citation.page_number} · vùng dòng</p><div className="page"><img src={image} alt={`Trang nguồn ${citation.page_number}`}/><div className="bbox" style={{left: `${citation.bbox[0] * 100}%`, top: `${citation.bbox[1] * 100}%`, width: `${(citation.bbox[2] - citation.bbox[0]) * 100}%`, height: `${(citation.bbox[3] - citation.bbox[1]) * 100}%`}}/></div><blockquote>{citation.quote}</blockquote></> : <p>Chọn “Nguồn” tại fact hoặc finding để mở trang và vùng bằng chứng.</p>}</section></div></>}
    <footer>Ứng viên từ rule local cần review. Chưa có benchmark accuracy; chưa hỗ trợ trích bảng hoặc suy luận pháp lý.</footer></main></>;
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
