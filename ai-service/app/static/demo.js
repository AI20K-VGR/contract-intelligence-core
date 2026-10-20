const $ = (id) => document.getElementById(id);
const STAGES = [
  "Bàn giao AI1 → AI2",
  "Duyệt mục lục",
  "Sự kiện / bảng",
  "Cắt đoạn điều khoản",
  "Ứng viên đối chiếu",
  "Đề xuất chỉ mục",
  "Neo nguồn dẫn",
];

let session = null;
let page = 1;
let tasks = [];
let lastReason = null;
let highlight = null;
let selectedNode = null;
let currentFileId = null;
let pageInFile = 1;
let pdfCache = { id: null, doc: null };

if (window.pdfjsLib) {
  pdfjsLib.GlobalWorkerOptions.workerSrc =
    "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
}

function badge(state) {
  return `<span class="badge ${state || ""}">${viLabel(state)}</span>`;
}

const VI = {
  CLAUSE: "Điều khoản",
  FIELD: "Trường",
  TABLE: "Bảng",
  SECTION: "Phần",
  UNNUMBERED_BLOCK: "Khối không số",
  PASS: "Đạt",
  NEEDS_REVIEW: "Cần rà",
  INSUFFICIENT_EVIDENCE: "Thiếu chứng cứ",
  BLOCKED: "Chặn",
  ANSWERED: "Đã trả lời",
  NOT_COMPARABLE: "Không so được",
  NEEDS_EVIDENCE: "Cần chứng cứ",
  CANDIDATE_AMENDMENT: "Ứng viên sửa đổi",
  COMPARABLE_MATCH: "Khớp so được",
  COMPARABLE_DIFFERENCE: "Khác biệt so được",
  MATCH: "Khớp",
  DIVERGENCE: "Lệch",
  GAP: "Hổng",
  AMBIGUITY: "Mơ hồ",
  CONSISTENT: "Nhất quán",
  CONFLICTING: "Khác giá trị (không kết luận pháp lý)",
  INCOMPLETE: "Chưa đủ",
  UNCLEAR: "Chưa rõ",
  RUNNING: "Đang chạy",
  SUCCEEDED: "Xong",
  FAILED: "Lỗi",
  WITHIN_DOCUMENT: "Trong cùng tài liệu",
  CONTRACT_ANNEX: "Hợp đồng ↔ phụ lục",
  ANNEX_ANNEX: "Phụ lục ↔ phụ lục",
  body: "thân HĐ",
  annex: "phụ lục",
  on: "bật",
  off: "tắt",
  confirm: "Xác nhận (kỹ thuật)",
  correct: "Overlay",
  reject: "Từ chối",
};

function viLabel(v) {
  if (v == null || v === "") return "—";
  const s = String(v);
  return VI[s] || s;
}
function escapeHtml(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}
function setStep(name) {
  document.querySelectorAll("#steps span").forEach((el) => {
    el.classList.toggle("on", el.getAttribute("data-step") === name);
  });
}

async function loadHealth() {
  const h = await fetch("/health").then((r) => r.json());
  const llmText = h.llm === "ready" ? `LLM: ${h.model}` : "LLM: off";
  const emb = h.embedding || {};
  const embText = emb.status === "READY"
    ? `Embedding: ${emb.selected_model} · ${emb.dimensions}d`
    : `Embedding: ${emb.status || "NOT_RUN"}`;
  $("health").textContent = `${llmText} · ${embText}`;
}

function traceHtml(out) {
  const trace = out?.retrieval_trace || {};
  const llm = out?.llm_trace || {};
  return `<details class="trace"><summary>Trace xử lý</summary>
    <div class="mono">vector=${escapeHtml(trace.vector_status || (out?.use_vector ? "REQUESTED" : "NOT_REQUESTED"))}
      · model=${escapeHtml(trace.embedding_model || "—")}
      · dimensions=${escapeHtml(trace.embedding_dimensions || "—")}
      · hits=${escapeHtml(trace.vector_hits ?? "—")}
      · LLM=${escapeHtml(out?.used_llm ? (llm.model || "enabled") : "off")}</div>
    ${Object.keys(llm).length ? `<pre class="mono">${escapeHtml(JSON.stringify(llm, null, 2))}</pre>` : ""}
  </details>`;
}

function showWork(on) {
  $("view-ingest").classList.toggle("hidden", on);
  $("view-work").classList.toggle("hidden", !on);
}

function renderTimeline(active, done) {
  $("timeline").innerHTML = STAGES.map((s, i) => {
    const cls = i < done ? "chip done" : i === active ? "chip run" : "chip";
    return `<span class="${cls}">${s}</span>`;
  }).join("");
}

