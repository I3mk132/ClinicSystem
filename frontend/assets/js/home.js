(async function () {
  await I18n.init();
  Layout.mount("home");
  Layout.initReveal();

  let departments = [];
  let doctorsCount = 0;

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

  document.addEventListener("clinic:langchange", renderDepartments);

  loadData();
})();
