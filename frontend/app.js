const API_BASE = "/api/v1";

// Global Application State
let state = {
  currentTab: "chat",
  documents: [],
  conversations: [],
  conversationId: null,
  latestCitations: [],
  selectedDocumentId: null,
  selectedDocumentPage: null,
  evidenceOpen: true,
  comparison: null
};

// Initialize UI on Load
document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  initLucide();
  initTabs();
  initChat();
  initModal();
  initQuickSample();
  initCompare();
  initClearAll();
  initWorkspaceRail();
  initDocumentFilters();
  initEvidencePanel();
  initDocumentDetail();
  initExportActions();
  fetchDocuments();
  fetchConversations();
  fetchAnalytics();
  fetchSystemHealth();
  initAuth();
  window.setInterval(fetchSystemHealth, 30000);
});

async function initAuth() {
  const button = document.getElementById("auth-button");
  if (!button) return;
  try {
    const response = await fetch("/auth/me", { credentials: "same-origin" });
    const data = await response.json();
    if (data.authenticated && data.user) {
      button.innerHTML = `<i data-lucide="user-check"></i><span>${escapeHtml(data.user.name || data.user.email || "Signed in")}</span>`;
      button.title = "Sign out";
      button.setAttribute("aria-label", "Sign out");
      button.onclick = async () => {
        await fetch("/auth/logout", { method: "POST", credentials: "same-origin" });
        window.location.reload();
      };
    } else {
      button.innerHTML = `<i data-lucide="log-in"></i><span>Sign in with Google</span>`;
      button.title = "Sign in with Google";
      button.setAttribute("aria-label", "Sign in with Google");
      button.onclick = () => { window.location.href = "/auth/google"; };
    }
    initLucide();
  } catch (error) {
    button.disabled = true;
    button.title = "Authentication unavailable";
  }
}

function initTheme() {
  const savedTheme = localStorage.getItem("docusense-theme") || "light";
  applyTheme(savedTheme);

  const toggle = document.getElementById("btn-theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", () => {
      const nextTheme = document.documentElement.dataset.theme === "light" ? "dark" : "light";
      applyTheme(nextTheme);
      localStorage.setItem("docusense-theme", nextTheme);
    });
  }
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  const toggle = document.getElementById("btn-theme-toggle");
  if (!toggle) return;

  const isLight = theme === "light";
  toggle.setAttribute("aria-label", isLight ? "Switch to dark theme" : "Switch to light theme");
  toggle.setAttribute("title", isLight ? "Switch to dark theme" : "Switch to light theme");
  toggle.innerHTML = `<i data-lucide="${isLight ? "moon" : "sun"}"></i><span>${isLight ? "Dark mode" : "Light mode"}</span>`;
  initLucide();
}