function renderStruct() {
  if (!session) return;
  const tableCoverage = Object.entries(session.table_coverage || {})
    .map(([status, count]) => `${status}: ${count}`)
    .join(" · ") || "UNKNOWN";
  const graph = session.relation_graph || {};
  const policy = session.policy || {};
  const policyRows = (policy.gates || []).map((gate) =>
    `<div class="row">${badge(gate.code)}<span>${escapeHtml(gate.operation)}</span><span class="muted">deterministic: ${escapeHtml(gate.deterministic_action)}</span></div>`
  ).join("");
  $("pane-struct").innerHTML = `
    <p class="muted">Cây theo từng tệp PDF. Bấm mục để tô trên PDF gốc, rồi hỏi bên phải.</p>
    <div class="stat">
      <div><b>${session.n_pages}</b><div class="muted">trang</div></div>
      <div><b>${session.n_nodes}</b><div class="muted">nút cây</div></div>
      <div><b>${session.n_tables}</b><div class="muted">bảng</div></div>
    </div>
    <p class="muted">Bao phủ bảng: <span class="mono">${escapeHtml(tableCoverage)}</span></p>
    <p class="muted">Relation graph: <span class="mono">${graph.n_edges || 0} edges · ${graph.n_issues || 0} issues</span></p>
    <p class="muted">Citation: <span class="mono">${session.n_citations || 0}</span> · Review queue: <span class="mono">${escapeHtml(session.review_queue_status || "NOT_RUN")} (${session.n_review_items || 0})</span></p>
    <p class="muted">Policy: deterministic=${escapeHtml(policy.deterministic || "—")} · external=${escapeHtml(policy.external || "—")}</p>
    ${policyRows ? `<h3>Policy gate</h3>${policyRows}` : ""}
    <p class="muted">${escapeHtml(session.ai1?.note || "")}</p>
  `;
  const handoff = session.handoff_issues || [];
  if (handoff.length) {
    const rows = handoff
      .map((issue) => `<div class="row">${badge(issue.review_state)}<span>${escapeHtml(issue.code)} — ${escapeHtml(issue.message || "")}</span></div>`)
      .join("");
    $("pane-struct").insertAdjacentHTML("beforeend", `<h3>Handoff AI1 → AI2</h3>${rows}`);
  }
  renderTree();
  renderGraphPane();
}

function renderGraphPane(graphData) {
  if (!session || !$("pane-graph")) return;
  const graph = graphData || session.relation_graph || {};
  const edges = graph.edges || [];
  const issues = graph.issues || [];
  const tables = session.tables || [];
  const edgeRows = edges.slice(0, 40).map((edge) =>
    `<div class="row"><span>${badge(edge.review_state)} <strong>${escapeHtml(edge.relation_type || "relation")}</strong></span>` +
    `<span>${escapeHtml(edge.from_node_id)} → ${escapeHtml(edge.to_node_id)}</span>` +
    `<span class="muted">${escapeHtml(edge.support || "")}</span></div>`
  ).join("");
  const issueRows = issues.map((issue) =>
    `<div class="row">${badge(issue.review_state)}<span>${escapeHtml(issue.missing || issue.code || "issue")} — ${escapeHtml(issue.reason || issue.message || "")}</span></div>`
  ).join("");
  const tableRows = tables.map((table) =>
    `<button type="button" class="table-link" data-table="${escapeHtml(table.table_id)}">${escapeHtml(table.title || table.table_id)} · ${table.n_rows} dòng</button>`
  ).join("");
  $("pane-graph").innerHTML = `<p class="muted">Graph và bảng được tải theo nhu cầu; không đưa toàn bộ tài liệu dài vào DOM.</p>
    <div class="stat"><div><b>${graph.n_nodes ?? edges.length}</b><div class="muted">graph node</div></div>
      <div><b>${graph.n_edges ?? edges.length}</b><div class="muted">relation edge</div></div>
      <div><b>${issues.length || graph.n_issues || 0}</b><div class="muted">graph issue</div></div></div>
    <h3>Quan hệ</h3>${edgeRows || '<p class="muted">Chưa có edge hoặc chưa chạy extraction.</p>'}
    <h3>Vấn đề chứng cứ</h3>${issueRows || '<p class="muted">Không có</p>'}
    <h3>Bảng</h3><div class="table-links">${tableRows || '<p class="muted">Không có bảng.</p>'}</div>
    <div id="table-detail"></div>`;
  $("pane-graph").querySelectorAll("button[data-table]").forEach((button) => {
    button.onclick = () => loadTableDetail(button.getAttribute("data-table"));
  });
}

async function refreshGraphPane() {
  if (!session) return;
  try {
    const data = await fetch(`/api/workspace/${session.session_id}/relation-graph`).then((r) => r.json());
    renderGraphPane(data);
  } catch (err) {
    renderGraphPane(session.relation_graph || {});
  }
}

