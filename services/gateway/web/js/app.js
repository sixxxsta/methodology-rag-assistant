const STORAGE_KEY = "methodology_session_id";

const messagesEl = document.getElementById("messages");
const form = document.getElementById("chatForm");
const input = document.getElementById("messageInput");
const sendBtn = document.getElementById("sendBtn");
const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");
const newChatBtn = document.getElementById("newChat");
const template = document.getElementById("messageTemplate");

let sessionId = localStorage.getItem(STORAGE_KEY) || "";
let lastQuestion = "";
let lastAnswer = "";

function autoResize() {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 140) + "px";
}

input.addEventListener("input", autoResize);

async function checkHealth() {
  try {
    const res = await fetch("/api/health");
    if (!res.ok) throw new Error("unhealthy");
    const data = await res.json();
    statusDot.className = "status-dot ok";
    const llm = data.llm_provider_active || data.llm_provider || "—";
    const pts = data.knowledge_points ?? 0;
    statusText.textContent = `Онлайн · LLM: ${llm} · ${pts} фрагментов в базе`;
  } catch {
    statusDot.className = "status-dot err";
    statusText.textContent = "RAG загружается… Сайт доступен, чат — через 1–3 мин";
  }
}

function appendMessage(role, text, sources = []) {
  const node = template.content.cloneNode(true);
  const article = node.querySelector(".message");
  article.classList.add(role);

  const content = node.querySelector(".content");
  content.textContent = text;

  if (role === "assistant" && sources.length) {
    const sourcesEl = node.querySelector(".sources");
    sourcesEl.classList.remove("hidden");
    const title = document.createElement("h3");
    title.textContent = "Источники";
    sourcesEl.appendChild(title);

    sources.forEach((s, i) => {
      const item = document.createElement("div");
      item.className = "source-item";
      item.innerHTML = `<strong>[${i + 1}] ${escapeHtml(s.source)}</strong> (${(s.score * 100).toFixed(0)}%)<br>${escapeHtml(s.excerpt)}`;
      sourcesEl.appendChild(item);
    });

    const feedback = node.querySelector(".feedback");
    feedback.classList.remove("hidden");
    const stars = node.querySelector(".stars");
    for (let r = 1; r <= 5; r++) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "star";
      btn.textContent = "★";
      btn.setAttribute("aria-label", `Оценка ${r}`);
      btn.addEventListener("click", () => submitFeedback(r, btn, stars));
      stars.appendChild(btn);
    }
  }

  messagesEl.appendChild(node);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function showTyping() {
  const el = document.createElement("article");
  el.className = "message assistant typing-row";
  el.innerHTML = `
    <div class="avatar"></div>
    <div class="bubble"><div class="typing"><span></span><span></span><span></span></div></div>
  `;
  el.id = "typing";
  messagesEl.appendChild(el);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function hideTyping() {
  document.getElementById("typing")?.remove();
}

async function sendMessage(text) {
  lastQuestion = text;
  appendMessage("user", text);
  showTyping();
  sendBtn.disabled = true;

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, session_id: sessionId }),
    });
    const data = await res.json();
    hideTyping();

    if (!res.ok) {
      appendMessage("assistant", data.error || "Ошибка сервера");
      return;
    }

    sessionId = data.session_id;
    localStorage.setItem(STORAGE_KEY, sessionId);
    lastAnswer = data.answer;
    appendMessage("assistant", data.answer, data.sources || []);
  } catch (err) {
    hideTyping();
    appendMessage("assistant", "Не удалось связаться с сервером. Запустите rag-service и Qdrant.");
    console.error(err);
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

async function submitFeedback(rating, btn, starsContainer) {
  starsContainer.querySelectorAll(".star").forEach((s) => s.classList.remove("active"));
  btn.classList.add("active");

  try {
    await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        rating,
        question: lastQuestion,
        answer: lastAnswer,
      }),
    });
  } catch (e) {
    console.warn("feedback failed", e);
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  autoResize();
  sendMessage(text);
});

input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    form.requestSubmit();
  }
});

newChatBtn.addEventListener("click", () => {
  sessionId = "";
  localStorage.removeItem(STORAGE_KEY);
  messagesEl.innerHTML = "";
  appendMessage("assistant", "Новый диалог. Задайте вопрос по методологии проекта — Scrum, Kanban, DevOps, документации.");
});

checkHealth();
setInterval(checkHealth, 30_000);

appendMessage(
  "assistant",
  "Привет! Я методологический ассистент. Спросите о планировании спринта, ролях в команде, Kanban, DevOps или документации по ГОСТ."
);
