const $ = (id) => document.getElementById(id);
let selected = null;
let cases = [];
let detail = null;

const escapeHtml = (value) => String(value ?? "")
  .replaceAll("&", "&amp;")
  .replaceAll("<", "&lt;")
  .replaceAll(">", "&gt;");
const badge = (state) => `<span class="badge ${escapeHtml(state || "")}">${escapeHtml(state || "—")}</span>`;

function traceHtml(out) {
  const trace = out?.retrieval_trace || {};
  return `<details class="trace"><summary>Retrieval/LLM trace</summary><pre class="mono">${escapeHtml(JSON.stringify({
    vector_status: trace.vector_status || (out?.use_vector ? "REQUESTED" : "NOT_REQUESTED"),
    embedding_model: trace.embedding_model,
    embedding_dimensions: trace.embedding_dimensions,
    vector_hits: trace.vector_hits,
    used_llm: out?.used_llm,
    llm_trace: out?.llm_trace,
  }, null, 2))}</pre></details>`;
}

async function jsonFetch(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail || data));
  return data;
}

async function loadHealth() {
  try {
    const h = await jsonFetch("/health");
    const embedding = h.embedding || {};
    $("health").textContent = `LLM ${h.llm}: ${h.model || "—"} · Embedding ${embedding.status || "NOT_RUN"}`;
  } catch (error) {
    $("health").textContent = "Health unavailable";
  }
}

function filteredCases() {
  const query = ($("filter").value || "").toLowerCase();
  const group = $("group-filter").value;
  const state = $("state-filter").value;
  return cases.filter((item) => {
    const text = `${item.case_id} ${item.title} ${item.scenario || ""}`.toLowerCase();
    const isSynthetic = (item.tags || []).includes("synthetic");
    return text.includes(query)
      && (!group || (group === "synthetic" ? isSynthetic : !isSynthetic))
      && (!state || item.expected_state === state);
  });
}

function renderCases() {
  const list = filteredCases();
  $("count").textContent = `${list.length}/${cases.length} case`;
  $("cases").innerHTML = list.map((item) => {
    const group = (item.tags || []).includes("synthetic") ? "synthetic" : "catalog";
    return `<button class="case${selected === item.case_id ? " primary" : ""}" data-case="${escapeHtml(item.case_id)}">
      <strong>${escapeHtml(item.case_id)}</strong> ${badge(item.expected_state)}
      <small>${escapeHtml(item.title)} · ${group} · ${item.n_pages} trang · ${item.n_tables} bảng</small>
    </button>`;
  }).join("") || '<p class="muted">Không có case phù hợp.</p>';
  $("cases").querySelectorAll("button[data-case]").forEach((button) => {
    button.onclick = () => selectCase(button.getAttribute("data-case"));
  });
}

async function selectCase(caseId) {
  selected = caseId;
  renderCases();
  detail = await jsonFetch(`/api/cases/${encodeURIComponent(caseId)}`);
  $("runL0").disabled = $("runLlm").disabled = $("runQ").disabled = false;
  $("q").value = detail.query || "";
  const tableMeta = (detail.tables || []).map((table) => `<li>${escapeHtml(table.title || table.table_id)} · ${table.n_rows} dòng</li>`).join("");
  $("meta").innerHTML = `<h2>${escapeHtml(detail.case_id)} ${badge(detail.expected_state)}</h2>
    <p>${escapeHtml(detail.title)}</p><p class="muted">${escapeHtml(detail.notes || detail.scenario || "")}</p>
    <div class="stat"><div><b>${detail.n_pages}</b><div class="muted">trang</div></div><div><b>${detail.n_nodes}</b><div class="muted">node</div></div><div><b>${detail.n_tables}</b><div class="muted">bảng</div></div></div>
    <p class="mono">input=${escapeHtml(detail.input_kind)} · query=${escapeHtml(detail.query || "—")}</p>
    <p>Policy: deterministic=${escapeHtml(detail.policy?.deterministic || "—")} · external=${escapeHtml(detail.policy?.external || "—")}</p>
    ${(detail.policy?.gates || []).map((gate) => `<div class="row">${badge(gate.code)}<span>${escapeHtml(gate.operation)}</span><span class="muted">${escapeHtml(gate.deterministic_action)}</span></div>`).join("")}
    <h3>Bảng input</h3><ul>${tableMeta || "<li>Không có</li>"}</ul>
    <details><summary>Expected no-claims</summary><pre class="mono">${escapeHtml(JSON.stringify(detail.expected_no_claims || [], null, 2))}</pre></details>`;
  $("result").innerHTML = '<p class="muted">Đã chọn case. Chạy deterministic hoặc live LLM.</p>';
}

