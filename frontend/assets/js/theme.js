/**
 * Per-clinic theming (Session 3).
 *
 * Fetches the clinic's effective theme from GET /api/v1/public/theme (resolved
 * by the X-Clinic header) and applies it as CSS custom properties on :root, so
 * the same deployed frontend paints a different brand for every clinic.
 *
 * Anti-FOUC: a cached copy (localStorage, keyed by clinic slug) is applied
 * synchronously the instant this script runs, then a fresh copy is fetched in
 * the background and re-applied. If the backend is unreachable, whatever is
 * cached (or the config.js defaults) stays in place - theming never blocks a page.
 *
 * The theme also feeds the clinic display name + logo back into CLINIC_CONFIG so
 * I18n.clinicName() and Layout pick them up, and drives any [data-theme-text]
 * nodes (hero title/subtitle, footer, contact) per active language.
 */
const Theme = {
  STORAGE_PREFIX: "clinic_theme:",
  current: null,

  _key() {
    return this.STORAGE_PREFIX + (window.CLINIC_CONFIG.CLINIC_SLUG || "default");
  },

  /** Apply a theme object to the page. Idempotent; safe to call repeatedly. */
  apply(theme) {
    if (!theme || typeof theme !== "object") return;
    this.current = theme;
    const root = document.documentElement;

    Object.entries(theme.colors || {}).forEach(([k, v]) => {
      if (typeof v === "string") root.style.setProperty(`--color-${k}`, v);
    });
    Object.entries(theme.radius || {}).forEach(([k, v]) => {
      if (typeof v === "string") root.style.setProperty(`--radius-${k}`, v);
    });

    const fonts = theme.fonts || {};
    if (fonts.latin) root.style.setProperty("--font-latin", fonts.latin);
    if (fonts.arabic) root.style.setProperty("--font-arabic", fonts.arabic);
    if (fonts.mono) root.style.setProperty("--font-mono", fonts.mono);
    this._ensureFontLink(fonts.import_url);

    // Feed name + logo into config so existing name/logo consumers use them.
    if (theme.name && (theme.name.ar || theme.name.tr)) {
      window.CLINIC_CONFIG.CLINIC_NAME = {
        ar: theme.name.ar || window.CLINIC_CONFIG.CLINIC_NAME.ar,
        tr: theme.name.tr || window.CLINIC_CONFIG.CLINIC_NAME.tr,
      };
    }
    if (theme.logo_url) window.CLINIC_CONFIG.CLINIC_LOGO_URL = theme.logo_url;

    this.applyTexts();
    document.dispatchEvent(new CustomEvent("clinic:themechange", { detail: theme }));
  },

  /**
   * Set the text of every [data-theme-text="path"] node from the current theme
   * in the active language (e.g. "hero.title", "hero.subtitle", "footer",
   * "contact.phone", "contact.address"). Uses textContent -> no XSS risk.
   * If a value is empty, the node's existing (i18n default) text is left as-is.
   */
  applyTexts() {
    const t = this.current;
    if (!t) return;
    const lang = (window.I18n && I18n.lang) || document.documentElement.getAttribute("lang") || "ar";
    document.querySelectorAll("[data-theme-text]").forEach((el) => {
      const val = this._resolve(t, el.getAttribute("data-theme-text"), lang);
      if (val) el.textContent = val;
    });
    const brand = document.getElementById("brand-name");
    if (brand && window.I18n) brand.textContent = I18n.clinicName();
  },

  _resolve(theme, path, lang) {
    const node = path.split(".").reduce((o, k) => (o == null ? o : o[k]), theme);
    if (node == null) return "";
    if (typeof node === "string") return node;
    if (typeof node === "object") return node[lang] || node.ar || node.tr || "";
    return "";
  },

  _ensureFontLink(url) {
    if (!url) return;
    let link = document.getElementById("theme-font-link");
    if (!link) {
      link = document.createElement("link");
      link.id = "theme-font-link";
      link.rel = "stylesheet";
      document.head.appendChild(link);
    }
    if (link.getAttribute("href") !== url) link.setAttribute("href", url);
  },

  /** Apply cached theme instantly, then refresh from the backend. */
  async boot() {
    try {
      const cached = localStorage.getItem(this._key());
      if (cached) this.apply(JSON.parse(cached));
    } catch (_) { /* corrupt cache - ignore */ }
    try {
      const theme = await Api.get("/public/theme");
      localStorage.setItem(this._key(), JSON.stringify(theme));
      this.apply(theme);
    } catch (_) { /* backend down - keep cached / config defaults */ }
  },
};

// Re-apply themed texts when the language switches.
document.addEventListener("clinic:langchange", () => Theme.applyTexts());

// Kick off immediately so colours paint before the page renders.
Theme.boot();