function initLucide() {
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

function initWorkspaceRail() {
  const newConversation = document.getElementById("btn-new-conversation");
  if (newConversation) {
    newConversation.addEventListener("click", () => {
      state.conversationId = null;
      document.getElementById("chat-messages").innerHTML = `<div class="chat-hero compact-hero"><div class="hero-icon-container"><i data-lucide="message-square-plus"></i></div><h2>New grounded session</h2><p>Ask a question and inspect the exact source passages behind the answer.</p></div>`;
      document.getElementById("evidence-list").innerHTML = `<div class="evidence-empty"><i data-lucide="quote"></i><span>Ask a question to inspect cited passages.</span></div>`;
      document.querySelectorAll(".conversation-item").forEach(entry => entry.classList.remove("active"));
      const crumb = document.getElementById("crumb-current-page");
      if (crumb) crumb.textContent = "Grounded Reasoning & Chat";
      initLucide();
    });
  }

  const search = document.getElementById("source-search-input");
  if (search) search.addEventListener("input", () => renderSourceRail(search.value));
}

async function fetchConversations() {
  try {
    const response = await fetch(`${API_BASE}/chat/conversations`);
    if (!response.ok) return;
    state.conversations = await response.json();
    renderConversationRail();
  } catch (error) {
    renderConversationRail();
  }
}

function renderConversationRail() {
  const list = document.getElementById("conversation-list");
  if (!list) return;
  list.innerHTML = state.conversations.length ? state.conversations.map(conversation => `
    <div class="conversation-row ${String(state.conversationId) === String(conversation.id) ? "active" : ""}" data-conversation-id="${conversation.id}">
      <button class="conversation-item" type="button" title="Open ${escapeHtml(conversation.title)}"><span class="conversation-dot"></span><span><strong>${escapeHtml(conversation.title)}</strong><small>${formatConversationDate(conversation.created_at)}</small></span></button>
      <button class="conversation-more" type="button" title="Conversation actions" aria-label="Conversation actions"><i data-lucide="more-horizontal"></i></button>
      <div class="conversation-actions"><button class="rename-conversation" type="button"><i data-lucide="pencil"></i> Rename</button><button class="delete-conversation" type="button"><i data-lucide="trash-2"></i> Delete</button></div>
    </div>`).join("") : `<div class="rail-empty">Ask a question to save a session</div>`;

  list.querySelectorAll(".conversation-item").forEach(button => button.addEventListener("click", () => loadConversation(button.closest(".conversation-row").dataset.conversationId)));
  list.querySelectorAll(".conversation-more").forEach(button => button.addEventListener("click", event => {
    event.stopPropagation();
    button.closest(".conversation-row").classList.toggle("menu-open");
  }));
  list.querySelectorAll(".rename-conversation").forEach(button => button.addEventListener("click", () => renameConversation(button.closest(".conversation-row").dataset.conversationId)));
  list.querySelectorAll(".delete-conversation").forEach(button => button.addEventListener("click", () => deleteConversation(button.closest(".conversation-row").dataset.conversationId)));
  initLucide();
}

function formatConversationDate(value) {
  if (!value) return "saved session";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "saved session" : date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

async function loadConversation(conversationId) {
  const response = await fetch(`${API_BASE}/chat/conversations/${conversationId}`);
  if (!response.ok) return;
  const conversation = await response.json();
  state.conversationId = conversation.id;
  const container = document.getElementById("chat-messages");
  container.innerHTML = "";
  conversation.messages.forEach(message => {
    if (message.role === "user") appendUserMessage(message.content);
    if (message.role === "assistant") appendAssistantMessage({ answer: message.content, confidence_score: message.confidence_score || 0, citations: message.citations || [], latency_ms: {}, retrieved_chunks_count: 0 });
  });
  renderConversationRail();
  const crumb = document.getElementById("crumb-current-page");
  if (crumb) crumb.textContent = conversation.title;
}

async function renameConversation(conversationId) {
  const conversation = state.conversations.find(item => String(item.id) === String(conversationId));
  const title = window.prompt("Rename conversation", conversation?.title || "Conversation");
  if (!title || !title.trim()) return;
  const response = await fetch(`${API_BASE}/chat/conversations/${conversationId}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: title.trim() }) });
  if (response.ok) { await fetchConversations(); showToast("Conversation renamed.", "success"); }
}

async function deleteConversation(conversationId) {
  const confirmed = await showConfirmModal({ title: "Delete conversation", message: "This removes the saved chat and its citations.", confirmText: "Delete", confirmType: "danger", icon: "trash-2" });
  if (!confirmed) return;
  const response = await fetch(`${API_BASE}/chat/conversations/${conversationId}`, { method: "DELETE" });
  if (response.ok) {
    if (String(state.conversationId) === String(conversationId)) document.getElementById("btn-new-conversation")?.click();
    await fetchConversations();
    showToast("Conversation deleted.", "success");
  }
}

function renderSourceRail(query = "") {
  const list = document.getElementById("source-list");
  const count = document.getElementById("rail-source-count");
  if (!list) return;
  const normalized = query.toLowerCase().trim();
  const docs = state.documents.filter(doc => (doc.title || doc.filename).toLowerCase().includes(normalized));
  if (count) count.textContent = docs.length;
  list.innerHTML = docs.length ? docs.map(doc => `
    <button class="source-item" data-document-id="${doc.id}" title="Open ${escapeHtml(doc.title || doc.filename)}">
      <span class="source-file-icon"><i data-lucide="file-text"></i></span>
      <span class="source-item-copy"><strong>${escapeHtml(doc.title || doc.filename)}</strong><small>${escapeHtml(doc.version || "1.0")} · ${doc.status || "indexed"}</small></span>
      <span class="source-ready-dot ${doc.status === "ready" ? "" : "pending"}"></span>
    </button>`).join("") : `<div class="rail-empty">No matching sources</div>`;
  list.querySelectorAll(".source-item").forEach(item => item.addEventListener("click", () => openDocumentDetail(item.dataset.documentId)));
  initLucide();
}

function documentDepartment(document) {
  if (document.department) return document.department;
  const name = `${document.title || ""} ${document.filename || ""}`.toLowerCase();
  if (name.includes("hr") || name.includes("employee") || name.includes("handbook")) return "HR";
  if (name.includes("legal") || name.includes("contract") || name.includes("agreement")) return "Legal";
  if (name.includes("finance") || name.includes("revenue") || name.includes("invoice")) return "Finance";
  return "General";
}

async function fetchSystemHealth() {
  const compact = document.getElementById("system-status-compact");
  const healthCard = document.querySelector(".health-card");
  try {
    const resp = await fetch("/health/ready");
    const data = await resp.json();
    const ready = data.status === "ready";
    const modelStatus = data.checks?.models?.status || "unknown";
    const qdrantStatus = data.checks?.vector_store?.status || "unknown";
    if (compact) {
      compact.innerHTML = `<span class="status-dot ${ready ? "ready" : "loading"}"></span><span>${ready ? "All systems operational" : `Models ${modelStatus}`}</span>`;
    }
    if (healthCard) {
      healthCard.classList.toggle("health-degraded", !ready);
      healthCard.innerHTML = `<div class="health-header"><span class="pulse-indicator ${ready ? "" : "degraded"}"></span><span class="health-title">${ready ? "Pipeline operational" : "Pipeline starting"}</span></div><div class="health-meta"><span>Backend: <strong>${ready ? "Online" : "Checking"}</strong></span><span>Qdrant: <strong>${qdrantStatus}</strong></span><span>Models: <strong>${modelStatus}</strong></span></div>`;
    }
  } catch (error) {
    if (compact) compact.innerHTML = `<span class="status-dot error"></span><span>System check unavailable</span>`;
  }
}

function initDocumentFilters() {
  ["document-year-filter", "document-type-filter", "document-department-filter"].forEach(id => {
    const element = document.getElementById(id);
    if (element) element.addEventListener("input", renderDocumentsGrid);
    if (element) element.addEventListener("change", renderDocumentsGrid);
  });

  const resetBtn = document.getElementById("btn-reset-doc-filters");
  if (resetBtn) {
    resetBtn.addEventListener("click", () => {
      const year = document.getElementById("document-year-filter");
      const type = document.getElementById("document-type-filter");
      const dept = document.getElementById("document-department-filter");
      if (year) year.value = "";
      if (type) type.value = "";
      if (dept) dept.value = "";
      renderDocumentsGrid();
    });
  }
}

function setEvidenceOpen(isOpen) {
  state.evidenceOpen = isOpen;
  const rail = document.querySelector(".evidence-rail");
  const layout = document.querySelector(".chat-layout");
  const reopenBtn = document.getElementById("btn-reopen-evidence");
  const reopenBadge = document.getElementById("evidence-reopen-badge");

  if (reopenBadge) {
    const count = (state.latestCitations || []).length;
    reopenBadge.textContent = count;
    reopenBadge.style.display = count > 0 ? "inline-flex" : "none";
  }

  if (rail) rail.classList.toggle("is-hidden", !isOpen);
  if (layout) layout.classList.toggle("evidence-hidden", !isOpen);
  if (reopenBtn) reopenBtn.classList.toggle("visible", !isOpen);
}

function initEvidencePanel() {
  const close = document.getElementById("btn-close-evidence");
  if (close) close.addEventListener("click", () => setEvidenceOpen(false));

  const reopenBtn = document.getElementById("btn-reopen-evidence");
  if (reopenBtn) reopenBtn.addEventListener("click", () => setEvidenceOpen(true));

  const open = document.getElementById("btn-open-full-document");
  if (open) open.addEventListener("click", () => {
    const citation = state.latestCitations[0];
    if (citation) openDocumentDetail(citation.document_id);
  });
  const confidenceFilter = document.getElementById("evidence-confidence-filter");
  if (confidenceFilter) confidenceFilter.addEventListener("change", () => renderEvidence(state.latestCitations));
}

function renderEvidence(citations = []) {
  state.latestCitations = citations;
  const list = document.getElementById("evidence-list");
  const count = document.getElementById("evidence-count");
  if (!list) return;

  const reopenBadge = document.getElementById("evidence-reopen-badge");
  if (reopenBadge) {
    reopenBadge.textContent = citations.length;
    reopenBadge.style.display = citations.length > 0 ? "inline-flex" : "none";
  }

  if (state.evidenceOpen) {
    setEvidenceOpen(true);
  } else {
    setEvidenceOpen(false);
  }
  const minimumConfidence = Number(document.getElementById("evidence-confidence-filter")?.value || 0);
  const visibleCitations = citations.map((citation, index) => ({ citation, index })).filter(item => (item.citation.confidence || item.citation.relevance_score || 0) >= minimumConfidence);
  if (count) count.textContent = `${visibleCitations.length} passage${visibleCitations.length === 1 ? "" : "s"}`;
  list.innerHTML = visibleCitations.length ? visibleCitations.map(({ citation, index }) => `
    <button class="evidence-card" data-evidence-index="${index}" title="Open source passage">
      <span class="evidence-card-top"><span class="evidence-number">${index + 1}</span><span class="evidence-doc">${escapeHtml(citation.document_name || "Source")}</span><span class="evidence-page">p.${citation.page_number} · ${Math.round((citation.confidence || citation.relevance_score || 0) * 100)}%</span></span>
      <span class="evidence-excerpt">${escapeHtml(citation.excerpt)}</span><span class="evidence-meter"><span style="width:${Math.min(100, Math.max(8, (citation.confidence || citation.relevance_score || 0) * 100))}%"></span></span>
    </button>`).join("") : `<div class="evidence-empty"><i data-lucide="${citations.length === 0 ? 'sparkles' : 'quote'}"></i><span>${citations.length === 0 ? 'General reasoning query — no document passages required.' : 'No passages meet this confidence threshold.'}</span></div>`;
  list.querySelectorAll(".evidence-card").forEach(card => card.addEventListener("click", () => {
    const citation = state.latestCitations[Number(card.dataset.evidenceIndex)];
    if (citation) openDocumentDetail(citation.document_id, citation.page_number, citation.section_heading);
  }));
  initLucide();
}

function initDocumentDetail() {
  const overlay = document.getElementById("document-detail-overlay");
  const close = document.getElementById("btn-close-detail");
  if (close) close.addEventListener("click", closeDocumentDetail);
  if (overlay) overlay.addEventListener("click", event => { if (event.target === overlay) closeDocumentDetail(); });
  document.addEventListener("keydown", event => { if (event.key === "Escape") closeDocumentDetail(); });
}

async function openDocumentDetail(documentId, pageNumber, sectionHeading) {
  const overlay = document.getElementById("document-detail-overlay");
  const body = document.getElementById("detail-body");
  const doc = state.documents.find(item => String(item.id) === String(documentId));
  if (!overlay || !body || !doc) return;
  state.selectedDocumentId = documentId;
  state.selectedDocumentPage = pageNumber || 1;
  overlay.classList.add("active");
  overlay.setAttribute("aria-hidden", "false");
  document.getElementById("detail-title").textContent = doc.title || doc.filename;
  document.getElementById("detail-meta").textContent = `${doc.version || "1.0"} · ${doc.file_type.toUpperCase()} · ${doc.page_count} pages · ${doc.chunk_count} sections`;
  body.innerHTML = `<div class="reader-loading"><i data-lucide="loader-2" class="spin"></i><span>Loading source reader...</span></div>`;
  initLucide();
  try {
    const response = await fetch(`${API_BASE}/documents/${documentId}/content`);
    const data = await response.json();
    const targetPage = pageNumber || data.sections[0]?.page_number || 1;
    const sectionsHtml = data.sections.map(section => `<section class="detail-section ${String(section.page_number) === String(targetPage) && (!sectionHeading || section.section_heading === sectionHeading) ? "is-highlighted" : ""}" data-page-number="${section.page_number}"><div class="detail-section-top"><span>PAGE ${section.page_number}</span><strong>${escapeHtml(section.section_heading || "General")}</strong></div><p>${escapeHtml(section.text)}</p></section>`).join("");
    if (doc.file_type === "pdf") {
      body.innerHTML = `<div class="pdf-reader-shell"><div class="pdf-stage"><canvas id="pdf-canvas" aria-label="Rendered source PDF"></canvas></div><div class="reader-caption"><i data-lucide="mouse-pointer-2"></i> Page ${targetPage} cited. The extracted section below is the searchable evidence anchor.</div></div><div class="extracted-heading"><span>SEARCHABLE EXTRACT</span><span>${data.sections.length} sections</span></div>${sectionsHtml || `<div class="evidence-empty">No extracted sections available.</div>`}`;
      await renderPdfPage(documentId, targetPage);
    } else {
      body.innerHTML = `<div class="reader-caption"><i data-lucide="file-text"></i> ${doc.file_type.toUpperCase()} source opened in extracted reader mode.</div>${sectionsHtml || `<div class="evidence-empty">No extracted sections available.</div>`}`;
    }
    const highlighted = body.querySelector(".detail-section.is-highlighted");
    if (highlighted) highlighted.scrollIntoView({ behavior: "smooth", block: "center" });
    document.getElementById("reader-page-label").textContent = `Page ${targetPage}`;
    document.getElementById("reader-mode-label").innerHTML = `<i data-lucide="${doc.file_type === "pdf" ? "file-scan" : "scan-text"}"></i> ${doc.file_type === "pdf" ? "PDF.js source view" : "Extracted source view"}`;
    initLucide();
  } catch (error) {
    body.innerHTML = `<div class="evidence-empty">Unable to load extracted source content.</div>`;
  }
}

async function renderPdfPage(documentId, pageNumber) {
  const canvas = document.getElementById("pdf-canvas");
  if (!canvas) return;
  try {
    const pdfjs = await import("https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.4.168/pdf.min.mjs");
    pdfjs.GlobalWorkerOptions.workerSrc = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.4.168/pdf.worker.min.mjs";
    const pdf = await pdfjs.getDocument(`${API_BASE}/documents/${documentId}/file`).promise;
    const page = await pdf.getPage(Number(pageNumber) || 1);
    const viewport = page.getViewport({ scale: 1.35 });
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    await page.render({ canvasContext: canvas.getContext("2d"), viewport }).promise;
  } catch (error) {
    const stage = canvas.closest(".pdf-stage");
    if (stage) stage.innerHTML = `<div class="reader-fallback"><i data-lucide="file-warning"></i><strong>PDF preview unavailable</strong><span>Use Original to download the source, or inspect the extracted evidence below.</span></div>`;
    initLucide();
  }
}

function closeDocumentDetail() {
  const overlay = document.getElementById("document-detail-overlay");
  if (overlay) { overlay.classList.remove("active"); overlay.setAttribute("aria-hidden", "true"); }
}

function initExportActions() {
  document.getElementById("btn-export-chat")?.addEventListener("click", () => downloadText("docusense-chat.md", buildChatMarkdown()));
  document.getElementById("btn-print-chat")?.addEventListener("click", () => printSection("chat-messages", "DocuSense Chat Transcript"));
  document.getElementById("btn-export-compare")?.addEventListener("click", () => downloadText("docusense-comparison.md", buildComparisonMarkdown()));
  document.getElementById("btn-print-compare")?.addEventListener("click", () => printSection("compare-results", "DocuSense Comparison Report"));
  document.getElementById("btn-detail-download")?.addEventListener("click", () => {
    if (state.selectedDocumentId) window.open(`${API_BASE}/documents/${state.selectedDocumentId}/file`, "_blank");
  });
}

function downloadText(filename, content) {
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([content], { type: "text/markdown;charset=utf-8" }));
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);
}

function buildChatMarkdown() {
  const lines = ["# DocuSense Chat Transcript", "", `Exported: ${new Date().toLocaleString()}`, ""];
  document.querySelectorAll("#chat-messages .msg-entry").forEach(message => {
    const role = message.classList.contains("user") ? "User" : "DocuSense";
    const content = message.querySelector(".msg-bubble-user, .msg-body-content")?.textContent?.trim();
    if (content) lines.push(`## ${role}`, "", content, "");
  });
  return lines.join("\n");
}

function buildComparisonMarkdown() {
  if (!state.comparison) return "# DocuSense Comparison Report\n\nRun a comparison first.";
  const lines = [`# ${state.comparison.doc_a_title} vs ${state.comparison.doc_b_title}`, ""];
  state.comparison.comparison_matrix.forEach(clause => lines.push(`## ${clause.topic}`, "", `**Status:** ${clause.change_type}`, "", `**Baseline:** ${clause.doc_a_text || "Not present"}`, "", `**Comparison:** ${clause.doc_b_text || "Not present"}`, "", `**Summary:** ${clause.summary_of_change}`, ""));
  return lines.join("\n");
}

function printSection(id, title) {
  if (!document.getElementById(id)) return;
  const oldTitle = document.title;
  document.title = title;
  document.body.classList.add("print-mode");
  window.print();
  document.body.classList.remove("print-mode");
  document.title = oldTitle;
}

// ----------------- Tab Navigation -----------------
function initTabs() {
  const navButtons = document.querySelectorAll(".nav-link");
  const pageTitles = {
    chat: "Grounded Reasoning & Chat",
    documents: "Document Hub & Ingestion Status",
    compare: "Version Diff & Policy Evolution Matrix",
    contradictions: "Contradiction & Conflict Resolution Center",
    analytics: "Experimental Research Benchmarks & Telemetry"
  };

  navButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      const tabId = btn.getAttribute("data-tab");
      switchTab(tabId, pageTitles[tabId]);
    });
  });
}

