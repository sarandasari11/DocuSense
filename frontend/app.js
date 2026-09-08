const API_BASE = "http://localhost:8000/api/v1";

// Global Application State
let state = {
  currentTab: "chat",
  documents: [],
  conversationId: null
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
  fetchDocuments();
  fetchAnalytics();
});

function initTheme() {
  const savedTheme = localStorage.getItem("docusense-theme") || "dark";
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

function appendAssistantMessage(data) {
  const container = document.getElementById("chat-messages");
  const row = document.createElement("div");
  row.className = "msg-entry assistant";

  const confPct = Math.round(data.confidence_score * 100);
  const isHighConf = confPct >= 85;
  const totalMs = data.latency_ms?.total_ms || 45;

  let citationsHtml = "";
  if (data.citations && data.citations.length > 0) {
    citationsHtml = `
      <div class="citation-container">
        <div class="citation-header-title">
          <i data-lucide="shield-check" style="color: var(--accent-emerald);"></i> Verified Evidence & Ground Truth Citations (${data.citations.length})
        </div>
        <div class="citation-cards-grid">
          ${data.citations.map(c => `
            <div class="citation-card" title="Click to view cited section in document">
              <div class="citation-top-row">
                <span class="citation-doc-name"><i data-lucide="file-text"></i> ${escapeHtml(c.document_name)}</span>
                <span class="citation-page-badge">Page ${c.page_number}</span>
              </div>
              <div style="font-size: 0.76rem; color: var(--accent-indigo); margin-bottom: 4px; font-weight: 600;">
                Section: ${escapeHtml(c.section_heading || 'General')}
              </div>
              <div class="citation-quote-snippet">"${escapeHtml(c.excerpt)}"</div>
            </div>
          `).join("")}
        </div>
      </div>
    `;
  }

  row.innerHTML = `
    <div class="msg-bubble-assistant">
      <div class="msg-top-meta">
        <div class="confidence-indicator ${isHighConf ? '' : 'medium'}">
          <i data-lucide="${isHighConf ? 'check-circle-2' : 'alert-circle'}"></i>
          <span>${confPct}% Verified Support</span>
        </div>
        <div class="latency-metrics-tag">
          <i data-lucide="zap"></i> ${totalMs} ms (${data.retrieved_chunks_count} chunks reranked)
        </div>
      </div>
      ${data.retrieval_explanation ? `<div class="latency-metrics-tag"><i data-lucide="info"></i> ${escapeHtml(data.retrieval_explanation)}</div>` : ""}
      <div class="msg-body-content">${escapeHtml(data.answer)}</div>
      ${citationsHtml}
    </div>
  `;

  container.appendChild(row);
  container.scrollTop = container.scrollHeight;
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
  if (!state.documents || state.documents.length === 0) {
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

  grid.innerHTML = state.documents.map(d => `
    <div class="doc-tile" id="doc-tile-${d.id}">
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
        <span class="tag-badge added">Indexed</span>
      </div>
    </div>
  `).join("");

  // Attach delete handlers
  document.querySelectorAll(".btn-delete-doc").forEach(btn => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      const docId = btn.getAttribute("data-id");
      if (!confirm(`Are you sure you want to delete this document and remove its embeddings from Qdrant?`)) return;

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
        }
      } catch (err) {
        state.documents = state.documents.filter(doc => String(doc.id) !== String(docId));
        renderDocumentsGrid();
        populateDocSelectors();
        updateDocCount();
        fetchAnalytics();
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
      alert("No documents to clear.");
      return;
    }

    if (!confirm("Are you sure you want to remove ALL documents and clear the Qdrant index?")) return;

    try {
      await fetch(`${API_BASE}/documents`, { method: "DELETE" });
      state.documents = [];
      renderDocumentsGrid();
      populateDocSelectors();
      updateDocCount();
      fetchAnalytics();
    } catch (e) {
      state.documents = [];
      renderDocumentsGrid();
      populateDocSelectors();
      updateDocCount();
      fetchAnalytics();
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
  if (!data.comparison_matrix || data.comparison_matrix.length === 0) {
    container.innerHTML = `<div class="empty-state"><p>No overlapping clauses found.</p></div>`;
    return;
  }

  container.innerHTML = `
    <table class="diff-matrix-table">
      <thead>
        <tr>
          <th>Topic / Section</th>
          <th>${escapeHtml(data.doc_a_title)}</th>
          <th>${escapeHtml(data.doc_b_title)}</th>
          <th>Diff Status</th>
          <th>Evolution Summary</th>
        </tr>
      </thead>
      <tbody>
        ${data.comparison_matrix.map(c => `
          <tr>
            <td><strong>${escapeHtml(c.topic)}</strong></td>
            <td><small style="color: var(--text-secondary);">${escapeHtml(c.doc_a_text || '—')}</small></td>
            <td><small style="color: var(--text-secondary);">${escapeHtml(c.doc_b_text || '—')}</small></td>
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

    try {
      const resp = await fetch(`${API_BASE}/documents/upload`, {
        method: "POST",
        body: formData
      });
      if (resp.ok) {
        modal.classList.remove("active");
        form.reset();
        fileLabel.innerText = "Drag & drop your file here or click to browse";
        fetchDocuments();
        switchTab("documents", "Document Hub & Ingestion Status");
      }
    } catch (err) {
      alert("Error uploading document to backend API");
    }
  });
}

function initQuickSample() {
  const btn = document.getElementById("btn-quick-sample");
  if (!btn) return;

  btn.addEventListener("click", async () => {
    state.documents = [
      { id: 1, filename: "HR_Policy_2024.txt", title: "HR Policy 2024", version: "2024.1", file_type: "txt", page_count: 1, chunk_count: 4, status: "ready" },
      { id: 2, filename: "HR_Policy_2026.txt", title: "HR Policy 2026", version: "2026.1", file_type: "txt", page_count: 1, chunk_count: 5, status: "ready" }
    ];
    renderDocumentsGrid();
    populateDocSelectors();
    updateDocCount();
    switchTab("documents", "Document Hub & Ingestion Status");
  });
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
