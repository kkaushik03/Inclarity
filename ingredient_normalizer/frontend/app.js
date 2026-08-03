/*
  Frontend behavior. Single responsibility: talk to the API and paint the
  results. All matching/decision logic lives on the server — this file only
  sends the pasted text and renders what comes back, including the
  graduated confidence scale each result is read against.
*/
"use strict";

const SAMPLE = [
  "Aqua (Water)",
  "Glycerine",
  "Butyrospermum Parkii (Shea) Butter*",
  "Vitamin C",
  "glycrol",
  "Sodium Hyaluronate",
  "Green Tea Extract",
  "Fragrance",
  "Tocopheryl Acetate",
  "Unicorn Extract",
].join(", ");

const DECISION_ICON = {
  accepted: "bi-check-circle-fill",
  review: "bi-exclamation-triangle-fill",
  unmatched: "bi-question-circle-fill",
};

const els = {
  input: document.getElementById("ingredient-input"),
  normalizeBtn: document.getElementById("normalize-btn"),
  sampleBtn: document.getElementById("sample-btn"),
  loading: document.getElementById("loading"),
  summary: document.getElementById("summary"),
  results: document.getElementById("results"),
  status: document.getElementById("engine-status"),
  statusText: document.getElementById("engine-status-text"),
  sTotal: document.getElementById("s-total"),
  sAccepted: document.getElementById("s-accepted"),
  sReview: document.getElementById("s-review"),
  sUnmatched: document.getElementById("s-unmatched"),
};

async function checkHealth() {
  try {
    const res = await fetch("/api/health");
    const data = await res.json();
    const mode = data.semantic_available
      ? "semantic + lexical matching"
      : "lexical matching only (semantic model not loaded)";
    els.status.classList.remove("error");
    els.statusText.textContent =
      `Engine ready \u2022 ${data.reference_size} reference ingredients \u2022 ${mode}`;
  } catch {
    els.status.classList.add("error");
    els.statusText.textContent = "Could not reach the matching engine.";
  }
}

async function normalize() {
  const text = els.input.value.trim();
  if (!text) return;

  els.loading.hidden = false;
  els.normalizeBtn.disabled = true;
  try {
    const res = await fetch("/api/normalize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Request failed");
    renderSummary(data.summary);
    renderResults(data.results);
  } catch (err) {
    els.results.innerHTML = `<p class="unmatched-name">Error: ${err.message}</p>`;
  } finally {
    els.loading.hidden = true;
    els.normalizeBtn.disabled = false;
  }
}

function renderSummary(summary) {
  els.summary.hidden = false;
  els.sTotal.textContent = summary.total;
  els.sAccepted.textContent = summary.accepted;
  els.sReview.textContent = summary.review;
  els.sUnmatched.textContent = summary.unmatched;
}

function renderResults(results) {
  els.results.innerHTML = "";
  results.forEach((r, i) => els.results.appendChild(renderRow(r, i)));

  // Let the rows mount at 0, then read the scale — gives the fill and
  // marker something to animate toward instead of snapping into place.
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      els.results.querySelectorAll(".scale-fill, .scale-marker").forEach((el) => {
        const target = el.dataset.target;
        if (el.classList.contains("scale-fill")) {
          el.style.width = `${target}%`;
        } else {
          el.style.left = `${target}%`;
        }
      });
    });
  });
}

function renderRow(r, index) {
  const row = document.createElement("div");
  row.className = `result-row ${r.decision}`;
  row.style.setProperty("--i", index);

  const matched =
    r.decision === "unmatched" || !r.matched_inci
      ? `<span class="unmatched-name">no confident match</span>`
      : `<span class="matched-name">${escapeHtml(r.matched_inci)}</span>`;

  const pct = Math.round((r.confidence || 0) * 100);
  const icon = DECISION_ICON[r.decision] || "bi-dash-circle";

  row.innerHTML = `
    <div class="row-top">
      <div class="row-names">
        <span class="raw-name">${escapeHtml(r.raw)}</span>
        <span class="arrow">&rarr;</span>
        ${matched}
      </div>
      <span class="badge badge-${r.decision}"><i class="bi ${icon}"></i>${r.decision}</span>
    </div>

    <div class="assay-scale" role="img" aria-label="Confidence ${pct} percent">
      <div class="scale-track">
        <span class="scale-tick" style="left:0%"></span>
        <span class="scale-tick" style="left:25%"></span>
        <span class="scale-tick" style="left:50%"></span>
        <span class="scale-tick" style="left:75%"></span>
        <span class="scale-tick" style="left:100%"></span>
        <span class="scale-fill" data-target="${pct}"></span>
        <span class="scale-marker" data-target="${pct}">${pct}%</span>
      </div>
      <div class="scale-labels"><span>0</span><span>100</span></div>
    </div>

    <div class="row-meta">
      <span class="meta-chip">confidence <b>${pct}%</b></span>
      <span class="meta-chip">stage <b>${escapeHtml(r.stage)}</b></span>
    </div>
    ${renderCandidates(r.candidates)}
  `;
  return row;
}

function renderCandidates(candidates) {
  if (!candidates || candidates.length <= 1) return "";
  const items = candidates
    .map((c, i) => {
      const pct = Math.round((c.score || 0) * 100);
      return `<li>
        <span>${i + 1}. ${escapeHtml(c.inci)}</span>
        <span class="score-bar-wrap"><span class="score-bar" style="width:${pct}%"></span></span>
        <span>${pct}%</span>
      </li>`;
    })
    .join("");
  return `<details class="candidates">
      <summary>Alternatives (${candidates.length})</summary>
      <ul class="candidate-list">${items}</ul>
    </details>`;
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

els.normalizeBtn.addEventListener("click", normalize);
els.sampleBtn.addEventListener("click", () => {
  els.input.value = SAMPLE;
});
checkHealth();