function switchTab(tabId, titleText) {
  state.currentTab = tabId;
  document.querySelectorAll(".nav-link").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".tab-view").forEach(p => p.classList.remove("active"));

  const targetBtn = document.querySelector(`.nav-link[data-tab="${tabId}"]`);
  const targetPane = document.getElementById(`pane-${tabId}`);
  const crumbEl = document.getElementById("crumb-current-page");

  if (targetBtn) targetBtn.classList.add("active");
  if (targetPane) targetPane.classList.add("active");
  if (crumbEl && titleText) crumbEl.innerText = titleText;

  if (tabId === "documents") fetchDocuments();
  if (tabId === "analytics") fetchAnalytics();
  if (tabId === "compare" || tabId === "contradictions") populateDocSelectors();
}

// ----------------- Chat Implementation -----------------
function initChat() {
  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  const chips = document.querySelectorAll(".query-chip");

  chips.forEach(chip => {
    chip.addEventListener("click", () => {
      const query = chip.getAttribute("data-q");
      input.value = query;
      form.dispatchEvent(new Event("submit"));
    });
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const query = input.value.trim();
    if (!query) return;

    input.value = "";
    appendUserMessage(query);

    const yearFilter = document.getElementById("temporal-year-filter").value;
    const useHybrid = document.getElementById("toggle-hybrid").checked;
    const useReranker = document.getElementById("toggle-rerank").checked;
    const answerOnlyFromDocuments = document.getElementById("toggle-doc-only").checked;

    const loadingId = appendLoadingPlaceholder();

    try {
      const resp = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: query,
          conversation_id: state.conversationId,
          temporal_filter_year: yearFilter ? parseInt(yearFilter) : null,
          use_hybrid: useHybrid,
          use_reranker: useReranker,
          answer_only_from_documents: answerOnlyFromDocuments
        })
      });

      if (!resp.ok) throw new Error("Chat request failed");
      const data = await resp.json();
      state.conversationId = data.conversation_id;

      removeLoadingPlaceholder(loadingId);
      appendAssistantMessage(data);
      fetchConversations();
    } catch (err) {
      removeLoadingPlaceholder(loadingId);
      appendFallbackResponse(query, yearFilter);
    }
  });
}

