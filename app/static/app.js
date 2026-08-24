/* ===== VERA DASHBOARD — app.js ===== */

// ---- HEALTH POLLING ----
async function fetchHealth() {
  try {
    const r = await fetch("/v1/healthz");
    const d = await r.json();
    // Hero stats
    document.getElementById("uptime-hero").textContent = d.uptime_seconds ?? "—";
    const total = (d.contexts_loaded?.category ?? 0) + (d.contexts_loaded?.merchant ?? 0) +
                  (d.contexts_loaded?.customer ?? 0) + (d.contexts_loaded?.trigger ?? 0);
    document.getElementById("ctx-hero").textContent = total;
    // Dashboard cards
    document.getElementById("status-val").textContent = d.status === "ok" ? "✅ OK" : "⚠️ " + d.status;
    const uptime = d.uptime_seconds;
    const h = Math.floor(uptime / 3600), m = Math.floor((uptime % 3600) / 60), s = uptime % 60;
    document.getElementById("uptime-val").textContent =
      h > 0 ? h + "h " + m + "m" : m > 0 ? m + "m " + s + "s" : s + "s";
    document.getElementById("ctx-category").textContent = d.contexts_loaded?.category ?? 0;
    document.getElementById("ctx-merchant").textContent = d.contexts_loaded?.merchant ?? 0;
    document.getElementById("ctx-customer").textContent = d.contexts_loaded?.customer ?? 0;
    document.getElementById("ctx-trigger").textContent = d.contexts_loaded?.trigger ?? 0;
  } catch (e) {
    document.getElementById("status-val").textContent = "❌ Offline";
  }
}

async function fetchMetadata() {
  try {
    const r = await fetch("/v1/metadata");
    const d = await r.json();
    document.getElementById("meta-team").textContent = d.team_name ?? "—";
    document.getElementById("meta-model").textContent = d.model ?? "—";
    document.getElementById("meta-version").textContent = d.version ?? "—";
  } catch {}
}

fetchHealth();
fetchMetadata();
setInterval(fetchHealth, 5000);

// ---- API EXPLORER ----
async function tryEndpoint(method, path, body, resultId) {
  const el = document.getElementById(resultId);
  el.textContent = "Loading…";
  el.classList.add("visible");
  try {
    const opts = { method, headers: { "Content-Type": "application/json" } };
    if (body) opts.body = JSON.stringify(body);
    const r = await fetch(path, opts);
    const d = await r.json();
    el.textContent = JSON.stringify(d, null, 2);
  } catch (e) {
    el.textContent = "Error: " + e.message;
  }
}

function tryContext() {
  tryEndpoint("POST", "/v1/context", {
    scope: "category",
    context_id: "cat_restaurant",
    version: 1,
    payload: {
      category_name: "Restaurants",
      triggers_supported: ["birthday_offer", "winback"],
      avg_spend_inr: 450,
      visit_frequency_days: 14
    }
  }, "result-context");
}

function tryTick() {
  tryEndpoint("POST", "/v1/tick", {
    merchant_id: "merch_001",
    customer_ids: ["cust_001", "cust_002"],
    now: new Date().toISOString()
  }, "result-tick");
}

function tryReply() {
  tryEndpoint("POST", "/v1/reply", {
    conversation_id: "conv_api_demo",
    merchant_id: "merch_001",
    customer_id: "cust_001",
    message: "Hi, I am interested in your offer",
    from_role: "customer",
    received_at: new Date().toISOString(),
    now: new Date().toISOString()
  }, "result-reply");
}

// ---- CHAT DEMO ----
function getConfig() {
  return {
    merchant: document.getElementById("cfg-merchant").value || "merch_001",
    customer: document.getElementById("cfg-customer").value || "cust_001",
    conv: document.getElementById("cfg-conv").value || "conv_demo_001"
  };
}

function addMessage(role, text) {
  const container = document.getElementById("chat-messages");
  const div = document.createElement("div");
  div.className = "message message-" + role;
  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";
  bubble.textContent = text;
  div.appendChild(bubble);
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  return bubble;
}

function setMessage(text) {
  document.getElementById("chat-input").value = text;
  document.getElementById("chat-input").focus();
}

async function sendChat() {
  const input = document.getElementById("chat-input");
  const msg = input.value.trim();
  if (!msg) return;
  input.value = "";

  addMessage("user", msg);

  const cfg = getConfig();
  const typingBubble = addMessage("bot", "Vera is typing…");
  typingBubble.classList.add("msg-typing");

  try {
    const r = await fetch("/v1/reply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversation_id: cfg.conv,
        merchant_id: cfg.merchant,
        customer_id: cfg.customer,
        message: msg,
        from_role: "customer",
        received_at: new Date().toISOString(),
        now: new Date().toISOString()
      })
    });
    const d = await r.json();
    typingBubble.textContent = d.body || JSON.stringify(d);
    typingBubble.classList.remove("msg-typing");
    if (d.action === "end") {
      typingBubble.textContent += "\n\n[Conversation ended]";
    }
  } catch (e) {
    typingBubble.textContent = "⚠️ Error: " + e.message;
    typingBubble.classList.remove("msg-typing");
  }
}

async function resetChat() {
  try {
    await fetch("/v1/reset", { method: "POST" });
  } catch {}
  const container = document.getElementById("chat-messages");
  container.innerHTML = "";
  addMessage("bot", "🔄 Session reset. Start a fresh conversation!");
  // Re-generate conv ID to force new session
  document.getElementById("cfg-conv").value = "conv_demo_" + Date.now();
}
