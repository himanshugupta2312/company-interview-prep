const elements = {
  company: document.querySelector("#company"),
  position: document.querySelector("#position"),
  type: document.querySelector("#type"),
  search: document.querySelector("#search"),
  difficulty: document.querySelector("#difficulty"),
  period: document.querySelector("#period"),
  companyOptions: document.querySelector("#company-options"),
  questionList: document.querySelector("#question-list"),
  resultsTitle: document.querySelector("#results-title"),
  totalCount: document.querySelector("#total-count"),
  leetcodeCount: document.querySelector("#leetcode-count"),
  designCount: document.querySelector("#design-count"),
  behavioralCount: document.querySelector("#behavioral-count"),
  positionNotice: document.querySelector("#position-notice"),
  errorMessage: document.querySelector("#error-message"),
  resultsSection: document.querySelector(".results-section"),
  loadMoreButton: document.querySelector("#load-more-button"),
  refreshButton: document.querySelector("#refresh-button"),
  syncIndicator: document.querySelector("#sync-indicator"),
  syncLabel: document.querySelector("#sync-label"),
};

let companiesLoaded = false;
let searchTimer;
let currentRequest = 0;
let loadedCount = 0;
let totalResults = 0;
const pageSize = 50;

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);
}

function setSyncStatus(state, message) {
  elements.syncIndicator.className = `status-dot ${state}`;
  elements.syncLabel.textContent = message;
}

function formatTimestamp(value) {
  if (!value) return "Not refreshed yet";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Refresh status unavailable";
  return `Checked ${date.toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}`;
}

function updateCompanyOptions(companies) {
  if (companiesLoaded) return;
  const fragment = document.createDocumentFragment();
  for (const company of companies) {
    const option = document.createElement("option");
    option.value = company;
    fragment.append(option);
  }
  elements.companyOptions.replaceChildren(fragment);
  companiesLoaded = true;
}

function renderCard(question) {
  const typeLabel = {
    leetcode: "LeetCode",
    "system-design": "System design",
    behavioral: "Behavioral",
  }[question.type] || "Question";
  const difficulty = question.difficulty
    ? `<span class="difficulty ${escapeHtml(question.difficulty.toLowerCase())}">${escapeHtml(question.difficulty)}</span>`
    : "";
  const topics = (question.topics || []).slice(0, 5)
    .map((topic) => `<span class="tag">${escapeHtml(topic)}</span>`)
    .join("");
  const windows = (question.time_windows || [])
    .map((window) => `<span class="window-tag">${escapeHtml(window)}</span>`)
    .join("");
  const company = question.company
    ? `<span>${escapeHtml(question.company)} · position not specified</span>`
    : `<span>General practice · not company-specific</span>`;
  const problemLink = question.link
    ? `<a href="${escapeHtml(question.link)}" target="_blank" rel="noreferrer">Open problem ↗</a>`
    : "";
  const sourceLink = question.source_url
    ? `<a href="${escapeHtml(question.source_url)}" target="_blank" rel="noreferrer">Source ↗</a>`
    : "";
  const rate = Number.parseFloat(question.acceptance_rate);
  const frequency = Number.parseFloat(question.frequency);
  const metrics = [
    Number.isFinite(frequency) ? `All-time frequency ${frequency.toFixed(1)}` : "",
    Number.isFinite(rate) ? `Acceptance ${(rate * 100).toFixed(1)}%` : "",
  ].filter(Boolean).join(" · ");

  return `
    <article class="question-card">
      <div class="card-topline">
        <span class="type-pill ${escapeHtml(question.type)}">${typeLabel}</span>
        ${difficulty}
      </div>
      <h3>${escapeHtml(question.title)}</h3>
      ${topics ? `<div class="tag-row">${topics}</div>` : ""}
      ${windows ? `<div class="tag-row">${windows}</div>` : ""}
      <div class="card-footer">
        <span>${company}${metrics ? ` · ${escapeHtml(metrics)}` : ""}</span>
        <span>${problemLink}${problemLink && sourceLink ? " · " : ""}${sourceLink}</span>
      </div>
    </article>`;
}