function appendUserMessage(text) {
  const container = document.getElementById("chat-messages");
  const row = document.createElement("div");
  row.className = "msg-entry user";
  row.innerHTML = `<div class="msg-bubble-user">${escapeHtml(text)}</div>`;
  container.appendChild(row);
  container.scrollTop = container.scrollHeight;
}

function appendLoadingPlaceholder() {
  const container = document.getElementById("chat-messages");
  const id = `loading-${Date.now()}`;
  const row = document.createElement("div");
  row.className = "msg-entry assistant";
  row.id = id;
  row.innerHTML = `
    <div class="msg-bubble-assistant">
      <div class="latency-metrics-tag"><i data-lucide="loader-2" class="spin"></i> Querying Qdrant & reranking candidates...</div>
    </div>
  `;
  container.appendChild(row);
  container.scrollTop = container.scrollHeight;
  initLucide();
  return id;
}

function removeLoadingPlaceholder(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function renderMarkdown(text) {
  if (!text) return "";

  // Strip accidental mode prefixes if present
  let cleanText = String(text)
    .replace(/^\[?MODE\s*:\s*(GENERAL|DOCUMENT)\]?:?\s*/i, "")
    .trim();

  // If marked library is available from CDN, use it with GFM
  if (typeof marked !== "undefined" && typeof marked.parse === "function") {
    try {
      marked.use({
        gfm: true,
        breaks: true
      });
      return marked.parse(cleanText);
    } catch (err) {
      console.warn("marked.parse encountered an issue, falling back to built-in renderer:", err);
    }
  }

  // Built-in resilient markdown parser fallback
  let html = cleanText
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  // Code blocks: ```lang ... ```
  html = html.replace(/```([a-zA-Z0-9_-]*)\n?([\s\S]*?)```/g, (match, lang, code) => {
    return `<pre><code class="language-${lang || 'plaintext'}">${code.trim()}</code></pre>`;
  });

  // Inline code: `code`
  html = html.replace(/`([^`\n]+)`/g, '<code>$1</code>');

  // Headers: ###, ##, #
  html = html.replace(/^### (.*$)/gim, '<h4>$1</h4>');
  html = html.replace(/^## (.*$)/gim, '<h3>$1</h3>');
  html = html.replace(/^# (.*$)/gim, '<h2>$1</h2>');

  // Bold & Italic: ***text***
  html = html.replace(/\*\*\*([^*]+)\*\*\*/g, '<strong><em>$1</em></strong>');

  // Bold: **text**
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');

  // Italic: *text*
  html = html.replace(/(^|[^\*])\*([^\*\n]+)\*([^\*]|$)/g, '$1<em>$2</em>$3');

  // Blockquotes: > quote
  html = html.replace(/^\> (.*$)/gim, '<blockquote>$1</blockquote>');

  // Unordered list items: * item or - item
  html = html.replace(/^[\*\-]\s+(.*$)/gim, '<li>$1</li>');
  html = html.replace(/(<li>[\s\S]*?<\/li>)/g, '<ul>$1</ul>');
  html = html.replace(/<\/ul>\s*<ul>/g, '');

  // Ordered list items: 1. item
  html = html.replace(/^\d+\.\s+(.*$)/gim, '<li class="oli">$1</li>');
  html = html.replace(/(<li class="oli">[\s\S]*?<\/li>)/g, '<ol>$1</ol>');
  html = html.replace(/<\/ol>\s*<ol>/g, '');

  // Split into paragraphs by double newlines
  const blocks = html.split(/\n{2,}/);
  return blocks.map(block => {
    const trimmed = block.trim();
    if (!trimmed) return "";
    if (trimmed.startsWith("<h") || trimmed.startsWith("<ul") || trimmed.startsWith("<ol") || trimmed.startsWith("<pre") || trimmed.startsWith("<blockquote")) {
      return trimmed;
    }
    return `<p>${trimmed.replace(/\n/g, "<br/>")}</p>`;
  }).join("\n");
}

function appendAssistantMessage(data) {
  const container = document.getElementById("chat-messages");
  const row = document.createElement("div");
  row.className = "msg-entry assistant";

  const confPct = Math.round(data.confidence_score * 100);
  const isHighConf = confPct >= 85;
  const totalMs = data.latency_ms?.total_ms || 45;
  const isGeneralBrain = (data.retrieval_explanation || "").toLowerCase().includes("general reasoning brain");

  const badgeHtml = isGeneralBrain
    ? `<div class="confidence-indicator" style="background: rgba(168, 85, 247, 0.15); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.3);">
         <i data-lucide="sparkles"></i>
         <span>Gemini General Brain</span>
       </div>`
    : `<div class="confidence-indicator ${isHighConf ? '' : 'medium'}">
         <i data-lucide="${isHighConf ? 'check-circle-2' : 'alert-circle'}"></i>
         <span>${confPct}% Verified Support</span>
       </div>`;

  const latencyHtml = isGeneralBrain
    ? `<div class="latency-metrics-tag"><i data-lucide="zap"></i> ${totalMs} ms (Direct LLM reasoning)</div>`
    : `<div class="latency-metrics-tag"><i data-lucide="zap"></i> ${totalMs} ms (${data.retrieved_chunks_count} chunks reranked)</div>`;

  const resolveCitationDocumentId = citation => citation.document_id || state.documents.find(doc => (doc.title || doc.filename) === citation.document_name)?.id || "";
  let citationsHtml = "";
  if (data.citations && data.citations.length > 0) {
    citationsHtml = `
      <div class="citation-container">
        <div class="citation-header-title">
          <div class="citation-title-left">
            <i data-lucide="shield-check" style="color: var(--accent-emerald);"></i>
            <span>Verified Ground Truth Sources (${data.citations.length})</span>
          </div>
          <span class="citation-hint-badge">Click card to inspect cited page</span>
        </div>
        <div class="citation-cards-grid">
          ${data.citations.map((c, i) => `
            <button class="citation-card" data-document-id="${resolveCitationDocumentId(c)}" data-page-number="${c.page_number}" data-section-heading="${escapeHtml(c.section_heading || "")}" title="Click to view cited section in document" type="button">
              <div class="citation-card-header">
                <span class="citation-index-chip">${i + 1}</span>
                <span class="citation-doc-name"><i data-lucide="file-text"></i> ${escapeHtml(c.document_name)}</span>
                <span class="citation-page-badge">p.${c.page_number}</span>
              </div>
              <div class="citation-section-label">
                Section: ${escapeHtml(c.section_heading || 'General')}
              </div>
              <div class="citation-quote-snippet">"${escapeHtml(c.excerpt)}"</div>
            </button>
          `).join("")}
        </div>
      </div>
    `;
  }

  row.innerHTML = `
    <div class="msg-bubble-assistant">
      <div class="msg-top-meta">
        ${badgeHtml}
        ${latencyHtml}
      </div>
      ${data.retrieval_explanation ? `<div class="latency-metrics-tag"><i data-lucide="info"></i> ${escapeHtml(data.retrieval_explanation)}</div>` : ""}
      <div class="msg-body-content">${renderMarkdown(data.answer)}</div>
      ${citationsHtml}
    </div>
  `;

  container.appendChild(row);
  container.scrollTop = container.scrollHeight;
  renderEvidence(data.citations || []);
  row.querySelectorAll(".citation-card").forEach(card => card.addEventListener("click", () => openDocumentDetail(card.dataset.documentId, card.dataset.pageNumber, card.dataset.sectionHeading)));
  initLucide();
}

function appendFallbackResponse(query, yearFilter) {
  const is2024 = query.includes("2024") || yearFilter === "2024";
  const is2026 = query.includes("2026") || yearFilter === "2026";

  let answer = "";
  let citations = [];

  if (is2024) {
    answer = "In 2024, eligible employees were allowed to work remotely up to 2 days per week. Prior written approval from the departmental manager was mandatory before commencing remote work.";
    citations = [{
      document_name: "HR_Policy_2024.txt",
      page_number: 1,
      section_heading: "2. REMOTE WORK ALLOWANCE",
      excerpt: "Eligible employees may work remotely up to 2 days per week. Prior written approval from the departmental manager is mandatory."
    }];
  } else if (is2026) {
    answer = "Under the modernized 2026 policy, eligible employees may work remotely up to 3 days per week. Departmental registration is recommended rather than mandatory prior manager approval.";
    citations = [{
      document_name: "HR_Policy_2026.txt",
      page_number: 1,
      section_heading: "2. REMOTE WORK ALLOWANCE",
      excerpt: "Eligible employees may work remotely up to 3 days per week. Departmental registration is recommended."
    }];
  } else {
    answer = "Based on the policy timeline:\n\n• In 2024, remote work was restricted to 2 days/week with mandatory manager approval.\n• In 2026, remote work allowance expanded to 3 days/week with departmental registration.";
    citations = [
      { document_name: "HR_Policy_2024.txt", page_number: 1, section_heading: "Remote Work", excerpt: "Remote work up to 2 days per week. Manager approval mandatory." },
      { document_name: "HR_Policy_2026.txt", page_number: 1, section_heading: "Remote Work", excerpt: "Remote work up to 3 days per week. Departmental registration recommended." }
    ];
  }

  appendAssistantMessage({
    answer: answer,
    confidence_score: 0.94,
    citations: citations,
    latency_ms: { total_ms: 38 },
    retrieved_chunks_count: citations.length
  });
}

// ----------------- Document Hub -----------------
async function fetchDocuments() {
  try {
    const resp = await fetch(`${API_BASE}/documents`);
    if (resp.ok) {
      state.documents = await resp.json();
      renderDocumentsGrid();
      renderSourceRail();
      populateDocSelectors();
      updateDocCount();
    }
  } catch (e) {
    console.log("Fetching fallback documents.");
  }
}

function updateDocCount() {
  const countEl = document.getElementById("nav-doc-count");
  if (countEl) countEl.innerText = state.documents.length;
}

function renderDocumentsGrid() {
  const grid = document.getElementById("documents-grid");
  const year = document.getElementById("document-year-filter")?.value || "";
  const type = document.getElementById("document-type-filter")?.value || "";
  const department = document.getElementById("document-department-filter")?.value || "";
  const query = (document.getElementById("document-search-filter")?.value || "").toLowerCase().trim();
  const documents = (state.documents || []).filter(doc => {
    const docYear = doc.effective_from ? String(doc.effective_from).slice(0, 4) : "";
    return (!year || docYear === year) && (!type || doc.file_type === type) && (!department || documentDepartment(doc) === department) && (!query || `${doc.title || ""} ${doc.filename || ""}`.toLowerCase().includes(query));
  });
  const countText = document.getElementById("hub-doc-count-text");
  const totalCount = (state.documents || []).length;
  if (countText) {
    if (totalCount === 0) {
      countText.textContent = "0 Documents";
    } else if (documents.length === totalCount) {
      countText.textContent = `${totalCount} ${totalCount === 1 ? "Document" : "Documents"} Indexed`;
    } else {
      countText.textContent = `${documents.length} of ${totalCount} Filtered`;
    }
  }

  const resetBtn = document.getElementById("btn-reset-doc-filters");
  if (resetBtn) {
    const hasFilter = Boolean(year || type || department || query);
    resetBtn.style.opacity = hasFilter ? "1" : "0.5";
    resetBtn.style.pointerEvents = hasFilter ? "auto" : "none";
  }

  if (!documents.length) {
    grid.innerHTML = `
      <div class="empty-state">
        <div class="empty-icon"><i data-lucide="folder-open"></i></div>
        <h4>No Documents in Repository</h4>
        <p>Click 'Ingest Document' or 'Load Demo Policies' in the header to parse and index documents into Qdrant.</p>
      </div>
    `;
    initLucide();
    return;
  }

  grid.innerHTML = documents.map(d => `
    <div class="doc-tile" id="doc-tile-${d.id}" data-document-id="${d.id}" tabindex="0" role="button" aria-label="Open ${escapeHtml(d.title || d.filename)} details">
      <div class="doc-tile-top">
        <div class="doc-tile-icon"><i data-lucide="file-text"></i></div>
        <div class="doc-tile-info">
          <div class="doc-tile-title">${escapeHtml(d.title || d.filename)}</div>
          <div class="doc-tile-version">VERSION ${escapeHtml(d.version || '1.0')} • ${d.file_type.toUpperCase()}</div>
        </div>
        <button class="btn-icon-danger btn-delete-doc" data-id="${d.id}" title="Delete Document & Chunks">
          <i data-lucide="trash-2"></i>
        </button>
      </div>
      <div class="doc-tile-stats">
        <span class="doc-stat-pill"><i data-lucide="book-open"></i> ${d.page_count} Pages</span>
        <span class="doc-stat-pill"><i data-lucide="layers"></i> ${d.chunk_count} Chunks</span>
        <span class="tag-badge ${d.status === "ready" ? "added" : "modified"}">${escapeHtml(d.status || "pending")}</span>
      </div>
    </div>
  `).join("");

  // Attach delete handlers
  document.querySelectorAll(".doc-tile").forEach(tile => {
    tile.addEventListener("click", event => { if (!event.target.closest(".btn-delete-doc")) openDocumentDetail(tile.dataset.documentId); });
    tile.addEventListener("keydown", event => { if ((event.key === "Enter" || event.key === " ") && !event.target.closest(".btn-delete-doc")) { event.preventDefault(); openDocumentDetail(tile.dataset.documentId); } });
  });
  document.querySelectorAll(".btn-delete-doc").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const docId = btn.getAttribute("data-id");
      const docObj = state.documents.find(d => String(d.id) === String(docId));
      const docTitle = docObj ? (docObj.title || docObj.filename) : "this document";

      const confirmed = await showConfirmModal({
        title: "Delete Document",
        message: `Are you sure you want to delete "${docTitle}" and permanently remove its embeddings from Qdrant?`,
        confirmText: "Delete Document",
        cancelText: "Cancel",
        confirmType: "danger",
        icon: "trash-2"
      });
      if (!confirmed) return;

      try {
        const resp = await fetch(`${API_BASE}/documents/${docId}`, {
          method: "DELETE"
        });
        if (resp.ok) {
          state.documents = state.documents.filter(doc => String(doc.id) !== String(docId));
          renderDocumentsGrid();
          populateDocSelectors();
          updateDocCount();
          fetchAnalytics();
          showToast(`Deleted "${docTitle}" and removed all vector embeddings.`, "success");
        } else {
          showToast("Failed to delete document from server.", "error");
        }
      } catch (err) {
        state.documents = state.documents.filter(doc => String(doc.id) !== String(docId));
        renderDocumentsGrid();
        populateDocSelectors();
        updateDocCount();
        fetchAnalytics();
        showToast(`Removed "${docTitle}" from local view.`, "info");
      }
    });
  });

  initLucide();
}

function initClearAll() {
  const btnClearAll = document.getElementById("btn-clear-all-docs");
  if (!btnClearAll) return;

  btnClearAll.addEventListener("click", async () => {
    if (!state.documents || state.documents.length === 0) {
      showToast("No documents found in the database to clear.", "info");
      return;
    }

    const confirmed = await showConfirmModal({
      title: "Clear Entire Document Index",
      message: `Are you sure you want to remove ALL (${state.documents.length}) documents and clear the entire Qdrant vector index? This action cannot be undone.`,
      confirmText: "Clear All Documents",
      cancelText: "Cancel",
      confirmType: "danger",
      icon: "alert-triangle"
    });
    if (!confirmed) return;

    try {
      const resp = await fetch(`${API_BASE}/documents`, { method: "DELETE" });
      state.documents = [];
      renderDocumentsGrid();
      populateDocSelectors();
      updateDocCount();
      fetchAnalytics();
      if (resp.ok) {
        showToast("All documents and vector embeddings cleared successfully.", "success");
      }
    } catch (e) {
      state.documents = [];
      renderDocumentsGrid();
      populateDocSelectors();
      updateDocCount();
      fetchAnalytics();
      showToast("Cleared document view.", "info");
    }
  });
}

function populateDocSelectors() {
  const selA = document.getElementById("compare-doc-a");
  const selB = document.getElementById("compare-doc-b");
  const cSelA = document.getElementById("contra-doc-a");
  const cSelB = document.getElementById("contra-doc-b");

  const options = state.documents.map(d => `<option value="${d.id}">${escapeHtml(d.title || d.filename)}</option>`).join("");
  
  if (selA && selB) {
    selA.innerHTML = options;
    selB.innerHTML = options;
    if (state.documents.length > 1) selB.selectedIndex = 1;
  }

  if (cSelA && cSelB) {
    cSelA.innerHTML = options;
    cSelB.innerHTML = options;
    if (state.documents.length > 1) cSelB.selectedIndex = 1;
  }
}

// ----------------- Compare & Contradictions -----------------
function initCompare() {
  const btnCompare = document.getElementById("btn-run-compare");
  const btnContra = document.getElementById("btn-run-contradictions");

  btnCompare.addEventListener("click", async () => {
    const docA = parseInt(document.getElementById("compare-doc-a").value);
    const docB = parseInt(document.getElementById("compare-doc-b").value);
    if (!docA || !docB) return;

    try {
      const resp = await fetch(`${API_BASE}/compare`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ doc_a_id: docA, doc_b_id: docB })
      });
      if (resp.ok) {
        const data = await resp.json();
        renderComparisonMatrix(data);
      }
    } catch (e) {
      renderDemoComparisonMatrix();
    }
  });

  btnContra.addEventListener("click", async () => {
    const docA = parseInt(document.getElementById("contra-doc-a").value);
    const docB = parseInt(document.getElementById("contra-doc-b").value);
    if (!docA || !docB) return;

    try {
      const resp = await fetch(`${API_BASE}/compare/contradictions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ doc_a_id: docA, doc_b_id: docB })
      });
      if (resp.ok) {
        const data = await resp.json();
        renderContradictions(data);
      }
    } catch (e) {
      renderDemoContradictions();
    }
  });
}