async function loadTableDetail(tableId) {
  if (!session || !tableId) return;
  const box = $("table-detail");
  if (!box) return;
  box.innerHTML = "<p>Đang tải bảng…</p>";
  const data = await fetch(`/api/workspace/${session.session_id}/tables/${encodeURIComponent(tableId)}?offset=0&limit=50`).then((r) => r.json());
  const rows = (data.rows || []).map((row, index) => `<tr><td>${data.offset + index + 1}</td>${row.map((cell) => `<td>${escapeHtml(cell)}</td>`).join("")}</tr>`).join("");
  box.innerHTML = `<h3>${escapeHtml(data.title || data.table_id)} <span class="muted">${data.n_rows} dòng · geometry=${data.has_geometry ? "có" : "không"}</span></h3>
    <div class="table-scroll"><table><thead><tr><th>#</th>${(data.header || []).map((cell) => `<th>${escapeHtml(cell)}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table></div>
    ${data.has_geometry ? "" : '<p class="err">AI1 không có cell/geometry: AI2 không dựng lại vị trí bảng.</p>'}`;
}

function nodeMatchesFilter(n, q) {
  if (!q) return true;
  const blob = `${n.raw_label || ""} ${n.node_id || ""} ${n.preview || ""}`.toLowerCase();
  if (blob.includes(q)) return true;
  return (n.children || []).some((c) => nodeMatchesFilter(c, q));
}

function treeHtml(nodes, q) {
  return (nodes || [])
    .filter((n) => nodeMatchesFilter(n, q))
    .map((n) => {
      const kids = n.children || [];
      const btn = `<button type="button" class="node${selectedNode === n.node_id ? " on" : ""}" data-node="${n.node_id}">${escapeHtml(n.raw_label)} <span class="pg">${n.page_in_file ? "trang " + n.page_in_file : "trang " + (n.page || "—")} · ${viLabel(n.type)}</span></button>`;
      if (!kids.length) return `<div>${btn}</div>`;
      return `<details open><summary>${btn}</summary>${treeHtml(kids, q)}</details>`;
    })
    .join("");
}

function renderTree() {
  const q = (($("tree-filter") && $("tree-filter").value) || "").toLowerCase();
  $("tree").innerHTML = treeHtml(session.tree || [], q) || '<p class="muted">Chưa có mục lục.</p>';
  $("tree").querySelectorAll("button.node").forEach((b) => {
    b.onclick = (e) => {
      e.preventDefault();
      e.stopPropagation();
      jumpToNode(b.getAttribute("data-node"));
    };
  });
}

async function jumpToNode(nodeId) {
  selectedNode = nodeId;
  renderTree();
  const loc = await fetch(`/api/workspace/${session.session_id}/locate/${encodeURIComponent(nodeId)}`).then((r) => r.json());
  highlight = loc;
  page = loc.page || 1;
  if (loc.file_id) currentFileId = loc.file_id;
  pageInFile = loc.page_in_file || 1;
  $("loc-meta").textContent = `${(loc.breadcrumb || []).join(" › ")} · ${loc.page_revision_id || ""}`;
  await showPage();
}

function fileOf(id) {
  return (session.files || []).find((f) => f.file_id === id);
}

function renderFileTabs() {
  const tabs = $("file-tabs");
  if (!tabs) return;
  const files = session.files || [];
  tabs.innerHTML = files
    .map(
      (f) =>
        `<button type="button" class="${f.file_id === currentFileId ? "on" : ""}" data-file="${f.file_id}">${escapeHtml(f.filename)}</button>`
    )
    .join("");
  tabs.querySelectorAll("button").forEach((b) => {
    b.onclick = () => {
      currentFileId = b.getAttribute("data-file");
      pageInFile = 1;
      highlight = null;
      showPage();
    };
  });
}

async function showPage() {
  if (!session) return;
  $("doc-name").textContent = session.filename;
  $("doc-meta").textContent = `${session.tenant_id} · ${session.dossier_id}`;
  renderFileTabs();
  const files = session.files || [];
  if (!currentFileId && files[0]) currentFileId = files[0].file_id;
  const src = fileOf(currentFileId);
  const nPages = src ? src.n_pages : session.n_pages || 1;
  pageInFile = Math.min(Math.max(pageInFile, 1), nPages);
  $("page-ind").textContent = `${pageInFile} / ${nPages}`;

  const usePdf = session.has_pdf && currentFileId && window.pdfjsLib;
  $("page-view").classList.toggle("hidden", !!usePdf);
  document.querySelector(".pdf-stage").classList.toggle("hidden", !usePdf);

  if (usePdf) {
    await renderPdf(currentFileId, pageInFile, highlight);
    return;
  }
  const n = Math.min(Math.max(page, 1), session.n_pages || 1);
  page = n;
  const p = await fetch(`/api/workspace/${session.session_id}/page/${n}`).then((r) => r.json());
  let body = escapeHtml(p.text || "(trang trống)");
  if (highlight && highlight.page === n && highlight.text_span) {
    const span = escapeHtml(highlight.text_span);
    if (span && body.includes(span)) body = body.replace(span, `<mark class="hit">${span}</mark>`);
  }
  $("page-view").innerHTML = `<p class="muted">${badge(p.quality)} ${escapeHtml(p.page_revision_id)}</p>${body}`;
}

async function renderPdf(fileId, num, loc) {
  const url = `/api/workspace/${session.session_id}/files/${fileId}`;
  if (pdfCache.id !== fileId) {
    const buf = await fetch(url).then((r) => r.arrayBuffer());
    pdfCache = { id: fileId, doc: await pdfjsLib.getDocument({ data: buf }).promise };
  }
  const pdfPage = await pdfCache.doc.getPage(num);
  const scale = 1.25;
  const viewport = pdfPage.getViewport({ scale });
  const canvas = $("pdf-canvas");
  const ctx = canvas.getContext("2d");
  canvas.width = viewport.width;
  canvas.height = viewport.height;
  await pdfPage.render({ canvasContext: ctx, viewport }).promise;
  const hl = $("pdf-hl");
  hl.innerHTML = "";
  hl.style.width = canvas.clientWidth + "px";
  hl.style.height = canvas.clientHeight + "px";
  if (!loc || loc.file_id !== fileId || Number(loc.page_in_file) !== Number(num)) return;
  const needle = highlightNeedle(loc);
  if (!needle) return;
  const tc = await pdfPage.getTextContent();
  const items = matchPdfItems(tc.items || [], needle);
  const sx = canvas.clientWidth / canvas.width;
  const sy = canvas.clientHeight / canvas.height;
  items.forEach((it) => {
    const r = itemViewportBox(it, viewport);
    const box = document.createElement("div");
    box.className = "hl";
    box.style.left = r.left * sx + "px";
    box.style.top = r.top * sy + "px";
    box.style.width = Math.max(r.width * sx, 8) + "px";
    box.style.height = Math.max(r.height * sy, 10) + "px";
    hl.appendChild(box);
  });
  hl.querySelector(".hl")?.scrollIntoView({ block: "center", behavior: "smooth" });
}

function highlightNeedle(loc) {
  const raw = String(loc.text_span || loc.structured_value || "");
  const m = raw.match(/\d{8,14}/);
  return (m ? m[0] : raw).trim();
}

function matchPdfItems(items, needle) {
  const n = needle.replace(/\s/g, "").toLowerCase();
  if (!n) return [];
  const cmap = [];
  let compact = "";
  for (const it of items) {
    for (const ch of it.str || "") {
      if (/\s/.test(ch)) continue;
      cmap.push(it);
      compact += ch.toLowerCase();
    }
  }
  const idx = compact.indexOf(n);
  if (idx < 0) return [];
  const used = new Set();
  for (let i = idx; i < idx + n.length && i < cmap.length; i++) used.add(cmap[i]);
  return [...used];
}

function itemViewportBox(item, viewport) {
  const m = item.transform;
  const w = item.width || 8;
  const h = item.height || Math.abs(m[3]) || 10;
  const a = viewport.convertToViewportPoint(m[4], m[5]);
  const b = viewport.convertToViewportPoint(m[4] + w, m[5] + h);
  return {
    left: Math.min(a[0], b[0]),
    top: Math.min(a[1], b[1]),
    width: Math.abs(b[0] - a[0]),
    height: Math.abs(b[1] - a[1]) || 12,
  };
}

function jobIssuesHtml() {
  const job = session?.job;
  if (!job) return "";
  const issues = job.handoff_issues || [];
  const rows = issues
    .map(
      (i) =>
        `<div class="row">${badge(i.review_state)}<span>${escapeHtml(i.code)} — ${escapeHtml(i.message || "")}</span></div>`
    )
    .join("");
  return `<p>Phiên ${escapeHtml(job.job_id || "")} ${badge(job.status)} ${badge(job.review_state)}</p>${rows}`;
}

function renderFacts() {
  const c = session?.contribution;
  if (!c) {
    $("pane-facts").innerHTML = session?.job
      ? `${jobIssuesHtml()}<p class="muted">Trích xuất bị chặn nên chưa có sự kiện. Sửa chất lượng trang hoặc chạy lại sau khi nạp code mới.</p>`
      : '<p class="muted">Chưa chạy trích xuất AI2.</p>';
    return;
  }
  const facts = (c.facts || [])
    .map(
      (f) =>
        `<div class="row">${badge(f.review_state)}<span><strong>${escapeHtml(f.raw_value)}</strong> → ${escapeHtml(f.normalized_value)} <span class="muted">${escapeHtml(f.item_key || f.unit || f.provenance)}</span></span><span>${citeBtn(f.citation)}</span></div>`
    )
    .join("");
  const cands = (c.candidates || [])
    .map(
      (x) =>
        `<div class="row">${badge(x.review_state)}<span>${escapeHtml(viLabel(x.finding_type))} / ${escapeHtml(viLabel(x.model_disposition))} — ${escapeHtml(x.reason)}</span><span></span></div>`
    )
    .join("");
  $("pane-facts").innerHTML = `<p>Phiên ${escapeHtml(session.job?.job_id)} ${badge(session.job?.status)} ${badge(session.job?.review_state)} · mô hình AI ${session.used_llm ? "bật" : "tắt"}</p>
    <h3>Sự kiện</h3>${facts || '<p class="muted">Không có</p>'}
    <h3>Ứng viên đối chiếu</h3>${cands || '<p class="muted">Không có (không kết luận bên nào thắng)</p>'}`;
  $("pane-facts").querySelectorAll("button[data-citation]").forEach((b) => {
    b.onclick = () => verifyCitation(b.getAttribute("data-citation"));
  });
}

function citeBtn(cite) {
  if (!cite || !cite.node_id) return "";
  const verify = cite.citation_id
    ? ` <button type="button" data-citation="${escapeHtml(cite.citation_id)}">verify</button>`
    : "";
  return `<button type="button" data-node="${escapeHtml(cite.node_id)}">${escapeHtml(cite.node_id)}</button>${verify}`;
}

async function verifyCitation(citationId) {
  if (!session || !citationId) return;
  const res = await fetch(`/api/workspace/${session.session_id}/citations/${encodeURIComponent(citationId)}/verify`, { method: "POST" });
  const data = await res.json();
  window.alert(`${citationId}: ${data.valid ? "VALID" : "INVALID"} · ${data.source_text || "không có source text"}`);
}

function factById(id) {
  return (session?.contribution?.facts || []).find((f) => f.fact_id === id);
}

function sourceCard(label, fact, cite) {
  const val = fact ? `${fact.raw_value}${fact.unit ? " " + fact.unit : ""}` : (cite?.text_span || "—");
  const where = fact
    ? `${viLabel(fact.source_role) || ""} · ${fact.subject || fact.validity || ""}`.trim()
    : "";
  return `<div class="src-card"><div class="muted">${escapeHtml(label)}</div><strong>${escapeHtml(val)}</strong><div class="muted">${escapeHtml(where)}</div>${citeBtn(cite)}</div>`;
}

function reviewOf(id) {
  return (session?.reviews || {})[id];
}

function isQueueFinding(x) {
  const d = x.disposition || x.finding_type;
  return ["COMPARABLE_DIFFERENCE", "CANDIDATE_AMENDMENT", "NEEDS_EVIDENCE"].includes(d);
}

function findingCard(x, queued) {
  const left = (x.evidence_left || [])[0];
  const right = (x.evidence_right || [])[0];
  const lf = factById(x.left_id);
  const rf = factById(x.right_id);
  const rev = reviewOf(x.candidate_id);
  const revLine = rev
    ? `<p>${badge(rev.action)} rev ${rev.revision}${rev.stale ? " · cũ sau trích xuất lại" : ""} — ${escapeHtml(rev.reason || "")}</p>`
    : "";
  const actions = queued
    ? `<div class="review-actions">
        <button type="button" data-rev="confirm" data-cid="${escapeHtml(x.candidate_id)}">Xác nhận</button>
        <button type="button" data-rev="correct" data-cid="${escapeHtml(x.candidate_id)}">Sửa overlay</button>
        <button type="button" data-rev="reject" data-cid="${escapeHtml(x.candidate_id)}">Từ chối</button>
      </div>`
    : "";
  return `<div class="finding">${badge(x.disposition || x.finding_type)}
    <div class="finding-ctx">${escapeHtml(viLabel(x.scope))} · ${escapeHtml(x.item_key || "—")}</div>
    <div class="two-src">${sourceCard("Nguồn 1", lf, left)}${sourceCard("Nguồn 2", rf, right)}</div>
    <p class="muted">${escapeHtml(x.reason)}</p>
    ${revLine}${actions}
  </div>`;
}

function renderFindings() {
  const c = session?.contribution;
  if (!c) {
    $("pane-findings").innerHTML = session?.job
      ? `${jobIssuesHtml()}<p class="muted">Không có phát hiện vì pipeline chưa chạy xong.</p>`
      : '<p class="muted">Chạy trích xuất để đối chiếu bán hàng / dịch vụ. Hỏi đáp không bắt buộc.</p>';
    return;
  }
  const all = c.candidates || [];
  const queue = all.filter(isQueueFinding);
  const other = all.filter((x) => !isQueueFinding(x) && x.disposition !== "COMPARABLE_MATCH");
  const matches = all.filter((x) => x.disposition === "COMPARABLE_MATCH");
  const rows = queue.map((x) => findingCard(x, true)).join("");
  const extra = other.map((x) => findingCard(x, false)).join("");
  const matchN = matches.length ? `<p class="muted">${matches.length} cặp khớp — không vào hàng cảnh báo.</p>` : "";
  const issues = (c.evidence_issues || [])
    .map(
      (i) =>
        `<div class="row">${badge("NEEDS_EVIDENCE")}<span>Thiếu ${escapeHtml(i.missing)} — ${escapeHtml(i.reason)}</span><span>${citeBtn(i.citation)}</span></div>`
    )
    .join("");
  $("pane-findings").innerHTML = `<p class="muted">Hàng việc: khác biệt / sửa đổi / thiếu kỳ. Không kết luận bên nào thắng. Coverage ≠ độ chính xác.</p>
    ${session?.reviews_stale ? '<p class="err">Review cũ đã stale sau lần trích xuất mới.</p>' : ""}
    <h3>Hàng review</h3>${rows || '<p class="muted">Không có</p>'}
    <h3>Không so được / khác phạm vi</h3>${extra || '<p class="muted">Không có</p>'}
    ${matchN}
    <h3>Thiếu chứng cứ / phủ sóng</h3>${issues || '<p class="muted">Không có vấn đề</p>'}
    <pre class="mono">${escapeHtml(JSON.stringify(c.coverage || {}, null, 2))}</pre>`;
  $("pane-findings").querySelectorAll("button[data-node]").forEach((b) => {
    b.onclick = () => jumpToNode(b.getAttribute("data-node"));
  });
  $("pane-findings").querySelectorAll("button[data-rev]").forEach((b) => {
    b.onclick = () => submitReview(b.getAttribute("data-cid"), b.getAttribute("data-rev"));
  });
}

async function submitReview(cid, action) {
  let reason = "";
  let overlay_text = null;
  if (action === "reject") {
    reason = window.prompt("Lý do từ chối (bắt buộc)") || "";
    if (!reason.trim()) return;
  }
  if (action === "correct") {
    overlay_text = window.prompt("Overlay (không sửa OCR/PDF gốc)") || "";
    reason = overlay_text || "correct";
  }
  const res = await fetch(`/api/workspace/${session.session_id}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ candidate_id: cid, action, reason, overlay_text }),
  });
  const data = await res.json();
  if (!res.ok) {
    window.alert(data.detail || res.status);
    return;
  }
  applySession(data, "extract", { keepPdf: true });
  document.querySelector('.tab[data-tab="findings"]')?.click();
}

