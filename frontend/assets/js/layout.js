/**
 * Shared site chrome + small UI utilities used across every page:
 *   Layout.mount()        -> builds navbar/footer into #site-header/#site-footer
 *   Layout.toast(msg,type)-> shows a floating toast notification
 *   Layout.confirmDialog() -> promise-based confirm modal (nicer than window.confirm)
 *   Layout.initReveal()   -> IntersectionObserver-based scroll reveal
 */
const Layout = {
  mount(activePage) {
    this._mountBanner();
    this._mountNavbar(activePage);
    this._mountFooter();
  },

  _mountBanner() {
    const user = Auth.getUser();
    if (!Auth.isLoggedIn() || !user || user.is_verified) return;
    const banner = document.createElement("div");
    banner.className = "verify-banner";
    banner.innerHTML = `<span data-i18n="verify.bannerText"></span> <a href="verify.html" data-i18n="verify.bannerLink"></a>`;
    document.body.insertBefore(banner, document.body.firstChild);
    I18n.translateDom(banner);
  },

  _mountNavbar(activePage) {
    const host = document.getElementById("site-header");
    if (!host) return;

    const loggedIn = Auth.isLoggedIn();
    const isAdmin = Auth.isAdmin();

    const links = [
      { href: "index.html", key: "nav.home", page: "home" },
      { href: "booking.html", key: "nav.book", page: "booking" },
    ];
    if (loggedIn) links.push({ href: "my-appointments.html", key: "nav.myAppointments", page: "my-appointments" });
    if (isAdmin) links.push({ href: "admin.html", key: "nav.admin", page: "admin" });

    const authLinks = loggedIn
      ? `<button class="nav-link" id="logout-btn" data-i18n="nav.logout">Logout</button>`
      : `<a class="nav-link" href="login.html" data-i18n="nav.login">Login</a>
         <a class="btn btn-primary btn-sm" href="register.html" data-i18n="nav.register">Register</a>`;

    host.innerHTML = `
      <nav class="navbar">
        <div class="navbar-inner">
          <a class="brand" href="index.html">
            <span class="brand-mark">${this._logoSvg()}</span>
            <span id="brand-name">${I18n.clinicName()}</span>
          </a>
          <button class="navbar-toggle btn-icon btn-ghost" id="nav-toggle" aria-label="menu">
            ${this._menuSvg()}
          </button>
          <div class="nav-links" id="nav-links">
            ${links.map((l) => `<a class="nav-link ${l.page === activePage ? "active" : ""}" href="${l.href}" data-i18n="${l.key}"></a>`).join("")}
            ${authLinks}
            <div class="lang-switch">
              <button data-lang="ar">AR</button>
              <button data-lang="tr">TR</button>
            </div>
          </div>
        </div>
      </nav>
    `;

    I18n.translateDom(host);
    
        // إضافة حدث استماع لأزرار تبديل اللغة
    host.querySelectorAll('.lang-switch button').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const lang = e.target.getAttribute('data-lang');
        if (lang) {
          // نفترض أن I18n لديها دالة setLang لتغيير اللغة
          I18n.setLang(lang); 
          // تحديث الصفحة لتعكس اللغة الجديدة
          I18n.translateDom(document.body);
        }
      });
    });

    document.getElementById("nav-toggle")?.addEventListener("click", () => {
      document.getElementById("nav-links").classList.toggle("open");
    });
    document.getElementById("logout-btn")?.addEventListener("click", () => Auth.logout());

    document.addEventListener("clinic:langchange", () => {
      document.getElementById("brand-name").textContent = I18n.clinicName();
    });
  },

  _mountFooter() {
    const host = document.getElementById("site-footer");
    if (!host) return;
    const year = new Date().getFullYear();
    host.innerHTML = `
      <footer class="site-footer">
        <div class="container footer-inner">
          <div class="row">
            <span class="brand-mark" style="width:30px;height:30px;">${this._logoSvg(16)}</span>
            <strong id="footer-brand">${I18n.clinicName()}</strong>
          </div>
          <small>&copy; ${year} <span id="footer-brand-2">${I18n.clinicName()}</span> — <span data-i18n="footer.rights"></span></small>
        </div>
      </footer>
    `;
    I18n.translateDom(host);
    document.addEventListener("clinic:langchange", () => {
      const a = document.getElementById("footer-brand");
      const b = document.getElementById("footer-brand-2");
      if (a) a.textContent = I18n.clinicName();
      if (b) b.textContent = I18n.clinicName();
    });
  },

  _logoSvg(size = 20) {
    return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 3v7M8.5 6.5h7" stroke="white" stroke-width="2" stroke-linecap="round"/>
      <path d="M6 11h12l-1 8.5a2 2 0 0 1-2 1.5H9a2 2 0 0 1-2-1.5L6 11Z" stroke="white" stroke-width="2" stroke-linejoin="round"/>
    </svg>`;
  },

  _menuSvg() {
    return `<svg width="22" height="22" viewBox="0 0 24 24" fill="none"><path d="M4 7h16M4 12h16M4 17h16" stroke="#14262B" stroke-width="2" stroke-linecap="round"/></svg>`;
  },

  // ------------------------------- Toasts --------------------------------
  toast(message, type = "info", duration = 3800) {
    let stack = document.querySelector(".toast-stack");
    if (!stack) {
      stack = document.createElement("div");
      stack.className = "toast-stack";
      document.body.appendChild(stack);
    }
    const el = document.createElement("div");
    el.className = `toast ${type}`;
    el.textContent = message;
    stack.appendChild(el);
    setTimeout(() => {
      el.style.transition = "opacity 300ms, transform 300ms";
      el.style.opacity = "0";
      el.style.transform = "translateY(8px)";
      setTimeout(() => el.remove(), 320);
    }, duration);
  },

  // ------------------------------ Confirm modal ---------------------------
  confirmDialog({ title, description, confirmLabel, cancelLabel, danger = false }) {
    return new Promise((resolve) => {
      const backdrop = document.createElement("div");
      backdrop.className = "modal-backdrop open";
      backdrop.innerHTML = `
        <div class="modal">
          <h3>${title}</h3>
          <p>${description}</p>
          <div class="row" style="justify-content:flex-end; margin-top:20px;">
            <button class="btn btn-ghost" data-action="cancel">${cancelLabel}</button>
            <button class="btn ${danger ? "btn-danger-ghost" : "btn-primary"}" data-action="confirm">${confirmLabel}</button>
          </div>
        </div>
      `;
      document.body.appendChild(backdrop);
      const cleanup = (result) => {
        backdrop.remove();
        resolve(result);
      };
      backdrop.querySelector('[data-action="cancel"]').addEventListener("click", () => cleanup(false));
      backdrop.querySelector('[data-action="confirm"]').addEventListener("click", () => cleanup(true));
      backdrop.addEventListener("click", (e) => { if (e.target === backdrop) cleanup(false); });
    });
  },

  // ---------------------------- Scroll reveal -----------------------------
  initReveal() {
    const targets = document.querySelectorAll("[data-reveal], [data-reveal-group]");
    if (!targets.length) return;
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("revealed");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.15 }
    );
    targets.forEach((t) => observer.observe(t));
  },
};
