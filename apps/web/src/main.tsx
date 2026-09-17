import React, {useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import './style.css';

type Dossier = {id: string; title: string; status: string; active_job_id: string | null};
type Fact = {id: string; type: string; raw: string; normalized: unknown; citation_ids: string[]};
type Finding = {id: string; topic: string; disposition: string; rationale: string; citations_a: string[]; citations_b: string[]};
type Citation = {id: string; quote: string; page_number: number; bbox: number[]; page_url: string};
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
    <h3>Thông tin trích xuất</h3>{shown?.facts.map(f => <article key={f.id}><strong>{f.type}</strong><p>Nguồn gốc: {f.raw}</p><code>{JSON.stringify(f.normalized)}</code><div>{refs(f.citation_ids)}<button className="link" disabled={view === 'machine'} onClick={() => {setReviewTarget(f.id); setCorrection(JSON.stringify(f.normalized));}}>Review</button></div></article>)}
    <h3>So sánh hai nguồn</h3>{shown?.findings.length === 0 && <p>Không có cặp ứng viên trong phạm vi rule hiện tại; không có nghĩa là đã chứng minh không có xung đột.</p>}{shown?.findings.map(f => <article key={f.id}><strong>{f.topic} · {f.disposition}</strong><p>{f.rationale}</p><div>A: {refs(f.citations_a)} B: {refs(f.citations_b)}<button className="link" disabled={view === 'machine'} onClick={() => setReviewTarget(f.id)}>Review</button></div></article>)}
    <h3>Kiểm tra bắt buộc ({result.review.unresolved.length})</h3>{result.review.unresolved.map(id => <button key={id} className="target" onClick={() => setReviewTarget(id)}>{id === 'completeness' ? 'Kiểm tra độ đầy đủ của hồ sơ' : id.startsWith('relation:') ? 'Xác nhận phụ lục thuộc hợp đồng' : id}</button>)}
    {reviewTarget && result.status !== 'approved' && <form onSubmit={e => {e.preventDefault(); perform(submitReview);}}><h3>Review: {reviewTarget}</h3><select value={action} onChange={e => setAction(e.target.value)}><option value="confirm">Xác nhận</option><option value="correct">Sửa fact (JSON)</option><option value="reject">Từ chối</option><option value="needs_more_evidence">Cần thêm bằng chứng</option></select><label>Lý do<textarea value={reason} onChange={e => setReason(e.target.value)}/></label>{action === 'correct' && <label>Giá trị sửa (JSON)<textarea value={correction} onChange={e => setCorrection(e.target.value)} placeholder='{"amount":"120000000","currency":"VND"}'/></label>}<button disabled={busy}>Lưu review</button></form>}
    {result.review.stale && <p className="error">Có correction: kết quả dẫn xuất cần phân tích lại trước khi phê duyệt.</p>}
    <button disabled={busy || result.review.blocked || result.status !== 'reviewed'} onClick={() => perform(async () => {await api(`/dossiers/${selected!.id}/approve`, 'POST', {expected_revision: result.review_version}); await open(selected!); await refresh();})}>Phê duyệt hồ sơ</button>
    <h3>Lịch sử review</h3>{result.review.history.map(e => <article key={e.id}><strong>#{e.version} · {e.action} · {e.actor}</strong><p>{e.target_id}</p><p>{e.reason}</p>{e.correction != null && <code>{JSON.stringify(e.correction)}</code>}</article>)}</>}
    </section><section className="source"><h2>Bằng chứng gốc</h2>{citation && image ? <><p>Trang {citation.page_number} · vùng dòng</p><div className="page"><img src={image} alt={`Trang nguồn ${citation.page_number}`}/><div className="bbox" style={{left: `${citation.bbox[0] * 100}%`, top: `${citation.bbox[1] * 100}%`, width: `${(citation.bbox[2] - citation.bbox[0]) * 100}%`, height: `${(citation.bbox[3] - citation.bbox[1]) * 100}%`}}/></div><blockquote>{citation.quote}</blockquote></> : <p>Chọn “Nguồn” tại fact hoặc finding để mở trang và vùng bằng chứng.</p>}</section></div></>}
    <footer>Ứng viên từ rule local cần review. Chưa có benchmark accuracy; chưa hỗ trợ trích bảng hoặc suy luận pháp lý.</footer></main></>;
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
