document.addEventListener("DOMContentLoaded", () => {
  const searchInput = document.getElementById("kb-search-input");
  const searchBtn = document.getElementById("kb-search-btn");
  const randomBtn = document.getElementById("kb-random-btn");
  const categoryFilter = document.getElementById("kb-category-filter");
  const resultsEl = document.getElementById("kb-results");
  const statEntries = document.getElementById("stat-entries");
  const statCategories = document.getElementById("stat-categories");
  const modal = document.getElementById("kb-modal");
  const modalTitle = document.getElementById("kb-modal-title");
  const modalBody = document.getElementById("kb-modal-body");
  const modalClose = document.getElementById("kb-modal-close");

  let allCategories = [];

  async function api(url, data) {
    const opts = { headers: { "Content-Type": "application/json" } };
    if (data) opts.method = "POST", opts.body = JSON.stringify(data);
    const r = await fetch(url, opts);
    return r.json();
  }

  async function loadStats() {
    const stats = await api("/knowledge/stats");
    statEntries.textContent = stats.total_entries ?? 0;
    statCategories.textContent = (stats.entries_by_category ? Object.keys(stats.entries_by_category).length : 0);
  }

  async function loadCategories() {
    const cats = await api("/knowledge/categories");
    allCategories = cats.categories ?? [];
    categoryFilter.innerHTML = '<option value="">All</option>' +
      allCategories.map(c => `<option value="${c}">${c}</option>`).join("");
  }

  function renderResults(results) {
    if (!results || results.length === 0) {
      resultsEl.innerHTML = '<div class="kb-empty">No results found.</div>';
      return;
    }
    resultsEl.innerHTML = results.map((r, i) => {
      const summary = (r.summary || r.content || "No content").slice(0, 300);
      const cat = r.category || "uncategorized";
      const score = r.score !== undefined ? `Score: ${(r.score * 100).toFixed(0)}%` : "";
      return `<div class="kb-card" data-id="${r.id || i}" data-index="${i}">
        <div class="kb-card-title">${esc(r.topic || "Untitled")}</div>
        <div class="kb-card-summary">${esc(summary)}</div>
        <div class="kb-card-meta">
          <span class="kb-card-category">${esc(cat)}</span>
          ${score ? `<span>${score}</span>` : ""}
        </div>
      </div>`;
    }).join("");
    resultsEl.querySelectorAll(".kb-card").forEach(el => {
      el.addEventListener("click", () => {
        const idx = parseInt(el.dataset.index);
        showEntry(results[idx]);
      });
    });
  }

  function showEntry(entry) {
    modalTitle.textContent = entry.topic || "Knowledge Entry";
    const lines = [];
    if (entry.category) lines.push(`Category: ${entry.category}`);
    if (entry.tags && entry.tags.length) lines.push(`Tags: ${entry.tags.join(", ")}`);
    if (entry.confidence) lines.push(`Confidence: ${(entry.confidence * 100).toFixed(0)}%`);
    if (entry.created_at) lines.push(`Created: ${entry.created_at}`);
    lines.push("");
    lines.push(entry.content || entry.summary || "(no content)");
    modalBody.textContent = lines.join("\n");
    modal.classList.add("active");
  }

  function esc(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  async function doSearch() {
    const q = searchInput.value.trim();
    const cat = categoryFilter.value || null;
    const results = await api("/knowledge/search", { query: q || "*", category: cat, limit: 50 });
    renderResults(results.results);
  }

  async function doRandom() {
    const data = await api("/knowledge/random", null);
    renderResults(data.results);
  }

  searchBtn.addEventListener("click", doSearch);
  randomBtn.addEventListener("click", doRandom);
  searchInput.addEventListener("keydown", e => { if (e.key === "Enter") doSearch(); });
  categoryFilter.addEventListener("change", doSearch);

  modalClose.addEventListener("click", () => modal.classList.remove("active"));
  modal.addEventListener("click", e => { if (e.target === modal) modal.classList.remove("active"); });
  document.addEventListener("keydown", e => { if (e.key === "Escape") modal.classList.remove("active"); });

  loadStats();
  loadCategories();
});