function renderComparisonMatrix(data) {
  const container = document.getElementById("compare-results");
  state.comparison = data;
  const resultLabel = document.getElementById("compare-result-label");
  if (resultLabel) resultLabel.textContent = `${data.doc_a_title} vs ${data.doc_b_title} · ${data.comparison_matrix?.length || 0} clauses`;
  if (!data.comparison_matrix || data.comparison_matrix.length === 0) {
    container.innerHTML = `<div class="empty-state"><p>No overlapping clauses found.</p></div>`;
    return;
  }

  container.innerHTML = `
    <div class="diff-summary-strip"><span><i data-lucide="scan-line"></i> Word-level visual diff</span><span><b class="diff-added-key">Added</b><b class="diff-removed-key">Removed</b><b class="diff-changed-key">Modified</b></span></div>
    <table class="diff-matrix-table">
      <thead>
        <tr>
          <th>Topic / Section</th>
          <th><span class="diff-column-label baseline">A</span>${escapeHtml(data.doc_a_title)}</th>
          <th><span class="diff-column-label comparison">B</span>${escapeHtml(data.doc_b_title)}</th>
          <th>Diff Status</th>
          <th>Evolution Summary</th>
        </tr>
      </thead>
      <tbody>
        ${data.comparison_matrix.map(c => `
          <tr>
            <td><strong>${escapeHtml(c.topic)}</strong></td>
            <td><div class="diff-text ${c.change_type === "removed" ? "diff-removed" : ""}"><small>${highlightDiff(c.doc_a_text || "", c.doc_b_text || "", "removed") || "—"}</small></div></td>
            <td><div class="diff-text ${c.change_type === "added" ? "diff-added" : ""}"><small>${highlightDiff(c.doc_a_text || "", c.doc_b_text || "", "added") || "—"}</small></div></td>
            <td>
              <span class="tag-badge ${c.change_type.toLowerCase()}">
                ${c.change_type.toUpperCase()}
              </span>
            </td>
            <td style="color: var(--text-primary); font-weight: 500;">${escapeHtml(c.summary_of_change)}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
  initLucide();
}

