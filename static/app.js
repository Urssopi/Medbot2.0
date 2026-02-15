const chatLog = document.getElementById("chat-log");
const composer = document.getElementById("composer");
const input = document.getElementById("message-input");
const sendBtn = document.getElementById("send-btn");
const caseList = document.getElementById("case-list");
const caseDetail = document.getElementById("case-detail");
const statusPill = document.getElementById("status-pill");

let lastMatches = [];

function setStatus(text, type = "") {
  statusPill.textContent = text;
  statusPill.classList.remove("good", "bad");
  if (type) {
    statusPill.classList.add(type);
  }
}

function addBubble(kind, text) {
  const el = document.createElement("div");
  el.className = `bubble ${kind}`;
  el.textContent = text;
  chatLog.appendChild(el);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function renderCases(matches) {
  lastMatches = matches || [];
  caseList.innerHTML = "";
  if (!lastMatches.length) {
    caseDetail.textContent = "No matched dataset cases found for this prompt.";
    return;
  }

  lastMatches.forEach((item, idx) => {
    const li = document.createElement("li");
    li.className = "case-item";
    if (idx === 0) li.classList.add("active");
    li.innerHTML = `
      <p class="case-title">${item.chief_complaint || "Unknown Complaint"}</p>
      <p class="case-meta">Encounter ${item.encounter_id || "N/A"} • Score ${item.score || 0}</p>
    `;
    li.addEventListener("click", () => {
      document.querySelectorAll(".case-item").forEach((x) => x.classList.remove("active"));
      li.classList.add("active");
      showCaseDetail(idx);
    });
    caseList.appendChild(li);
  });

  showCaseDetail(0);
}

function showCaseDetail(index) {
  const row = lastMatches[index];
  if (!row) return;
  caseDetail.textContent = [
    `Encounter ID: ${row.encounter_id || "N/A"}`,
    `Chief Complaint: ${row.chief_complaint || "N/A"}`,
    `Final Diagnosis: ${row.final_dx || "N/A"}`,
    `Score: ${row.score || 0}`,
    "",
    row.summary || "No summary available.",
  ].join("\n");
}

async function loadStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    if (data.dataset_loaded) {
      setStatus(`Ready • ${data.records} cases loaded`, "good");
    } else {
      setStatus("Dataset missing", "bad");
    }
  } catch (err) {
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

  addBubble("user", message);
  input.value = "";
  sendBtn.disabled = true;
  setStatus("Generating response...");

  try {
    const data = await sendMessage(message);
    addBubble("bot", data.response);
    renderCases(data.matches);
    setStatus("Ready", "good");
  } catch (err) {
    addBubble("system", `Error: ${err.message}`);
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

loadStatus();
input.focus();
