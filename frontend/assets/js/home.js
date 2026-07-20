(async function () {
  await I18n.init();
  Layout.mount("home");
  Layout.initReveal();

  let departments = [];
  let doctorsCount = 0;
  let sections = [];

  async function loadData() {
    try {
      const [depts, doctors] = await Promise.all([Api.get("/departments"), Api.get("/doctors")]);
      departments = depts;
      doctorsCount = doctors.length;
    } catch (err) {
      Layout.toast(err.message, "error");
      return;
    }
    renderStats();
    renderDepartments();
    loadSections();
  }

  async function loadSections() {
    try {
      sections = await Api.get("/public/sections");
    } catch (_) {
      sections = []; // homepage still works if the endpoint is unavailable
    }
    renderSections();
  }

  function renderSections() {
    const host = document.getElementById("clinic-sections");
    if (!host) return;
    if (!sections.length) {
      host.innerHTML = "";
      return;
    }
    const lang = I18n.lang;
    host.innerHTML = sections
      .map((s, i) => {
        const title = esc((lang === "ar" ? s.title_ar : s.title_tr) || "");
        const body = esc((lang === "ar" ? s.body_ar : s.body_tr) || "");
        const imgs = s.images || [];
        const imagesHtml = imgs.length
          ? `<div class="grid grid-3" data-reveal-group style="margin-top:24px;">
              ${imgs
                .map((m) => {
                  const alt = esc((lang === "ar" ? m.alt_ar : m.alt_tr) || title || "");
                  return `<div class="card" style="overflow:hidden;">
                    <img src="${esc(m.url)}" alt="${alt}" loading="lazy"
                         style="width:100%; aspect-ratio:4/3; object-fit:cover; display:block; background:var(--color-bg-alt);">
                  </div>`;
                })
                .join("")}
            </div>`
          : "";
        // Alternate background to separate stacked sections visually.
        const bg = i % 2 === 1 ? ' style="background:var(--color-bg-alt);"' : "";
        return `
          <section${bg}>
            <div class="container">
              <div class="text-center" style="max-width:640px; margin:0 auto;" data-reveal>
                ${title ? `<h2>${title}</h2>` : ""}
                ${body ? `<p style="white-space:pre-line;">${body}</p>` : ""}
              </div>
              ${imagesHtml}
            </div>
          </section>`;
      })
      .join("");
    Layout.initReveal();
  }

  function renderStats() {
    document.getElementById("stat-departments").textContent = departments.length;
    document.getElementById("stat-doctors").textContent = doctorsCount;
  }

  function renderDepartments() {
    const grid = document.getElementById("departments-grid");
    if (!departments.length) {
      grid.innerHTML = `<p class="muted">${I18n.t("admin.noData")}</p>`;
      return;
    }
    grid.innerHTML = departments
      .map(
        (d) => `
      <a class="dept-card" href="booking.html?department=${d.id}">
        <div class="dept-icon">${Icons.svg(d.icon)}</div>
        <h3>${esc(I18n.lang === "ar" ? d.name_ar : d.name_tr)}</h3>
        <p>${esc((I18n.lang === "ar" ? d.description_ar : d.description_tr) || "")}</p>
      </a>`
      )
      .join("");
    Layout.initReveal();
  }

  document.addEventListener("clinic:langchange", () => {
    renderDepartments();
    renderSections();
  });

  loadData();
})();