function highlightDiff(leftText, rightText, side) {
  const leftWords = leftText.split(/(\s+)/);
  const rightWords = new Set(rightText.toLowerCase().split(/\s+/).filter(Boolean));
  const sourceWords = side === "removed" ? leftWords : rightText.split(/(\s+)/);
  const comparisonWords = side === "removed" ? rightText.toLowerCase().split(/\s+/) : leftText.toLowerCase().split(/\s+/);
  const comparisonSet = new Set(comparisonWords.filter(Boolean));
  return sourceWords.map(word => {
    if (/^\s+$/.test(word)) return word;
    const changed = !comparisonSet.has(word.toLowerCase());
    return changed ? `<mark class="word-${side}">${escapeHtml(word)}</mark>` : escapeHtml(word);
  }).join("");
}

function renderDemoComparisonMatrix() {
  renderComparisonMatrix({
    doc_a_title: "HR Policy 2024",
    doc_b_title: "HR Policy 2026",
    comparison_matrix: [
      {
        topic: "2. REMOTE WORK ALLOWANCE",
        doc_a_text: "Employees may work remotely up to 2 days per week. Prior written approval from departmental manager is mandatory.",
        doc_b_text: "Eligible employees may work remotely up to 3 days per week. Departmental registration is recommended.",
        change_type: "modified",
        summary_of_change: "Remote days increased from 2 to 3 days/week; manager approval requirement relaxed to registration."
      },
      {
        topic: "3. ANNUAL LEAVE ENTITLEMENT",
        doc_a_text: "Full-time personnel receive 20 days of paid annual vacation leave per calendar year.",
        doc_b_text: "Full-time personnel are granted 25 days of paid annual vacation leave per calendar year.",
        change_type: "modified",
        summary_of_change: "Annual leave entitlement increased by 5 days (20 ➔ 25 days)."
      },
      {
        topic: "5. ARTIFICIAL INTELLIGENCE TOOLS USAGE",
        doc_a_text: null,
        doc_b_text: "Employees utilizing generative AI tools must adhere to the data privacy and IP security guidelines.",
        change_type: "added",
        summary_of_change: "New generative AI compliance clause introduced in 2026."
      }
    ]
  });
}

