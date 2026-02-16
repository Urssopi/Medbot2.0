const chatLog = document.getElementById("chat-log");
const composer = document.getElementById("composer");
const input = document.getElementById("message-input");
const sendBtn = document.getElementById("send-btn");
const caseList = document.getElementById("case-list");
const caseDetail = document.getElementById("case-detail");
const statusPill = document.getElementById("status-pill");
const tabsContainer = document.getElementById("conversation-tabs");
const newChatBtn = document.getElementById("new-chat-btn");

const STORAGE_KEY = "medbot_web_state_v1";
const MAX_TAB_TITLE_LEN = 28;
const INITIAL_PROMPT =
  "To help you better, please share your symptoms and include: age, sex/gender, how long symptoms have been present, severity (mild/moderate/severe), relevant medical history, current medications, and allergies.";

let appState = loadState();

function setStatus(text, type = "") {
  statusPill.textContent = text;
  statusPill.classList.remove("good", "bad");
  if (type) {
    statusPill.classList.add(type);
  }
}

function buildDefaultState() {
  const tab = {
    id: `default-${Date.now()}`,
    title: "Chat 1",
    createdAt: Date.now(),
    updatedAt: Date.now(),
    messages: [{ kind: "bot", text: INITIAL_PROMPT }],
    matches: [],
    activeCaseIndex: 0,
  };
  return { tabs: [tab], activeTabId: tab.id };
}

function cleanTitle(text, number) {
  const fallback = `Chat ${number}`;
  if (typeof text !== "string") return fallback;
  const trimmed = text.trim();
  if (!trimmed) return fallback;
  return trimmed.slice(0, MAX_TAB_TITLE_LEN);
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return buildDefaultState();

    const parsed = JSON.parse(raw);
    if (!parsed || !Array.isArray(parsed.tabs) || !parsed.tabs.length) {
      return buildDefaultState();
    }

    const normalizedTabs = parsed.tabs
      .filter((tab) => tab && typeof tab.id === "string")
      .map((tab, idx) => ({
        id: tab.id,
        title: cleanTitle(tab.title, idx + 1),
        createdAt: Number(tab.createdAt) || Date.now(),
        updatedAt: Number(tab.updatedAt) || Date.now(),
        messages: Array.isArray(tab.messages)
          ? tab.messages.filter((m) => m && m.kind && typeof m.text === "string")
          : [],
        matches: Array.isArray(tab.matches) ? tab.matches : [],
        activeCaseIndex: Number.isInteger(tab.activeCaseIndex) ? tab.activeCaseIndex : 0,
      }));

    if (!normalizedTabs.length) return buildDefaultState();

    const hasActive = normalizedTabs.some((t) => t.id === parsed.activeTabId);
    return {
      tabs: normalizedTabs,
      activeTabId: hasActive ? parsed.activeTabId : normalizedTabs[0].id,
    };
  } catch {
    return buildDefaultState();
  }
}

function saveState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(appState));
}

function getActiveTab() {
  return appState.tabs.find((tab) => tab.id === appState.activeTabId) || appState.tabs[0];
}

function setActiveTab(tabId) {
  const exists = appState.tabs.some((tab) => tab.id === tabId);
  if (!exists) return;
  appState.activeTabId = tabId;
  saveState();
  renderAll();
  input.focus();
}

function maybeUpdateTitleFromMessage(tab, message) {
  if (!tab || tab.messages.length > 0) return;
  const normalized = message.replace(/\s+/g, " ").trim();
  if (!normalized) return;
  tab.title = cleanTitle(normalized, 1);
}

function createTab(title = "") {
  const nextNumber = appState.tabs.length + 1;
  const tab = {
    id: `${Date.now()}-${Math.random().toString(16).slice(2, 8)}`,
    title: title || `Chat ${nextNumber}`,
    createdAt: Date.now(),
    updatedAt: Date.now(),
    messages: [{ kind: "bot", text: INITIAL_PROMPT }],
    matches: [],
    activeCaseIndex: 0,
  };
  appState.tabs.unshift(tab);
  appState.activeTabId = tab.id;
  saveState();
  renderAll();
  input.focus();
}

function deleteTab(tabId) {
  const index = appState.tabs.findIndex((tab) => tab.id === tabId);
  if (index < 0) return;

  appState.tabs.splice(index, 1);

  if (!appState.tabs.length) {
    appState = buildDefaultState();
  } else if (appState.activeTabId === tabId) {
    appState.activeTabId = appState.tabs[Math.max(0, index - 1)].id;
  }

  saveState();
  renderAll();
  input.focus();
}

function appendMessageToActiveTab(kind, text) {
  const tab = getActiveTab();
  if (!tab) return;
  const value = String(text || "");
  maybeUpdateTitleFromMessage(tab, value);
  tab.messages.push({ kind, text: value });
  tab.updatedAt = Date.now();
  saveState();
  renderChat(tab.messages);
  renderTabs();
}