function renderReasonList() {
  const renderTasks = (items) =>
    items
      .map(
        (t) =>
          `<div class="task-row"><button data-task="${t.id}">${t.id}</button><span>${escapeHtml(t.query)}</span> ${badge(t.expected_state)} ` +
          `<small class="muted">${t.applicable === false ? "probe · không áp dụng" : t.kind === "probe" ? "probe" : "product"}</small>` +
          `${t.expected_reason ? `<div class="muted">${escapeHtml(t.expected_reason)}</div>` : ""}</div>`
      )
      .join("");
  const product = tasks.filter((t) => t.kind !== "probe");
  const probes = tasks.filter((t) => t.kind === "probe");
  $("pane-reason").innerHTML =
    "<p class=\"muted\">Chọn nhiệm vụ. Mọi câu trả lời đều neo nguồn (tầng L3).</p>" +
    `<h3>Task sản phẩm</h3>${renderTasks(product) || '<p class="muted">Không có task áp dụng.</p>'}` +
    `<h3>Probe an toàn / thiếu chứng cứ</h3>${renderTasks(probes) || '<p class="muted">Không có probe.</p>'}` +
    `<div id="reason-out"></div>`;
  $("pane-reason").querySelectorAll("button[data-task]").forEach((b) => {
    b.onclick = () => runReason(b.getAttribute("data-task"));
  });
  if (lastReason) paintReason(lastReason);
}

