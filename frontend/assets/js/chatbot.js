/**
 * Web chat widget (Session 6).
 *
 * A no-build vanilla-JS floating chat that talks to the standalone bot service
 * (POST {BOT_BASE_URL}/bot/v1/chat, see bot/). Loaded on public pages after the
 * existing script chain, so CLINIC_CONFIG / Auth / Theme / I18n are available.
 *
 * - Renders only when the bot is configured (config.js BOT_BASE_URL) AND the
 *   clinic has it enabled (theme.chatbot_enabled, admin toggle). Mounts/unmounts
 *   live on `clinic:themechange`.
 * - conversation_id + transcript persist in localStorage (keyed by clinic slug)
 *   so the chat survives reloads; a reset button starts a fresh conversation.
 * - Logged-in users (Auth) seed the first turn with name/phone so the bot skips
 *   the identity questions; guests are asked in-chat (handled server-side).
 * - Chrome strings are i18n and re-render on `clinic:langchange`. RTL/LTR follows
 *   <html dir>. EVERY bot/user string is esc()'d before innerHTML insertion -
 *   both are untrusted.
 */
const Chatbot = {
  STORAGE_PREFIX: "clinic_chat:",
  conversationId: null,
  transcript: [], // [{ role: "user"|"bot"|"error", text, ts }]
  busy: false,
  identitySent: false,
  root: null,

  // ---- config helpers ----
  botBase() {
    return (window.CLINIC_CONFIG.BOT_BASE_URL || "").replace(/\/$/, "");
  },
  tenant() {
    return window.CLINIC_CONFIG.BOT_TENANT || window.CLINIC_CONFIG.CLINIC_SLUG || "";
  },
  configured() {
    return !!this.botBase() && !!this.tenant();
  },
  enabled() {
    if (!this.configured()) return false;
    const t = window.Theme && Theme.current;
    // Default on: only an explicit `false` (admin toggle off) hides the widget.
    return !t || t.chatbot_enabled !== false;
  },

  _key(suffix) {
    return this.STORAGE_PREFIX + (window.CLINIC_CONFIG.CLINIC_SLUG || "default") + ":" + suffix;
  },

  // ---- persistence ----
  load() {
    try {
      this.conversationId = localStorage.getItem(this._key("cid")) || null;
      const raw = localStorage.getItem(this._key("log"));
      this.transcript = raw ? JSON.parse(raw) : [];
    } catch (_) {
      this.transcript = [];
    }
    if (!Array.isArray(this.transcript)) this.transcript = [];
    if (!this.conversationId) this.conversationId = this._newId();
    // If we already have user turns, the server likely knows the identity.
    this.identitySent = this.transcript.some((m) => m.role === "user");
  },
  persist() {
    try {
      localStorage.setItem(this._key("cid"), this.conversationId);
      localStorage.setItem(this._key("log"), JSON.stringify(this.transcript));
    } catch (_) { /* quota/full - non-fatal */ }
  },
  _newId() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    return "c" + Date.now() + Math.random().toString(36).slice(2, 12);
  },

  // ---- mount / unmount ----
  sync() {
    if (this.enabled()) this.mount();
    else this.unmount();
  },
  mount() {
    if (this.root) return;
    this.load();
    const el = document.createElement("div");
    el.className = "chatbot-root";
    el.innerHTML = this._shell();
    document.body.appendChild(el);
    this.root = el;
    this._wire();
    this.renderChrome();
    this.renderMessages();
  },
  unmount() {
    if (!this.root) return;
    this.root.remove();
    this.root = null;
  },

  _shell() {
    const chat = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/></svg>`;
    const close = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>`;
    const reset = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 4v6h-6"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>`;
    const send = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>`;
    return `
      <button type="button" class="chatbot-fab" data-cb="open" aria-label="chat">${chat}</button>
      <div class="chatbot-panel" role="dialog" aria-modal="false">
        <div class="chatbot-header">
          <img class="chatbot-header-logo" data-cb="logo" alt="" hidden>
          <div class="chatbot-header-meta">
            <div class="chatbot-header-name" data-cb="title"></div>
            <div class="chatbot-header-status" data-cb="status"></div>
          </div>
          <button type="button" class="chatbot-header-btn" data-cb="reset" title="">${reset}</button>
          <button type="button" class="chatbot-header-btn" data-cb="close" aria-label="close">${close}</button>
        </div>
        <div class="chatbot-messages" data-cb="messages"></div>
        <form class="chatbot-input-row" data-cb="form">
          <textarea class="chatbot-input" data-cb="input" rows="1"></textarea>
          <button type="submit" class="chatbot-send" data-cb="send">${send}</button>
        </form>
      </div>`;
  },

  _el(name) {
    return this.root.querySelector(`[data-cb="${name}"]`);
  },

  _wire() {
    this._el("open").addEventListener("click", () => this.open());
    this._el("close").addEventListener("click", () => this.close());
    this._el("reset").addEventListener("click", () => this.reset());
    this._el("form").addEventListener("submit", (e) => {
      e.preventDefault();
      this.send();
    });
    const input = this._el("input");
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        this.send();
      }
    });
    input.addEventListener("input", () => {
      input.style.height = "auto";
      input.style.height = Math.min(input.scrollHeight, 100) + "px";
    });
  },

  open() {
    this.root.classList.add("is-open");
    setTimeout(() => this._el("input").focus(), 220);
    this.scrollDown();
  },
  close() {
    this.root.classList.remove("is-open");
  },
  reset() {
    this.conversationId = this._newId();
    this.transcript = [];
    this.identitySent = false;
    this.persist();
    this.renderMessages();
    this._el("input").focus();
  },

  // ---- chrome (i18n + theme) ----
  renderChrome() {
    if (!this.root) return;
    const name = (window.I18n && I18n.clinicName()) || "";
    this._el("title").textContent = name;
    this._el("status").textContent = this._t("chatbot.status", "Online");
    const input = this._el("input");
    input.setAttribute("placeholder", this._t("chatbot.placeholder", "Type a message…"));
    this._el("reset").title = this._t("chatbot.reset", "New chat");
    const logo = this._el("logo");
    const url = window.CLINIC_CONFIG.CLINIC_LOGO_URL;
    if (url) { logo.src = url; logo.hidden = false; } else { logo.hidden = true; }
    // Greeting shown while the transcript is empty re-translates with the chrome.
    if (!this.transcript.length) this.renderMessages();
  },

  _t(key, fallback) {
    return (window.I18n && I18n.t(key, fallback)) || fallback;
  },

  // ---- messages ----
  renderMessages() {
    if (!this.root) return;
    const host = this._el("messages");
    let html = "";
    if (!this.transcript.length) {
      html += this._bubble("bot", this._t("chatbot.greeting", "Hello! How can I help you book an appointment?"), null);
    }
    this.transcript.forEach((m) => { html += this._bubble(m.role, m.text, m.ts); });
    if (this.busy) {
      html += `<div class="chatbot-typing"><span></span><span></span><span></span></div>`;
    }
    host.innerHTML = html;
    this.scrollDown();
  },

  _bubble(role, text, ts) {
    const cls = role === "user" ? "user" : role === "error" ? "error" : "bot";
    const time = ts ? `<div class="chatbot-msg-time">${esc(this._time(ts))}</div>` : "";
    return `<div class="chatbot-msg ${cls}"><div class="chatbot-msg-bubble">${esc(text)}</div>${time}</div>`;
  },

  _time(ts) {
    const locale = window.I18n && I18n.lang === "ar" ? "ar-EG" : "tr-TR";
    try {
      return new Date(ts).toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
    } catch (_) {
      return "";
    }
  },

  scrollDown() {
    if (!this.root) return;
    const host = this._el("messages");
    requestAnimationFrame(() => { host.scrollTop = host.scrollHeight; });
  },

  // ---- send ----
  async send() {
    if (this.busy) return;
    const input = this._el("input");
    const text = input.value.trim();
    if (!text) return;

    input.value = "";
    input.style.height = "auto";
    this.transcript.push({ role: "user", text, ts: Date.now() });
    this.persist();
    this.busy = true;
    this._el("send").disabled = true;
    this.renderMessages();

    const body = { conversation_id: this.conversationId, message: text };
    // Seed identity from the logged-in profile on the first turn only; the bot
    // sets it once server-side and never overwrites it.
    if (!this.identitySent) {
      const identity = this._identity();
      if (identity) body.identity = identity;
      this.identitySent = true;
    }

    let reply, errored = false;
    try {
      const res = await fetch(this.botBase() + "/bot/v1/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Bot-Tenant": this.tenant() },
        body: JSON.stringify(body),
      });
      const payload = await res.json().catch(() => null);
      if (!res.ok) {
        errored = true;
        reply = (payload && payload.detail) || this._t("chatbot.error", "Something went wrong. Please try again.");
        if (typeof reply !== "string") reply = this._t("chatbot.error", "Something went wrong. Please try again.");
      } else {
        reply = (payload && payload.reply) || "";
      }
    } catch (_) {
      errored = true;
      reply = this._t("chatbot.offline", "Cannot reach the assistant. Please try again later.");
    }

    this.busy = false;
    this._el("send").disabled = false;
    if (reply) this.transcript.push({ role: errored ? "error" : "bot", text: reply, ts: Date.now() });
    this.persist();
    this.renderMessages();
    input.focus();
  },

  _identity() {
    if (!window.Auth || !Auth.isLoggedIn()) return null;
    const u = Auth.getUser();
    if (!u || !u.full_name || !u.phone) return null; // bot requires name + phone
    return { full_name: u.full_name, phone: u.phone };
  },
};

document.addEventListener("clinic:langchange", () => Chatbot.renderChrome());
document.addEventListener("clinic:themechange", () => Chatbot.sync());

// The theme may already be cached/applied by the time we load; mount now and let
// themechange re-evaluate once the fresh theme arrives.
Chatbot.sync();
