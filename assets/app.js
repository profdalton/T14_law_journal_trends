const ROMAN = ["I","II","III","IV","V","VI","VII","VIII","IX","X","XI","XII","XIII","XIV","XV","XVI"];

let ALL_ARTICLES = [];
let TOPIC_ORDER = [];

async function init() {
  const [articlesRes, topicsRes] = await Promise.all([
    fetch("data/articles.json"),
    fetch("data/topics.json")
  ]);
  const articlesData = await articlesRes.json();
  const topicsData = await topicsRes.json();
  let historySnapshots = [];
  try {
    const historyRes = await fetch("data/topic-history.json");
    const historyData = await historyRes.json();
    historySnapshots = historyData.snapshots || [];
  } catch (e) {
    console.warn("Topic history unavailable yet:", e);
  }

  ALL_ARTICLES = articlesData.articles || [];
  TOPIC_ORDER = topicsData.topics || [];

  document.getElementById("lastUpdated").textContent =
    "Last scanned \u2014 " + formatDate(articlesData.generated_at);

  populateFilters();
  renderTicker();
  try {
    renderTrendChart(historySnapshots);
  } catch (e) {
    // Never let the trend chart take down the rest of the page.
    console.error("Trend chart failed to render:", e);
  }
  render();

  document.getElementById("searchBox").addEventListener("input", render);
  document.getElementById("journalFilter").addEventListener("change", render);
  document.getElementById("topicFilter").addEventListener("change", render);
  document.getElementById("typeFilter").addEventListener("change", render);
  document.getElementById("exportCsv").addEventListener("click", exportCsv);
  document.getElementById("exportJson").addEventListener("click", exportJson);
}

function formatDate(iso) {
  if (!iso) return "unknown";
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
}

function populateFilters() {
  const journals = [...new Set(ALL_ARTICLES.map(a => a.journal))].sort();
  const journalSel = document.getElementById("journalFilter");
  journals.forEach(j => {
    const opt = document.createElement("option");
    opt.value = j; opt.textContent = j;
    journalSel.appendChild(opt);
  });

  const topicSel = document.getElementById("topicFilter");
  TOPIC_ORDER.forEach(t => {
    const opt = document.createElement("option");
    opt.value = t; opt.textContent = t;
    topicSel.appendChild(opt);
  });

  const types = [...new Set(ALL_ARTICLES.map(a => a.article_type).filter(Boolean))].sort();
  const typeSel = document.getElementById("typeFilter");
  if (types.length === 0) {
    typeSel.hidden = true;
  } else {
    types.forEach(t => {
      const opt = document.createElement("option");
      opt.value = t; opt.textContent = t;
      typeSel.appendChild(opt);
    });
  }
}

function renderTicker() {
  const counts = {};
  TOPIC_ORDER.forEach(t => counts[t] = 0);
  ALL_ARTICLES.forEach(a => { counts[a.topic] = (counts[a.topic] || 0) + 1; });
  const max = Math.max(1, ...Object.values(counts));

  const ticker = document.getElementById("ticker");
  ticker.innerHTML = TOPIC_ORDER.map(t => {
    const c = counts[t] || 0;
    const pct = Math.round((c / max) * 100);
    return `
      <div class="ticker-item">
        <div class="t-name">${escapeHtml(t)}</div>
        <div class="ticker-bar-track"><div class="ticker-bar-fill" style="width:${pct}%"></div></div>
        <div class="t-count">${c}</div>
      </div>`;
  }).join("");
}

const TREND_COLORS = [
  "#ed3500", "#3c3333", "#8a6d3b", "#2f6b57", "#2f5d8a", "#a13d63", "#6b8e23"
];

function renderTrendChart(snapshots) {
  const wrap = document.querySelector(".trend-chart-wrap");
  const canvas = document.getElementById("trendChart");
  const emptyMsg = document.getElementById("trendEmpty");
  const sublabel = document.getElementById("trendSublabel");

  if (typeof Chart === "undefined") {
    // Chart.js failed to load (CDN blocked/down/ad-blocker/stale
    // upload missing the <script> tag). Fail soft instead of
    // throwing, so the rest of the page (articles, filters, search)
    // still works even if the trend chart can't render.
    console.warn("Chart.js not loaded -- skipping trend chart.");
    if (wrap) wrap.hidden = true;
    if (emptyMsg) {
      emptyMsg.hidden = false;
      emptyMsg.textContent = "Trend chart couldn't load (a required script didn't load).";
    }
    return;
  }

  if (snapshots.length < 2) {
    wrap.hidden = true;
    emptyMsg.hidden = false;
    sublabel.textContent = snapshots.length === 1 ? "1 week recorded so far" : "";
    return;
  }

  sublabel.textContent = `${snapshots.length} weeks recorded`;

  // Pick the topics with the highest total volume across all
  // recorded weeks, so the chart stays readable instead of showing
  // all 14 lines at once.
  const totals = {};
  snapshots.forEach(s => {
    Object.entries(s.counts || {}).forEach(([topic, count]) => {
      totals[topic] = (totals[topic] || 0) + count;
    });
  });
  const topTopics = Object.entries(totals)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 6)
    .map(([topic]) => topic);

  const labels = snapshots.map(s => {
    const d = new Date(s.date);
    return isNaN(d) ? s.date : d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  });

  const datasets = topTopics.map((topic, i) => ({
    label: topic,
    data: snapshots.map(s => (s.counts || {})[topic] || 0),
    borderColor: TREND_COLORS[i % TREND_COLORS.length],
    backgroundColor: TREND_COLORS[i % TREND_COLORS.length],
    borderWidth: 2,
    pointRadius: 2.5,
    tension: 0.25,
    fill: false,
  }));

  new Chart(canvas.getContext("2d"), {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          position: "bottom",
          labels: {
            color: "#3c3333",
            font: { family: "IBM Plex Sans", size: 11 },
            boxWidth: 12,
            padding: 12,
          },
        },
        tooltip: {
          titleFont: { family: "IBM Plex Mono" },
          bodyFont: { family: "IBM Plex Sans" },
        },
      },
      scales: {
        x: {
          ticks: { color: "#7a6f6f", font: { family: "IBM Plex Mono", size: 10 } },
          grid: { color: "#ddd5c8" },
        },
        y: {
          beginAtZero: true,
          ticks: { color: "#7a6f6f", font: { family: "IBM Plex Mono", size: 10 }, precision: 0 },
          grid: { color: "#ddd5c8" },
        },
      },
    },
  });
}