function paintReason(out) {
  const box = $("reason-out") || document.createElement("div");
  if (!$("reason-out")) {
    box.id = "reason-out";
    $("pane-reason").appendChild(box);
  }
  const layers = (out.layers_used || []).map((l) => `<span class="layer">${l}</span>`).join(" ");
  const expected = tasks.find((item) => item.id === out.task_id);
  const match = expected && expected.expected_state === out.review_state;
  const comparison = expected
    ? `<span class="badge ${match ? "PASS" : "NEEDS_REVIEW"}">${match ? "MATCH" : "MISMATCH"}</span> kỳ vọng ${badge(expected.expected_state)}`
    : "";
  const cites = (out.citations || [])
    .map(
      (c) =>
        `<div class="mono"><button type="button" data-node="${escapeHtml(c.node_id)}">${escapeHtml(c.node_id)}</button> · ${escapeHtml(c.text_span)}</div>`
    )
    .join("");
  const ans = typeof out.answer === "string" ? out.answer : JSON.stringify(out.answer, null, 2);
  box.innerHTML = `<hr/><p>${escapeHtml(out.task_id || "")} ${badge(out.review_state)} ${comparison} ${layers}</p>
    <pre class="mono">${escapeHtml(ans)}</pre>
    <strong>Nguồn dẫn</strong>${cites || '<p class="muted">—</p>'}
    ${traceHtml(out)}
    ${out.relation_issues?.length ? `<h4>Graph issue</h4><pre class="mono">${escapeHtml(JSON.stringify(out.relation_issues, null, 2))}</pre>` : ""}`;
  box.querySelectorAll("button[data-node]").forEach((b) => {
    b.onclick = () => jumpToNode(b.getAttribute("data-node"));
  });
}

