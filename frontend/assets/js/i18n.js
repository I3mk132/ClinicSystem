/**
 * Lightweight i18n engine (Arabic / Turkish).
 * - Persists the chosen language in localStorage.
 * - Sets <html lang dir> so RTL/LTR and fonts follow automatically (see style.css).
 * - Translates every element with [data-i18n]="namespace.key" (textContent)
 *   and [data-i18n-placeholder]="namespace.key" (input placeholder).
 * - Fires a `clinic:langchange` event so pages can re-render dynamic
 *   (API-driven) content in the new language.
 */
const I18n = {
  STORAGE_KEY: "clinic_lang",
  dict: {},
  lang: "ar",

  async init() {
    this.lang = localStorage.getItem(this.STORAGE_KEY) || "ar";
    await this.load(this.lang);
    this.applyDirection();
    this.translateDom();
    this.initSwitcher();
  },

  async load(lang) {
    const res = await fetch(`assets/i18n/${lang}.json`);
    this.dict = await res.json();
    this.lang = lang;
  },

  applyDirection() {
    document.documentElement.setAttribute("lang", this.lang);
    document.documentElement.setAttribute("dir", this.lang === "ar" ? "rtl" : "ltr");
  },

  t(key, fallback = "") {
    const parts = key.split(".");
    let node = this.dict;
    for (const part of parts) {
      node = node?.[part];
      if (node === undefined) return fallback || key;
    }
    return node;
  },

  translateDom(root = document) {
    root.querySelectorAll("[data-i18n]").forEach((el) => {
      el.textContent = this.t(el.getAttribute("data-i18n"));
    });
    root.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      el.setAttribute("placeholder", this.t(el.getAttribute("data-i18n-placeholder")));
    });
    root.querySelectorAll(".lang-switch button").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.lang === this.lang);
    });
  },

  async setLang(lang) {
    if (lang === this.lang) return;
    await this.load(lang);
    localStorage.setItem(this.STORAGE_KEY, lang);
    this.applyDirection();
    this.translateDom();
    document.dispatchEvent(new CustomEvent("clinic:langchange", { detail: { lang } }));
  },

  initSwitcher() {
    document.querySelectorAll(".lang-switch button").forEach((btn) => {
      btn.addEventListener("click", () => this.setLang(btn.dataset.lang));
    });
  },

  /** Localized clinic display name from config.js */
  clinicName() {
    return window.CLINIC_CONFIG.CLINIC_NAME[this.lang] || window.CLINIC_CONFIG.CLINIC_NAME.ar;
  },

  /** Format an ISO date (YYYY-MM-DD) using the active locale */
  formatDate(isoDate) {
    const d = new Date(isoDate + "T00:00:00");
    const locale = this.lang === "ar" ? "ar-EG" : "tr-TR";
    return d.toLocaleDateString(locale, { weekday: "short", day: "numeric", month: "short", year: "numeric" });
  },

  /** Format "HH:MM:SS" -> localized short time */
  formatTime(hhmmss) {
    const [h, m] = hhmmss.split(":");
    const d = new Date();
    d.setHours(Number(h), Number(m), 0);
    const locale = this.lang === "ar" ? "ar-EG" : "tr-TR";
    return d.toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit" });
  },

  dayName(weekdayIndex) {
    return this.t(`days.${weekdayIndex}`);
  },

  statusLabel(status) {
    return this.t(`status.${status}`);
  },
};