function renderQuestions(data, append) {
  updateCompanyOptions(data.companies || []);
  elements.resultsSection.setAttribute("aria-busy", "false");
  elements.resultsTitle.textContent = data.selected_company
    ? `${data.selected_company} interview questions`
    : "Interview question collection";
  elements.totalCount.textContent = data.total;
  totalResults = data.total;
  elements.leetcodeCount.textContent = data.counts.leetcode;
  elements.designCount.textContent = data.counts["system-design"];
  elements.behavioralCount.textContent = data.counts.behavioral;
  elements.positionNotice.textContent = data.selected_position
    ? `Position “${data.selected_position}”: ${data.position_notice}`
    : data.position_notice;
  elements.errorMessage.hidden = true;
  if (append) {
    elements.questionList.insertAdjacentHTML("beforeend", data.results.map(renderCard).join(""));
  } else {
    loadedCount = 0;
    elements.questionList.innerHTML = data.results.length
      ? data.results.map(renderCard).join("")
      : `<div class="empty-state">
        <strong>${data.selected_company ? "No questions match these filters." : "Choose a company to browse its LeetCode questions."}</strong>
        ${data.selected_company
          ? "Try another time period or clear a filter. General system-design and behavioral questions are included when they match your search."
          : "System-design and behavioral practice are available below even before you choose a company."}
      </div>`;
  }
  loadedCount += data.results.length;
  elements.loadMoreButton.hidden = !data.has_more;
  elements.loadMoreButton.textContent = `Load more questions (${Math.max(0, totalResults - loadedCount)} remaining)`;
  setSyncStatus("ready", formatTimestamp(data.refreshed_at));
}

function showError(message) {
  elements.resultsSection.setAttribute("aria-busy", "false");
  elements.errorMessage.textContent = message;
  elements.errorMessage.hidden = false;
  setSyncStatus("error", "Could not load the latest questions");
}

async function loadQuestions(offset = 0, append = false) {
  const requestId = ++currentRequest;
  const params = new URLSearchParams();
  for (const [key, element] of Object.entries({
    company: elements.company,
    position: elements.position,
    type: elements.type,
    search: elements.search,
    difficulty: elements.difficulty,
    period: elements.period,
  })) {
    if (element.value.trim()) params.set(key, element.value.trim());
  }
  params.set("offset", String(offset));
  params.set("limit", String(pageSize));

  elements.resultsSection.setAttribute("aria-busy", "true");
  try {
    const response = await fetch(`/api/questions?${params.toString()}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not load questions.");
    if (requestId === currentRequest) renderQuestions(data, append);
  } catch (error) {
    if (requestId === currentRequest) showError(error.message);
  }
}

function loadMoreQuestions() {
  if (loadedCount < totalResults) loadQuestions(loadedCount, true);
}

function scheduleSearch() {
  window.clearTimeout(searchTimer);
  searchTimer = window.setTimeout(loadQuestions, 180);
}

async function refreshSources() {
  elements.refreshButton.disabled = true;
  elements.refreshButton.textContent = "Refreshing…";
  setSyncStatus("busy", "Checking for source updates…");
  try {
    const response = await fetch("/api/refresh", { method: "POST" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Could not refresh sources.");
    await loadQuestions();
  } catch (error) {
    showError(error.message);
  } finally {
    elements.refreshButton.disabled = false;
    elements.refreshButton.textContent = "Refresh sources";
  }
}

for (const element of [
  elements.company,
  elements.position,
  elements.search,
]) {
  element.addEventListener("input", scheduleSearch);
}
for (const element of [
  elements.type,
  elements.difficulty,
  elements.period,
]) {
  element.addEventListener("change", () => loadQuestions());
}
elements.refreshButton.addEventListener("click", refreshSources);
elements.loadMoreButton.addEventListener("click", loadMoreQuestions);

loadQuestions();