function renderOut() {
  if (!session?.job) {
    $("pane-out").innerHTML = '<p class="muted">Kết quả xuất hiện sau trích xuất / tra cứu. Chỉ mục chỉ đề xuất, không tự công bố.</p>';
    return;
  }
  if (!session.contribution) {
    $("pane-out").innerHTML = `${jobIssuesHtml()}<p class="muted">Không có JSON phát hiện vì job thất bại hoặc bị chặn.</p>`;
    return;
  }
  const c = session.contribution || {};
  const snap = {
    findings: c.candidates || [],
    evidence_issues: c.evidence_issues || [],
    coverage: c.coverage || {},
    publish: c.publish || "propose",
    reviews: session.reviews || {},
    reviews_stale: session.reviews_stale || false,
  };
  $("pane-out").innerHTML = `
    <div class="stat">
      <div><b>${(c.facts || []).length}</b><div class="muted">sự kiện (mẫu)</div></div>
      <div><b>${(c.candidates || []).length}</b><div class="muted">phát hiện</div></div>
      <div><b>${(c.evidence_issues || []).length}</b><div class="muted">thiếu chứng cứ</div></div>
    </div>
    <p>Trạng thái hồ sơ ${badge(session.job.review_state)}. Công bố AI2 = <code>${viLabel(c.publish || "propose")}</code>${session.published ? " · cổng người dùng đã bấm" : ""}.</p>
    ${lastReason ? traceHtml(lastReason) : ""}
    <p class="muted">Coverage là mức xử lý, không phải độ chính xác. Overlay không sửa PDF/OCR.</p>
    <button type="button" id="btn-export-json">Tải JSON</button>
    <button type="button" id="btn-export-csv">Tải CSV hàng review</button>
    <button type="button" id="btn-publish" ${session.authoritative_publish_blocked ? 'disabled title="pending_review"' : ""}>Cổng công bố (index vẫn đề xuất)</button>
    <pre class="mono" id="export-json">${escapeHtml(JSON.stringify({ ...snap, reviews: session.reviews || {} }, null, 2))}</pre>
    ${lastReason ? `<p>Tra cứu gần nhất ${badge(lastReason.review_state)}</p>` : ""}
  `;
  const btn = $("btn-export-json");
  if (btn) {
    btn.onclick = () => {
      const blob = new Blob([JSON.stringify(snap, null, 2)], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "ai2-findings.json";
      a.click();
    };
  }
  const csvBtn = $("btn-export-csv");
  if (csvBtn) {
    csvBtn.onclick = () => {
      const lines = ["candidate_id,item_key,scope,disposition,review_action,reason"];
      (c.candidates || []).forEach((x) => {
        const r = (session.reviews || {})[x.candidate_id] || {};
        lines.push([x.candidate_id, x.item_key, x.scope, x.disposition, r.action || "", (r.reason || "").replaceAll(",", " ")].join(","));
      });
      const blob = new Blob([lines.join("\n")], { type: "text/csv" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = "ai2-review-queue.csv";
      a.click();
    };
  }
  const pub = $("btn-publish");
  if (pub) {
    pub.onclick = async () => {
      const res = await fetch(`/api/workspace/${session.session_id}/publish`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirm: true }),
      });
      const data = await res.json();
      if (!res.ok) {
        window.alert(data.detail || res.status);
        return;
      }
      applySession(data, "result", { keepPdf: true });
    };
  }
}