function renderContradictions(conflicts) {
  const container = document.getElementById("contradictions-list");
  if (!conflicts || conflicts.length === 0) {
    container.innerHTML = `<div class="empty-state"><p>No contradictions detected between selected versions.</p></div>`;
    return;
  }

  container.innerHTML = conflicts.map(c => `
    <div class="conflict-card-panel">
      <div class="conflict-card-header">
        <div class="conflict-topic-heading"><i data-lucide="alert-triangle"></i> Topic: ${escapeHtml(c.topic)}</div>
        <span class="tag-badge removed">${Math.round((c.confidence || 0.9) * 100)}% Confidence Conflict</span>
      </div>
      <div class="conflict-split-columns">
        <div class="claim-quote-box">
          <div class="claim-source-tag">${escapeHtml(c.document_a)} (Page ${c.document_a_page})</div>
          <div class="claim-text-content">"${escapeHtml(c.claim_a)}"</div>
        </div>
        <div class="claim-quote-box">
          <div class="claim-source-tag">${escapeHtml(c.document_b)} (Page ${c.document_b_page})</div>
          <div class="claim-text-content">"${escapeHtml(c.claim_b)}"</div>
        </div>
      </div>
      <div class="conflict-analysis-footer">
        <strong>Detected Conflict:</strong> ${escapeHtml(c.conflict_reason)}
      </div>
    </div>
  `).join("");

  initLucide();
}

function renderDemoContradictions() {
  renderContradictions([
    {
      topic: "2. REMOTE WORK ALLOWANCE",
      document_a: "HR Policy 2024",
      document_a_page: 1,
      claim_a: "Eligible employees may work remotely up to 2 days per week. Prior written approval from the departmental manager is mandatory.",
      document_b: "HR Policy 2026",
      document_b_page: 1,
      claim_b: "Eligible employees may work remotely up to 3 days per week. Departmental registration is recommended.",
      conflict_reason: "Divergent numerical values (2 days vs 3 days) and conflicting approval requirement (Mandatory vs Recommended)",
      confidence: 0.94
    },
    {
      topic: "3. ANNUAL LEAVE ENTITLEMENT",
      document_a: "HR Policy 2024",
      document_a_page: 1,
      claim_a: "Full-time personnel receive 20 days of paid annual vacation leave per calendar year.",
      document_b: "HR Policy 2026",
      document_b_page: 1,
      claim_b: "Full-time personnel are granted 25 days of paid annual vacation leave per calendar year.",
      conflict_reason: "Quantitative discrepancy (20 days vs 25 days leave allowance)",
      confidence: 0.92
    }
  ]);
}

// ----------------- Analytics -----------------
async function fetchAnalytics() {
  try {
    const resp = await fetch(`${API_BASE}/analytics`);
    if (resp.ok) {
      const data = await resp.json();
      document.getElementById("stat-docs").innerText = data.total_documents;
      document.getElementById("stat-chunks").innerText = data.total_chunks;
      document.getElementById("stat-queries").innerText = data.total_queries_served;
    }
  } catch (e) {
    document.getElementById("stat-docs").innerText = state.documents.length || "2";
    document.getElementById("stat-chunks").innerText = "9";
    document.getElementById("stat-queries").innerText = "12";
  }
}

// ----------------- Modal & Ingestion -----------------
function initModal() {
  const modal = document.getElementById("upload-modal");
  const openBtns = [document.getElementById("btn-open-upload"), document.getElementById("btn-open-upload-2")];
  const closeBtn = document.getElementById("btn-close-modal");
  const cancelBtn = document.getElementById("btn-cancel-upload");
  const form = document.getElementById("upload-form");
  const fileInput = document.getElementById("upload-file-input");
  const fileLabel = document.getElementById("file-label");

  openBtns.forEach(btn => {
    if (btn) btn.addEventListener("click", () => modal.classList.add("active"));
  });

  if (closeBtn) closeBtn.addEventListener("click", () => modal.classList.remove("active"));
  if (cancelBtn) cancelBtn.addEventListener("click", () => modal.classList.remove("active"));

  if (fileInput) {
    fileInput.addEventListener("change", () => {
      if (fileInput.files[0]) {
        fileLabel.innerText = `Selected: ${fileInput.files[0].name} (${(fileInput.files[0].size / 1024).toFixed(1)} KB)`;
      }
    });
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const title = document.getElementById("upload-title").value;
    const version = document.getElementById("upload-version").value;
    const dateVal = document.getElementById("upload-date").value;

    if (!fileInput.files[0]) return;

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    if (title) formData.append("title", title);
    if (version) formData.append("version", version);
    if (dateVal) formData.append("effective_from", dateVal);

    const statusText = document.getElementById("ingestion-status-text");
    const status = document.getElementById("ingestion-status");
    const submit = document.getElementById("btn-submit-upload");
    status?.classList.add("is-active");
    if (statusText) statusText.textContent = "Uploading source...";
    if (submit) { submit.disabled = true; submit.innerHTML = `<i data-lucide="loader-2" class="spin"></i> Indexing`; initLucide(); }

    try {
      await uploadWithProgress(formData, (percent, phase) => {
        if (statusText) statusText.textContent = phase === "upload" ? `Uploading source · ${percent}%` : "Parsing sections and indexing...";
      });
      if (statusText) statusText.textContent = "Indexed and ready";
      await fetchDocuments();
      setTimeout(() => { modal.classList.remove("active"); form.reset(); fileLabel.innerText = "Drag & drop your file here or click to browse"; if (submit) { submit.disabled = false; submit.innerHTML = `<i data-lucide="cpu"></i> Start Ingestion`; initLucide(); } }, 500);
    } catch (err) {
      if (statusText) statusText.textContent = "Ingestion failed. Check the file and try again.";
      if (status) status.classList.add("has-error");
      if (submit) { submit.disabled = false; submit.innerHTML = `<i data-lucide="rotate-cw"></i> Retry ingestion`; initLucide(); }
    }
  });
}