function getFilteredArticles() {
  const q = document.getElementById("searchBox").value.trim().toLowerCase();
  const journal = document.getElementById("journalFilter").value;
  const topicFilter = document.getElementById("topicFilter").value;
  const typeFilter = document.getElementById("typeFilter").value;

  return ALL_ARTICLES.filter(a => {
    if (journal && a.journal !== journal) return false;
    if (topicFilter && a.topic !== topicFilter) return false;
    if (typeFilter && a.article_type !== typeFilter) return false;
    if (q) {
      const hay = (a.title + " " + a.authors + " " + a.journal).toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

function render() {
  const topicFilter = document.getElementById("topicFilter").value;
  const filtered = getFilteredArticles();

  document.getElementById("resultCount").textContent =
    `${filtered.length} article${filtered.length === 1 ? "" : "s"}`;

  const byTopic = {};
  filtered.forEach(a => {
    if (!byTopic[a.topic]) byTopic[a.topic] = [];
    byTopic[a.topic].push(a);
  });

  const container = document.getElementById("topics");
  container.innerHTML = "";

  const topicsToShow = topicFilter ? [topicFilter] : TOPIC_ORDER;
  let anyRendered = false;

  topicsToShow.forEach(topic => {
    const items = byTopic[topic];
    if (!items || items.length === 0) return;
    anyRendered = true;
    const numeral = ROMAN[TOPIC_ORDER.indexOf(topic)] || "\u2014";

    const section = document.createElement("section");
    section.className = "topic-section";
    section.innerHTML = `
      <div class="topic-heading">
        <span class="topic-numeral">${numeral}.</span>
        <h2>${escapeHtml(topic)}</h2>
        <span class="topic-count">${items.length}</span>
      </div>
      <div class="article-grid"></div>
    `;
    const grid = section.querySelector(".article-grid");
    items
      .sort((a, b) => (b.date || "").localeCompare(a.date || ""))
      .forEach(a => grid.appendChild(articleCard(a)));
    container.appendChild(section);
  });

  if (!anyRendered) {
    container.innerHTML = `<p class="no-results">No articles match those filters.</p>`;
  }
}

function articleCard(a) {
  const card = document.createElement("article");
  card.className = "article-card";
  const titleHtml = a.url
    ? `<a href="${escapeAttr(a.url)}" target="_blank" rel="noopener">${escapeHtml(a.title)}</a>`
    : escapeHtml(a.title);
  card.innerHTML = `
    <div class="article-meta"><span>${escapeHtml(a.journal)}</span><span>${escapeHtml(a.date || "")}</span></div>
    ${a.article_type ? `<span class="article-type-badge">${escapeHtml(a.article_type)}</span>` : ""}
    <h3>${titleHtml}</h3>
    ${a.authors ? `<p class="article-authors">${escapeHtml(a.authors)}</p>` : ""}
    ${a.snippet ? `<p class="article-snippet">${escapeHtml(a.snippet)}</p>` : ""}
  `;
  return card;
}

function downloadBlob(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function csvEscape(val) {
  const s = String(val ?? "");
  if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

function exportCsv() {
  const rows = getFilteredArticles();
  const cols = ["title", "authors", "journal", "topic", "article_type", "date", "url"];
  const lines = [cols.join(",")];
  rows.forEach(a => {
    lines.push(cols.map(c => csvEscape(a[c])).join(","));
  });
  downloadBlob(lines.join("\n"), "de-novo-articles.csv", "text/csv");
}

function exportJson() {
  const rows = getFilteredArticles();
  downloadBlob(JSON.stringify(rows, null, 2), "de-novo-articles.json", "application/json");
}

function escapeHtml(str) {
  return String(str || "").replace(/[&<>"']/g, s => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[s]));
}
function escapeAttr(str) { return escapeHtml(str); }

init();