function citationsHtml(citations) {
  return (citations || []).map((citation) => `<div class="row"><span class="mono">${escapeHtml(citation.node_id || "—")}</span><span>${escapeHtml(citation.text_span || "")}</span></div>`).join("") || '<p class="muted">Không có citation.</p>';
}

function renderResult(out, label) {
  const answer = typeof out.answer === "string" ? out.answer : JSON.stringify(out.answer, null, 2);
  const edges = (out.relation_edges || []).map((edge) => `<div class="row">${badge(edge.review_state)} <span>${escapeHtml(edge.relation_type)}: ${escapeHtml(edge.from_node_id)} → ${escapeHtml(edge.to_node_id)}</span></div>`).join("");
  const issues = [...(out.evidence_issues || []), ...(out.relation_issues || [])].map((issue) => `<div class="row">${badge(issue.review_state || "NEEDS_REVIEW")}<span>${escapeHtml(issue.missing || issue.code || "issue")} — ${escapeHtml(issue.reason || issue.message || "")}</span></div>`).join("");
  $("result").innerHTML = `<p>${escapeHtml(label)} · ${badge(out.review_state)} · ${escapeHtml((out.layers_used || []).join(" → "))}</p>
    <div class="result-grid"><div><h3>Answer</h3><pre class="mono">${escapeHtml(answer || "—")}</pre></div><div><h3>Citation</h3>${citationsHtml(out.citations)}</div></div>
    <h3>Relation edges</h3>${edges || '<p class="muted">Không có edge trực tiếp.</p>'}
    <h3>Evidence issues</h3>${issues || '<p class="muted">Không có.</p>'}
    ${traceHtml(out)}
    <details><summary>Raw response</summary><pre class="mono">${escapeHtml(JSON.stringify(out, null, 2))}</pre></details>`;
}

async function run(useLlm) {
  if (!selected) return;
  $("runL0").disabled = $("runLlm").disabled = true;
  $("result").innerHTML = `<p>Đang chạy ${useLlm ? "live LLM" : "deterministic"}…</p>`;
  try {
    const out = await jsonFetch(`/api/cases/${encodeURIComponent(selected)}/run`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ use_llm: useLlm }),
    });
    renderResult({ ...out.job, used_llm: out.used_llm }, useLlm ? "Live LLM extraction" : "Deterministic extraction");
  } catch (error) {
    $("result").innerHTML = `<p class="err">Run lỗi: ${escapeHtml(error.message)}</p>`;
  } finally {
    $("runL0").disabled = $("runLlm").disabled = false;
  }
}

$("filter").oninput = renderCases;
$("group-filter").onchange = renderCases;
$("state-filter").onchange = renderCases;
$("runL0").onclick = () => run(false);
$("runLlm").onclick = () => run(true);
$("qform").onsubmit = async (event) => {
  event.preventDefault();
  if (!selected) return;
  $("result").innerHTML = "<p>Đang tra cứu…</p>";
  try {
    const out = await jsonFetch(`/api/cases/${encodeURIComponent(selected)}/query`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: $("q").value, use_llm: $("use-llm").checked, use_vector: $("use-vector").checked }),
    });
    renderResult(out, `Query · vector=${$("use-vector").checked ? "on" : "off"}`);
  } catch (error) {
    $("result").innerHTML = `<p class="err">Query lỗi: ${escapeHtml(error.message)}</p>`;
  }
};

async function init() {
  await Promise.all([loadHealth(), jsonFetch("/api/cases").then((data) => { cases = data; renderCases(); })]);
}
init();