function applySession(data, stepName, opts) {
  const keepPdf = opts && opts.keepPdf && session && session.session_id === data.session_id;
  session = data;
  if (!keepPdf) {
    pdfCache = { id: null, doc: null };
    currentFileId = (data.files && data.files[0] && data.files[0].file_id) || null;
    pageInFile = 1;
    page = 1;
  }
  showWork(true);
  setStep(stepName || data.step || "reconstruct");
  renderStruct();
  renderFacts();
  renderFindings();
  renderOut();
  renderGraphPane();
  refreshGraphPane();
  if (!keepPdf) showPage();
}

async function loadCaseChoices() {
  const select = $("sample-case");
  if (!select) return;
  try {
    const cases = await fetch("/api/cases").then((r) => r.json());
    cases.forEach((item) => {
      const option = document.createElement("option");
      option.value = item.case_id;
      option.textContent = `${item.case_id} · ${item.title} · ${item.expected_state}`;
      select.appendChild(option);
    });
  } catch (err) {
    select.innerHTML = '<option value="">Không tải được catalog case</option>';
  }
}

async function openEvalCase() {
  const id = $("sample-case")?.value;
  if (!id) return;
  $("ingest-err").textContent = "";
  const res = await fetch(`/api/workspace/case/${encodeURIComponent(id)}`, { method: "POST" });
  const data = await res.json();
  if (!res.ok) {
    $("ingest-err").textContent = "Không mở được case: " + escapeHtml(JSON.stringify(data.detail || data));
    return;
  }
  applySession(data, "reconstruct");
  renderTimeline(-1, 0);
  tasks = await fetch(`/api/workspace/${session.session_id}/tasks`).then((r) => r.json());
  renderReasonList();
}

async function openSample() {
  $("ingest-err").textContent = "";
  setStep("reconstruct");
  const data = await fetch("/api/workspace/sample", { method: "POST" }).then((r) => r.json());
  page = 1;
  applySession(data, "reconstruct");
  renderTimeline(-1, 0);
  tasks = await fetch(`/api/workspace/${session.session_id}/tasks`).then((r) => r.json());
  renderReasonList();
  await extract();
}

async function openCompareSample() {
  $("ingest-err").textContent = "";
  const data = await fetch("/api/workspace/sample-compare", { method: "POST" }).then((r) => r.json());
  page = 1;
  applySession(data, "extract");
  renderTimeline(-1, STAGES.length);
  tasks = await fetch(`/api/workspace/${session.session_id}/tasks`).then((r) => r.json());
  renderReasonList();
  const tab = document.querySelector('.tab[data-tab="findings"]');
  if (tab) tab.click();
}

async function uploadFiles(fileList) {
  $("ingest-err").textContent = "";
  const fd = new FormData();
  [...fileList].forEach((f) => fd.append("files", f));
  const res = await fetch("/api/workspace/upload", { method: "POST", body: fd });
  if (!res.ok) {
    let detail = res.status;
    try {
      const err = await res.json();
      detail = err.detail ? JSON.stringify(err.detail) : res.status;
    } catch (e) {
      /* ignore */
    }
    $("ingest-err").textContent = "Không nhận tệp: " + detail;
    return;
  }
  page = 1;
  applySession(await res.json(), "reconstruct");
  renderTimeline(-1, 0);
  tasks = await fetch(`/api/workspace/${session.session_id}/tasks`).then((r) => r.json());
  renderReasonList();
}

async function uploadSnapshotFile(file, optionalPdf = null) {
  $("ingest-err").textContent = "";
  try {
    const snapshot = JSON.parse(await file.text());
    const isResult = snapshot?.machine?.schema_version === "0.1";
    let res;
    if (isResult && optionalPdf) {
      const fd = new FormData();
      fd.append("artifact", file);
      fd.append("pdf", optionalPdf);
      res = await fetch("/api/workspace/ai1-result", { method: "POST", body: fd });
    } else {
      res = await fetch(isResult ? "/api/workspace/ai1-result" : "/api/workspace/ai1-snapshot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(snapshot),
      });
    }
    const data = await res.json();
    if (!res.ok) {
      $("ingest-err").textContent = "Không nhận snapshot AI1: " + (data.detail || res.status);
      return;
    }
    page = 1;
    applySession(data, "reconstruct");
    renderTimeline(-1, 0);
    tasks = await fetch(`/api/workspace/${session.session_id}/tasks`).then((r) => r.json());
    renderReasonList();
  } catch (err) {
    $("ingest-err").textContent = "JSON snapshot không hợp lệ: " + String(err);
  }
}

function handleSelectedFiles(fileList) {
  const files = [...fileList];
  const snapshots = files.filter((file) => file.name.toLowerCase().endsWith(".json"));
  if (snapshots.length) {
    const pdfs = files.filter((file) => file.name.toLowerCase().endsWith(".pdf"));
    if (snapshots.length !== 1 || files.length > 2 || (files.length === 2 && !pdfs.length)) {
      $("ingest-err").textContent = "Snapshot AI1 phải được nạp riêng một tệp JSON.";
      return;
    }
    return uploadSnapshotFile(snapshots[0], pdfs[0] || null);
  }
  return uploadFiles(files);
}