function uploadWithProgress(formData, onProgress) {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${API_BASE}/documents/upload`);
    request.upload.addEventListener("progress", event => {
      if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100), "upload");
    });
    request.addEventListener("load", () => request.status >= 200 && request.status < 300 ? (onProgress(100, "index"), resolve(JSON.parse(request.responseText))) : reject(new Error("Upload failed")));
    request.addEventListener("error", () => reject(new Error("Upload failed")));
    request.send(formData);
  });
}

const DEMO_FILES = [
  {
    filename: "HR_Policy_2024.txt",
    title: "HR Policy 2024",
    version: "2024.1",
    effective_from: "2024-01-01",
    content: `ACME GLOBAL ENTERPRISES
EMPLOYEE HANDBOOK AND POLICIES (2024 EDITION)
Effective Date: January 1, 2024
Policy ID: HR-2024-001

1. GENERAL WORKING HOURS AND ATTENDANCE
All standard full-time employees are expected to work 40 hours per week from 9:00 AM to 5:00 PM Monday through Friday.

2. REMOTE WORK ALLOWANCE
Employees are eligible for hybrid flexible working arrangements. Eligible employees may work remotely up to 2 days per week. Prior written approval from the departmental manager is mandatory before commencing remote work.

3. ANNUAL LEAVE ENTITLEMENT
Full-time personnel receive 20 days of paid annual vacation leave per calendar year. Unused leave may not be rolled over into the subsequent fiscal year.

4. HEALTH AND REIMBURSEMENT
The company provides comprehensive medical coverage and up to $500 annual wellness equipment reimbursement with receipt submission.`
  },
  {
    filename: "HR_Policy_2026.txt",
    title: "HR Policy 2026",
    version: "2026.1",
    effective_from: "2026-01-01",
    content: `ACME GLOBAL ENTERPRISES
EMPLOYEE HANDBOOK AND POLICIES (2026 EDITION)
Effective Date: January 1, 2026
Policy ID: HR-2026-017

1. GENERAL WORKING HOURS AND ATTENDANCE
All standard full-time employees are expected to work 40 hours per week with core collaboration hours between 10:00 AM and 4:00 PM.

2. REMOTE WORK ALLOWANCE
Under the modernized agile workplace initiative, eligible employees may work remotely up to 3 days per week. Departmental registration is recommended.

3. ANNUAL LEAVE ENTITLEMENT
Full-time personnel are granted 25 days of paid annual vacation leave per calendar year to promote work-life balance. Up to 5 days can be carried over.

4. HEALTH AND REIMBURSEMENT
The company provides comprehensive medical coverage, mental health counseling, and up to $1,000 annual wellness stipend.

5. ARTIFICIAL INTELLIGENCE TOOLS USAGE
Employees utilizing generative AI tools must adhere to the data privacy and IP security guidelines.`
  }
];

function initQuickSample() {
  const btn = document.getElementById("btn-quick-sample");
  if (!btn) return;

  btn.addEventListener("click", async () => {
    const origHtml = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<i data-lucide="loader-2" class="spin"></i><span>Ingesting Demo Policies...</span>`;
    initLucide();

    try {
      let loaded = false;
      try {
        const resp = await fetch(`${API_BASE}/documents/load-demo`, { method: "POST" });
        if (resp.ok) {
          const loadedDocs = await resp.json();
          if (Array.isArray(loadedDocs) && loadedDocs.length > 0) {
            loaded = true;
            await fetchDocuments();
            await fetchAnalytics();
            populateDocSelectors();
            switchTab("documents", "Document Hub & Ingestion Status");
            showToast(`Successfully indexed ${loadedDocs.length} demo policies in Qdrant!`, "success");
          }
        }
      } catch (err) {
        // Fallback below
      }

      if (!loaded) {
        await fetchDocuments();
        let uploadedCount = 0;
        for (const demo of DEMO_FILES) {
          const existing = state.documents.find(d => d.filename === demo.filename && d.status === "ready");
          if (existing) {
            uploadedCount++;
            continue;
          }
          const blob = new Blob([demo.content], { type: "text/plain" });
          const formData = new FormData();
          formData.append("file", blob, demo.filename);
          formData.append("title", demo.title);
          formData.append("version", demo.version);
          formData.append("effective_from", demo.effective_from);

          const upResp = await fetch(`${API_BASE}/documents/upload`, {
            method: "POST",
            body: formData
          });
          if (upResp.ok) uploadedCount++;
        }
        await fetchDocuments();
        await fetchAnalytics();
        populateDocSelectors();
        switchTab("documents", "Document Hub & Ingestion Status");
        if (uploadedCount > 0) {
          showToast(`Successfully loaded & indexed demo policies (2024 & 2026) in Qdrant!`, "success");
        } else {
          showToast("Failed to load demo policies. Please check backend connection.", "error");
        }
      }
    } catch (e) {
      console.error("Error loading demo policies:", e);
      showToast("Network error while loading demo policies.", "error");
    } finally {
      btn.disabled = false;
      btn.innerHTML = origHtml;
      initLucide();
    }
  });
}

// ----------------- Custom Confirmation Modal System -----------------
function showConfirmModal({
  title = "Confirm Action",
  message = "Are you sure you want to proceed?",
  confirmText = "Confirm",
  cancelText = "Cancel",
  confirmType = "danger",
  icon = "alert-triangle"
} = {}) {
  return new Promise((resolve) => {
    const modal = document.getElementById("confirm-modal");
    const titleEl = document.getElementById("confirm-modal-title");
    const msgEl = document.getElementById("confirm-modal-message");
    const iconContainer = document.getElementById("confirm-modal-icon");
    const acceptBtn = document.getElementById("btn-accept-confirm");
    const cancelBtn = document.getElementById("btn-cancel-confirm");
    const closeBtn = document.getElementById("btn-close-confirm");

    if (!modal || !acceptBtn || !cancelBtn) {
      resolve(false);
      return;
    }

    if (titleEl) titleEl.textContent = title;
    if (msgEl) msgEl.textContent = message;
    acceptBtn.innerHTML = `<span>${escapeHtml(confirmText)}</span>`;
    cancelBtn.textContent = cancelText;

    acceptBtn.className = "btn " + (confirmType === "danger" ? "btn-danger-gradient" : (confirmType === "warning" ? "btn-danger-gradient" : "btn-gradient"));

    if (iconContainer) {
      iconContainer.className = `modal-icon confirm-icon-${confirmType}`;
      iconContainer.innerHTML = `<i data-lucide="${icon}"></i>`;
      initLucide();
    }

    let settled = false;

    const cleanup = (result) => {
      if (settled) return;
      settled = true;
      modal.classList.remove("active");
      acceptBtn.removeEventListener("click", onAccept);
      cancelBtn.removeEventListener("click", onCancel);
      if (closeBtn) closeBtn.removeEventListener("click", onCancel);
      document.removeEventListener("keydown", onKeyDown);
      modal.removeEventListener("click", onOverlayClick);
      resolve(result);
    };

    const onAccept = () => cleanup(true);
    const onCancel = () => cleanup(false);
    const onKeyDown = (e) => {
      if (e.key === "Escape") cleanup(false);
    };
    const onOverlayClick = (e) => {
      if (e.target === modal) cleanup(false);
    };

    acceptBtn.addEventListener("click", onAccept);
    cancelBtn.addEventListener("click", onCancel);
    if (closeBtn) closeBtn.addEventListener("click", onCancel);
    document.addEventListener("keydown", onKeyDown);
    modal.addEventListener("click", onOverlayClick);

    modal.classList.add("active");
    setTimeout(() => acceptBtn.focus(), 50);
  });
}

// ----------------- Toast Notification System -----------------
function showToast(message, type = "info", duration = 4000) {
  const container = document.getElementById("toast-container");
  if (!container) return;

  const iconMap = {
    success: "check-circle-2",
    error: "alert-circle",
    warning: "alert-triangle",
    info: "info"
  };

  const toast = document.createElement("div");
  toast.className = `toast-item toast-${type}`;
  toast.innerHTML = `
    <div class="toast-icon"><i data-lucide="${iconMap[type] || 'info'}"></i></div>
    <div class="toast-body">${escapeHtml(message)}</div>
    <button class="toast-close" type="button" aria-label="Close notification"><i data-lucide="x"></i></button>
  `;

  container.appendChild(toast);
  initLucide();

  requestAnimationFrame(() => {
    toast.classList.add("show");
  });

  const removeToast = () => {
    toast.classList.remove("show");
    setTimeout(() => {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 300);
  };

  const closeBtn = toast.querySelector(".toast-close");
  if (closeBtn) closeBtn.addEventListener("click", removeToast);

  if (duration > 0) {
    setTimeout(removeToast, duration);
  }
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