function renderChat(messages) {
  chatLog.innerHTML = "";
  messages.forEach((entry) => {
    const el = document.createElement("div");
    el.className = `bubble ${entry.kind}`;
    el.textContent = entry.text;
    chatLog.appendChild(el);
  });
  chatLog.scrollTop = chatLog.scrollHeight;
}

function showCaseDetail(matches, index) {
  const row = matches[index] || matches[0];
  if (!row) return;
  const fullEncounter = row.chunk_text || row.chunk_excerpt || "No encounter text available.";
  caseDetail.textContent = [
    `Encounter ID: ${row.encounter_id || "N/A"}`,
    `Chief Complaint: ${row.chief_complaint || "N/A"}`,
    `Final Diagnosis: ${row.final_dx || "N/A"}`,
    `Score: ${row.score || 0}`,
    "",
    row.summary || "No summary available.",
    "",
    "Matched Encounter Text:",
    fullEncounter,
  ].join("\n");
}

function renderCases(matches, activeCaseIndex = 0) {
  const safeMatches = Array.isArray(matches) ? matches : [];
  caseList.innerHTML = "";
  if (!safeMatches.length) {
    caseDetail.textContent = "No matched dataset cases found for this prompt.";
    return;
  }

  safeMatches.forEach((item, idx) => {
    const li = document.createElement("li");
    li.className = "case-item";
    if (idx === activeCaseIndex) li.classList.add("active");
    li.innerHTML = `
      <p class="case-title">${item.chief_complaint || "Unknown Complaint"}</p>
      <p class="case-meta">Encounter ${item.encounter_id || "N/A"} | Score ${item.score || 0}</p>
    `;
    li.addEventListener("click", () => {
      document.querySelectorAll(".case-item").forEach((x) => x.classList.remove("active"));
      li.classList.add("active");
      const tab = getActiveTab();
      if (tab) {
        tab.activeCaseIndex = idx;
        saveState();
      }
      showCaseDetail(safeMatches, idx);
    });
    caseList.appendChild(li);
  });

  showCaseDetail(safeMatches, activeCaseIndex);
}

function renderTabs() {
  tabsContainer.innerHTML = "";
  appState.tabs.forEach((tab) => {
    const row = document.createElement("div");
    row.className = "chat-tab-row";

    const openBtn = document.createElement("button");
    openBtn.type = "button";
    openBtn.className = "conversation-tab";
    if (tab.id === appState.activeTabId) openBtn.classList.add("active");
    openBtn.textContent = tab.title;
    openBtn.title = tab.title;
    openBtn.addEventListener("click", () => setActiveTab(tab.id));

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.className = "delete-chat-btn";
    deleteBtn.textContent = "Delete";
    deleteBtn.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      deleteTab(tab.id);
    });

    row.appendChild(openBtn);
    row.appendChild(deleteBtn);
    tabsContainer.appendChild(row);
  });
}

function renderAll() {
  const tab = getActiveTab();
  if (!tab) return;
  renderTabs();
  renderChat(tab.messages);
  renderCases(tab.matches, tab.activeCaseIndex || 0);
}

async function loadStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    if (data.reindexing) {
      setStatus("Reindexing RAG...", "bad");
    } else if (data.dataset_loaded && data.rag_ready) {
      setStatus(`Ready | ${data.records} cases | ${data.indexed_chunks} chunks indexed`, "good");
    } else if (data.dataset_loaded) {
      setStatus(`Dataset loaded, RAG not ready`, "bad");
    } else {
      setStatus("Dataset missing", "bad");
    }
  } catch (_err) {
    setStatus("Backend unavailable", "bad");
  }
}

async function sendMessage(message) {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  const data = await res.json();
  if (!res.ok || !data.ok) {
    throw new Error(data.error || "Request failed");
  }
  return data;
}

composer.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) return;

  appendMessageToActiveTab("user", message);
  input.value = "";
  sendBtn.disabled = true;
  setStatus("Generating response...");

  try {
    const data = await sendMessage(message);
    appendMessageToActiveTab("bot", data.response);

    const tab = getActiveTab();
    if (tab) {
      tab.matches = Array.isArray(data.matches) ? data.matches : [];
      tab.activeCaseIndex = 0;
      tab.updatedAt = Date.now();
      saveState();
      renderCases(tab.matches, tab.activeCaseIndex);
    }

    setStatus("Ready", "good");
  } catch (err) {
    appendMessageToActiveTab("system", `Error: ${err.message}`);
    setStatus("Request failed", "bad");
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
});

input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && event.shiftKey) {
    event.preventDefault();
    composer.requestSubmit();
  }
});

newChatBtn.addEventListener("click", () => createTab());

renderAll();
loadStatus();
input.focus();