async function extract() {
  if (!session) return;
  $("btn-extract").disabled = true;
  for (let i = 0; i < STAGES.length; i++) {
    renderTimeline(i, i);
    await new Promise((r) => setTimeout(r, 180));
  }
  try {
    const res = await fetch(`/api/workspace/${session.session_id}/extract`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ use_llm: $("use-llm").checked }),
    });
    const data = await res.json();
    if (!res.ok) {
      $("pane-facts").innerHTML = `<p class="muted">Lỗi trích xuất: ${escapeHtml(JSON.stringify(data.detail || data))}</p>`;
      document.querySelector('.tab[data-tab="facts"]')?.click();
      return;
    }
    renderTimeline(-1, STAGES.length);
    applySession(data, "extract", { keepPdf: true });
    if (!session.tasksLoaded) {
      tasks = await fetch(`/api/workspace/${session.session_id}/tasks`).then((r) => r.json());
      session.tasksLoaded = true;
      renderReasonList();
    }
    const tabName =
      session?.source === "compare" || (session?.contribution?.candidates || []).length
        ? "findings"
        : "facts";
    const tab = document.querySelector(`.tab[data-tab="${tabName}"]`);
    if (tab) tab.click();
  } catch (err) {
    $("pane-facts").innerHTML = `<p class="muted">Không gọi được API trích xuất: ${escapeHtml(String(err))}</p>`;
    document.querySelector('.tab[data-tab="facts"]')?.click();
  } finally {
    $("btn-extract").disabled = false;
    renderTimeline(-1, STAGES.length);
  }
}

async function runReason(taskId) {
  setStep("reason");
  const out = await fetch(`/api/workspace/${session.session_id}/reason`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task_id: taskId, use_llm: $("use-llm").checked, use_vector: $("use-vector").checked }),
  }).then((r) => r.json());
  lastReason = out;
  paintReason(out);
  setStep("result");
  renderOut();
}

$("pick").onclick = () => $("file").click();
$("file").onchange = () => {
  if ($("file").files.length) handleSelectedFiles($("file").files);
};
$("pick-snapshot").onclick = () => $("snapshot-file").click();
$("snapshot-file").onchange = () => {
  if ($("snapshot-file").files.length) uploadSnapshotFile($("snapshot-file").files[0]);
};
$("sample").onclick = openSample;
$("sample-compare").onclick = openCompareSample;
$("load-case").onclick = openEvalCase;
["dragenter", "dragover"].forEach((ev) => {
  $("drop").addEventListener(ev, (e) => {
    e.preventDefault();
    $("drop").classList.add("drag");
  });
});
["dragleave", "drop"].forEach((ev) => {
  $("drop").addEventListener(ev, (e) => {
    e.preventDefault();
    $("drop").classList.remove("drag");
  });
});
$("drop").addEventListener("drop", (e) => {
  if (e.dataTransfer.files.length) handleSelectedFiles(e.dataTransfer.files);
});
$("btn-extract").onclick = extract;
$("tree-filter").oninput = () => session && renderTree();
$("askform").onsubmit = async (e) => {
  e.preventDefault();
  if (!session) return;
  const q = $("ask").value.trim();
  if (!q) return;
  setStep("reason");
  $("ask-out").innerHTML = "<p>Đang tra cứu…</p>";
  const out = await fetch(`/api/workspace/${session.session_id}/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query: q, use_llm: $("use-llm").checked, use_vector: $("use-vector").checked }),
  }).then((r) => r.json());
  lastReason = out;
  const layers = (out.layers_used || []).map((l) => `<span class="layer">${l}</span>`).join(" ");
  const ans = typeof out.answer === "string" ? out.answer : JSON.stringify(out.answer, null, 2);
  const cites = (out.citations || [])
    .map(
      (c) =>
        `<button type="button" data-node="${escapeHtml(c.node_id)}">${escapeHtml(c.node_id)}</button>`
    )
    .join(" ");
  $("ask-out").innerHTML = `<p>${badge(out.review_state)} ${layers} · ${escapeHtml(out.task?.type || "")}</p>
    <pre class="mono">${escapeHtml(ans)}</pre>
    <p>Nguồn dẫn ${cites || "—"}</p>${traceHtml(out)}`;
  $("ask-out").querySelectorAll("button[data-node]").forEach((b) => {
    b.onclick = () => jumpToNode(b.getAttribute("data-node"));
  });
  const first = (out.locations || [])[0] || (out.citations || [])[0];
  const nid = first && (first.node_id || first);
  if (nid && typeof nid === "string") jumpToNode(nid);
  setStep("result");
};
$("btn-reset").onclick = () => {
  session = null;
  lastReason = null;
  pdfCache = { id: null, doc: null };
  currentFileId = null;
  showWork(false);
  setStep("ingest");
};
$("prev").onclick = () => {
  pageInFile -= 1;
  page -= 1;
  showPage();
};
$("next").onclick = () => {
  pageInFile += 1;
  page += 1;
  showPage();
};
document.querySelectorAll(".tab").forEach((t) => {
  t.onclick = () => {
    document.querySelectorAll(".tab").forEach((x) => x.classList.remove("on"));
    t.classList.add("on");
    ["struct", "facts", "findings", "graph", "reason", "out"].forEach((id) => {
      $(`pane-${id}`).classList.toggle("hidden", t.getAttribute("data-tab") !== id);
    });
  };
});

loadHealth();
loadCaseChoices();
