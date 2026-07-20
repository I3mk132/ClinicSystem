(async function () {
  await I18n.init();
  Layout.mount("admin");
  if (!Auth.requireAdmin()) return;

  const modalHost = document.getElementById("modal-host");
  let cache = { departments: [], doctors: [] };

  // ============================================================
  // Tabs
  // ============================================================
  document.querySelectorAll(".admin-tab").forEach((btn) => {
    btn.addEventListener("click", () => switchTab(btn.dataset.tab));
  });
  function switchTab(tab) {
    document.querySelectorAll(".admin-tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
    document.querySelectorAll(".admin-panel").forEach((p) => p.classList.toggle("active", p.dataset.panel === tab));
    if (tab === "overview") loadOverview();
    if (tab === "appointments") loadAppointments();
    if (tab === "doctors") loadDoctors();
    if (tab === "departments") loadDepartments();
    if (tab === "schedules") loadScheduleDoctorOptions();
    if (tab === "theme") loadTheme();
    if (tab === "integrations") loadApiKeys();
  }

  // ============================================================
  // Generic form modal
  // ============================================================
  function openFormModal({ title, fields, initialValues = {}, onSubmit }) {
    const backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop open";
    backdrop.innerHTML = `
      <div class="modal">
        <h3>${esc(title)}</h3>
        <div class="form-error" id="modal-error"></div>
        <form id="modal-form">
          ${fields
            .map((f) => {
              const value = initialValues[f.name] ?? "";
              if (f.type === "select") {
                return `<div class="field"><label>${esc(f.label)}</label>
                  <select name="${f.name}" ${f.required ? "required" : ""}>
                    ${f.options.map((o) => `<option value="${esc(o.value)}" ${String(o.value) === String(value) ? "selected" : ""}>${esc(o.label)}</option>`).join("")}
                  </select></div>`;
              }
              if (f.type === "textarea") {
                return `<div class="field"><label>${esc(f.label)}</label><textarea name="${f.name}" ${f.required ? "required" : ""}>${esc(value)}</textarea></div>`;
              }
              if (f.type === "checkbox") {
                return `<div class="field row"><input type="checkbox" name="${f.name}" style="width:auto;" ${value ? "checked" : ""}><label style="margin:0;">${esc(f.label)}</label></div>`;
              }
              return `<div class="field"><label>${esc(f.label)}</label><input type="${f.type || "text"}" name="${f.name}" value="${esc(value)}" ${f.required ? "required" : ""} ${f.min !== undefined ? `min="${f.min}"` : ""} ${f.step ? `step="${f.step}"` : ""}></div>`;
            })
            .join("")}
          <div class="row" style="justify-content:flex-end; margin-top:8px;">
            <button type="button" class="btn btn-ghost" data-action="cancel">${I18n.t("common.cancel")}</button>
            <button type="submit" class="btn btn-primary">${I18n.t("common.save")}</button>
          </div>
        </form>
      </div>`;
    modalHost.appendChild(backdrop);

    const close = () => backdrop.remove();
    backdrop.querySelector('[data-action="cancel"]').addEventListener("click", close);
    backdrop.addEventListener("click", (e) => { if (e.target === backdrop) close(); });

    backdrop.querySelector("#modal-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const errorBox = backdrop.querySelector("#modal-error");
      errorBox.classList.remove("visible");
      const formData = new FormData(e.target);
      const values = {};
      fields.forEach((f) => {
        if (f.type === "checkbox") {
          values[f.name] = formData.get(f.name) === "on";
        } else if (f.type === "number") {
          values[f.name] = formData.get(f.name) ? Number(formData.get(f.name)) : null;
        } else {
          values[f.name] = formData.get(f.name)?.toString().trim() || null;
        }
      });
      try {
        await onSubmit(values);
        close();
      } catch (err) {
        errorBox.textContent = err.message;
        errorBox.classList.add("visible");
      }
    });
  }

  async function refreshCache() {
    [cache.departments, cache.doctors] = await Promise.all([
      Api.get("/departments", { params: { include_inactive: true } }),
      Api.get("/doctors", { params: { include_inactive: true } }),
    ]);
  }

  function deptLabel(d) {
    return I18n.lang === "ar" ? d.name_ar : d.name_tr;
  }

  // ============================================================
  // Overview
  // ============================================================
  async function loadOverview() {
    const host = document.getElementById("overview-stats");
    host.innerHTML = `<div class="skeleton" style="height:100px;"></div>`.repeat(4);
    let appointments;
    try {
      appointments = await Api.get("/appointments", { auth: true });
    } catch (err) {
      Layout.toast(err.message, "error");
      return;
    }
    const today = new Date().toISOString().split("T")[0];
    const in7 = new Date(Date.now() + 7 * 86400000).toISOString().split("T")[0];

    const todayCount = appointments.filter((a) => a.appointment_date === today && a.status !== "cancelled").length;
    const upcomingCount = appointments.filter((a) => a.appointment_date >= today && a.appointment_date <= in7 && a.status !== "cancelled").length;
    const cancelledCount = appointments.filter((a) => a.status === "cancelled").length;

    const stats = [
      [appointments.length, "admin.overviewTotal"],
      [todayCount, "admin.overviewToday"],
      [upcomingCount, "admin.overviewUpcoming"],
      [cancelledCount, "admin.overviewCancelled"],
    ];
    host.innerHTML = stats
      .map(
        ([value, key]) => `
      <div class="card card-pad">
        <div class="mono" style="font-size:2rem; font-weight:800; color:var(--color-primary-dark);">${value}</div>
        <p style="margin:4px 0 0;" data-i18n="${key}"></p>
      </div>`
      )
      .join("");
    I18n.translateDom(host);
  }

  // ============================================================
  // Appointments
  // ============================================================
  async function loadAppointments() {
    await ensureFilterDoctorOptions();
    const tbody = document.getElementById("appointments-tbody");
    tbody.innerHTML = `<tr><td colspan="6"><div class="spinner"></div></td></tr>`;

    const params = {
      status: document.getElementById("filter-status").value || undefined,
      doctor_id: document.getElementById("filter-doctor").value || undefined,
      date_from: document.getElementById("filter-date-from").value || undefined,
      date_to: document.getElementById("filter-date-to").value || undefined,
    };

    let appointments;
    try {
      appointments = await Api.get("/appointments", { auth: true, params });
    } catch (err) {
      Layout.toast(err.message, "error");
      return;
    }

    if (!appointments.length) {
      tbody.innerHTML = `<tr><td colspan="6" class="muted">${I18n.t("admin.noData")}</td></tr>`;
      return;
    }

    tbody.innerHTML = appointments
      .map(
        (a) => `
      <tr>
        <td>${esc(a.patient.full_name)}</td>
        <td>${esc(a.doctor.full_name)}</td>
        <td>${esc(deptLabel(a.department))}</td>
        <td class="mono">${a.appointment_date} · ${a.start_time.slice(0, 5)}</td>
        <td><span class="badge badge-${a.status}">${I18n.statusLabel(a.status)}</span></td>
        <td>
          <select data-status-select="${a.id}" class="btn-sm" style="width:auto; padding:6px 10px;">
            ${["confirmed", "completed", "cancelled", "no_show"].map((s) => `<option value="${s}" ${s === a.status ? "selected" : ""}>${I18n.statusLabel(s)}</option>`).join("")}
          </select>
        </td>
      </tr>`
      )
      .join("");

    tbody.querySelectorAll("[data-status-select]").forEach((select) => {
      select.addEventListener("change", async () => {
        try {
          await Api.patch(`/appointments/${select.dataset.statusSelect}/status`, { status: select.value }, { auth: true });
          Layout.toast(I18n.t("admin.savedSuccess"), "success");
          loadAppointments();
        } catch (err) {
          Layout.toast(err.message, "error");
        }
      });
    });
  }

  async function ensureFilterDoctorOptions() {
    if (!cache.doctors.length) await refreshCache();
    const select = document.getElementById("filter-doctor");
    if (select.options.length <= 1) {
      cache.doctors.forEach((d) => select.insertAdjacentHTML("beforeend", `<option value="${d.id}">${esc(d.full_name)}</option>`));
    }
  }
  ["filter-status", "filter-doctor", "filter-date-from", "filter-date-to"].forEach((id) => {
    document.getElementById(id).addEventListener("change", loadAppointments);
  });

  // ============================================================
  // Departments
  // ============================================================
  async function loadDepartments() {
    await refreshCache();
    const tbody = document.getElementById("departments-tbody");
    if (!cache.departments.length) {
      tbody.innerHTML = `<tr><td colspan="4" class="muted">${I18n.t("admin.noData")}</td></tr>`;
      return;
    }
    tbody.innerHTML = cache.departments
      .map(
        (d) => `
      <tr>
        <td>${esc(d.name_ar)}</td>
        <td>${esc(d.name_tr)}</td>
        <td>${d.is_active ? I18n.t("common.active") : I18n.t("common.inactive")}</td>
        <td class="row">
          <button class="btn btn-ghost btn-sm" data-edit-dept="${d.id}">${I18n.t("common.edit")}</button>
          <button class="btn btn-danger-ghost btn-sm" data-del-dept="${d.id}">${I18n.t("common.delete")}</button>
        </td>
      </tr>`
      )
      .join("");

    tbody.querySelectorAll("[data-edit-dept]").forEach((btn) => btn.addEventListener("click", () => departmentModal(Number(btn.dataset.editDept))));
    tbody.querySelectorAll("[data-del-dept]").forEach((btn) => btn.addEventListener("click", () => deleteDepartment(Number(btn.dataset.delDept))));
  }

  function departmentFields() {
    return [
      { name: "name_ar", label: I18n.t("admin.nameAr"), required: true },
      { name: "name_tr", label: I18n.t("admin.nameTr"), required: true },
      { name: "description_ar", label: I18n.t("admin.descriptionAr"), type: "textarea" },
      { name: "description_tr", label: I18n.t("admin.descriptionTr"), type: "textarea" },
      { name: "icon", label: "Icon", type: "select", options: Icons.options().map((k) => ({ value: k, label: k })) },
      { name: "is_active", label: I18n.t("common.active"), type: "checkbox" },
    ];
  }

  function departmentModal(id) {
    const existing = id ? cache.departments.find((d) => d.id === id) : null;
    openFormModal({
      title: I18n.t(existing ? "admin.editDepartment" : "admin.addDepartment"),
      fields: departmentFields(),
      initialValues: existing || { is_active: true, icon: "stethoscope" },
      onSubmit: async (values) => {
        if (existing) {
          await Api.patch(`/departments/${existing.id}`, values, { auth: true });
        } else {
          await Api.post("/departments", values, { auth: true });
        }
        Layout.toast(I18n.t("admin.savedSuccess"), "success");
        loadDepartments();
      },
    });
  }

  async function deleteDepartment(id) {
    const ok = await Layout.confirmDialog({
      title: I18n.t("common.delete"),
      description: I18n.t("admin.confirmDeleteGeneric"),
      confirmLabel: I18n.t("common.delete"),
      cancelLabel: I18n.t("common.cancel"),
      danger: true,
    });
    if (!ok) return;
    try {
      await Api.delete(`/departments/${id}`, { auth: true });
      Layout.toast(I18n.t("admin.deletedSuccess"), "success");
      loadDepartments();
    } catch (err) {
      Layout.toast(err.message, "error");
    }
  }

  document.getElementById("add-department-btn").addEventListener("click", () => departmentModal(null));

  // ============================================================
  // Doctors
  // ============================================================
  async function loadDoctors() {
    await refreshCache();
    const tbody = document.getElementById("doctors-tbody");
    if (!cache.doctors.length) {
      tbody.innerHTML = `<tr><td colspan="4" class="muted">${I18n.t("admin.noData")}</td></tr>`;
      return;
    }
    tbody.innerHTML = cache.doctors
      .map(
        (d) => `
      <tr>
        <td>${esc(d.full_name)}</td>
        <td>${d.department ? esc(deptLabel(d.department)) : "—"}</td>
        <td>${d.is_active ? I18n.t("common.active") : I18n.t("common.inactive")}</td>
        <td class="row">
          <button class="btn btn-ghost btn-sm" data-edit-doc="${d.id}">${I18n.t("common.edit")}</button>
          <button class="btn btn-danger-ghost btn-sm" data-del-doc="${d.id}">${I18n.t("common.delete")}</button>
        </td>
      </tr>`
      )
      .join("");

    tbody.querySelectorAll("[data-edit-doc]").forEach((btn) => btn.addEventListener("click", () => doctorModal(Number(btn.dataset.editDoc))));
    tbody.querySelectorAll("[data-del-doc]").forEach((btn) => btn.addEventListener("click", () => deleteDoctor(Number(btn.dataset.delDoc))));
  }

  function doctorFields() {
    return [
      { name: "full_name", label: I18n.t("auth.fullName"), required: true },
      { name: "department_id", label: I18n.t("admin.department"), type: "select", required: true, options: cache.departments.map((d) => ({ value: d.id, label: deptLabel(d) })) },
      { name: "title_ar", label: I18n.t("admin.titleAr") },
      { name: "title_tr", label: I18n.t("admin.titleTr") },
      { name: "bio_ar", label: I18n.t("admin.bioAr"), type: "textarea" },
      { name: "bio_tr", label: I18n.t("admin.bioTr"), type: "textarea" },
      { name: "photo_url", label: "Photo URL" },
      { name: "is_active", label: I18n.t("common.active"), type: "checkbox" },
    ];
  }

  function doctorModal(id) {
    const existing = id ? cache.doctors.find((d) => d.id === id) : null;
    const initial = existing ? { ...existing, department_id: existing.department_id } : { is_active: true, department_id: cache.departments[0]?.id };
    openFormModal({
      title: I18n.t(existing ? "admin.editDoctor" : "admin.addDoctor"),
      fields: doctorFields(),
      initialValues: initial,
      onSubmit: async (values) => {
        values.department_id = Number(values.department_id);
        if (existing) {
          await Api.patch(`/doctors/${existing.id}`, values, { auth: true });
        } else {
          await Api.post("/doctors", values, { auth: true });
        }
        Layout.toast(I18n.t("admin.savedSuccess"), "success");
        loadDoctors();
      },
    });
  }

  async function deleteDoctor(id) {
    const ok = await Layout.confirmDialog({
      title: I18n.t("common.delete"),
      description: I18n.t("admin.confirmDeleteGeneric"),
      confirmLabel: I18n.t("common.delete"),
      cancelLabel: I18n.t("common.cancel"),
      danger: true,
    });
    if (!ok) return;
    try {
      await Api.delete(`/doctors/${id}`, { auth: true });
      Layout.toast(I18n.t("admin.deletedSuccess"), "success");
      loadDoctors();
    } catch (err) {
      Layout.toast(err.message, "error");
    }
  }

  document.getElementById("add-doctor-btn").addEventListener("click", async () => {
    if (!cache.departments.length) await refreshCache();
    doctorModal(null);
  });

  // ============================================================
  // Schedules (weekly availability + time off)
  // ============================================================
  async function loadScheduleDoctorOptions() {
    if (!cache.doctors.length) await refreshCache();
    const select = document.getElementById("schedule-doctor-select");
    select.innerHTML = `<option value="">—</option>` + cache.doctors.map((d) => `<option value="${d.id}">${esc(d.full_name)}</option>`).join("");
  }

  document.getElementById("schedule-doctor-select").addEventListener("change", (e) => {
    const id = e.target.value;
    document.getElementById("schedule-content").hidden = !id;
    document.getElementById("schedule-placeholder").hidden = !!id;
    if (id) {
      loadAvailabilities(Number(id));
      loadTimeOff(Number(id));
    }
  });

  async function loadAvailabilities(doctorId) {
    const tbody = document.getElementById("availabilities-tbody");
    tbody.innerHTML = `<tr><td colspan="5"><div class="spinner"></div></td></tr>`;
    const rules = await Api.get("/availabilities", { params: { doctor_id: doctorId } });
    if (!rules.length) {
      tbody.innerHTML = `<tr><td colspan="5" class="muted">${I18n.t("admin.noData")}</td></tr>`;
      return;
    }
    tbody.innerHTML = rules
      .map(
        (r) => `
      <tr>
        <td>${I18n.dayName(r.weekday)}</td>
        <td class="mono">${r.start_time.slice(0, 5)}</td>
        <td class="mono">${r.end_time.slice(0, 5)}</td>
        <td class="mono">${r.slot_duration_minutes}</td>
        <td><button class="btn btn-danger-ghost btn-sm" data-del-avail="${r.id}">${I18n.t("common.delete")}</button></td>
      </tr>`
      )
      .join("");
    tbody.querySelectorAll("[data-del-avail]").forEach((btn) =>
      btn.addEventListener("click", async () => {
        await Api.delete(`/availabilities/${btn.dataset.delAvail}`, { auth: true });
        Layout.toast(I18n.t("admin.deletedSuccess"), "success");
        loadAvailabilities(doctorId);
      })
    );
  }

  function weekdayOptions() {
    return [0, 1, 2, 3, 4, 5, 6].map((n) => ({ value: n, label: I18n.dayName(n) }));
  }

  document.getElementById("add-availability-btn").addEventListener("click", () => {
    const doctorId = Number(document.getElementById("schedule-doctor-select").value);
    openFormModal({
      title: I18n.t("admin.addAvailability"),
      fields: [
        { name: "weekday", label: I18n.t("admin.weekday"), type: "select", options: weekdayOptions(), required: true },
        { name: "start_time", label: I18n.t("admin.startTime"), type: "time", required: true },
        { name: "end_time", label: I18n.t("admin.endTime"), type: "time", required: true },
        { name: "slot_duration_minutes", label: I18n.t("admin.slotDuration"), type: "number", min: 5, required: true },
      ],
      initialValues: { weekday: 0, start_time: "09:00", end_time: "13:00", slot_duration_minutes: 30 },
      onSubmit: async (values) => {
        await Api.post(
          "/availabilities",
          {
            doctor_id: doctorId,
            weekday: Number(values.weekday),
            start_time: values.start_time,
            end_time: values.end_time,
            slot_duration_minutes: Number(values.slot_duration_minutes),
          },
          { auth: true }
        );
        Layout.toast(I18n.t("admin.savedSuccess"), "success");
        loadAvailabilities(doctorId);
      },
    });
  });

  async function loadTimeOff(doctorId) {
    const tbody = document.getElementById("timeoff-tbody");
    tbody.innerHTML = `<tr><td colspan="3"><div class="spinner"></div></td></tr>`;
    const items = await Api.get("/time-off", { params: { doctor_id: doctorId } });
    if (!items.length) {
      tbody.innerHTML = `<tr><td colspan="3" class="muted">${I18n.t("admin.noData")}</td></tr>`;
      return;
    }
    tbody.innerHTML = items
      .map(
        (t) => `
      <tr>
        <td class="mono">${t.date}</td>
        <td>${esc(t.reason) || "—"}</td>
        <td><button class="btn btn-danger-ghost btn-sm" data-del-timeoff="${t.id}">${I18n.t("common.delete")}</button></td>
      </tr>`
      )
      .join("");
    tbody.querySelectorAll("[data-del-timeoff]").forEach((btn) =>
      btn.addEventListener("click", async () => {
        await Api.delete(`/time-off/${btn.dataset.delTimeoff}`, { auth: true });
        Layout.toast(I18n.t("admin.deletedSuccess"), "success");
        loadTimeOff(doctorId);
      })
    );
  }

  document.getElementById("add-timeoff-btn").addEventListener("click", () => {
    const doctorId = Number(document.getElementById("schedule-doctor-select").value);
    openFormModal({
      title: I18n.t("admin.addTimeOff"),
      fields: [
        { name: "date", label: I18n.t("admin.date"), type: "date", required: true },
        { name: "reason", label: I18n.t("admin.reason") },
      ],
      initialValues: {},
      onSubmit: async (values) => {
        await Api.post("/time-off", { doctor_id: doctorId, date: values.date, reason: values.reason }, { auth: true });
        Layout.toast(I18n.t("admin.savedSuccess"), "success");
        loadTimeOff(doctorId);
      },
    });
  });

  // ============================================================
  // Integrations (API keys)
  // ============================================================
  document.getElementById("api-docs-link").href = Api.baseUrl.replace(/\/api\/v1\/?$/, "/docs");

  async function loadApiKeys() {
    const tbody = document.getElementById("api-keys-tbody");
    tbody.innerHTML = `<tr><td colspan="5"><div class="spinner"></div></td></tr>`;
    let keys;
    try {
      keys = await Api.get("/api-keys", { auth: true });
    } catch (err) {
      Layout.toast(err.message, "error");
      return;
    }
    if (!keys.length) {
      tbody.innerHTML = `<tr><td colspan="5" class="muted">${I18n.t("admin.noData")}</td></tr>`;
      return;
    }
    tbody.innerHTML = keys
      .map(
        (k) => `
      <tr>
        <td>${esc(k.name)}</td>
        <td class="mono">${esc(k.key_prefix)}…</td>
        <td>${k.is_active ? I18n.t("common.active") : I18n.t("common.inactive")}</td>
        <td class="muted" style="font-size:0.8rem;">${k.last_used_at ? new Date(k.last_used_at).toLocaleString(I18n.lang === "ar" ? "ar-EG" : "tr-TR") : I18n.t("admin.neverUsed")}</td>
        <td>${k.is_active ? `<button class="btn btn-danger-ghost btn-sm" data-revoke-key="${k.id}">${I18n.t("admin.revokeButton")}</button>` : ""}</td>
      </tr>`
      )
      .join("");

    tbody.querySelectorAll("[data-revoke-key]").forEach((btn) =>
      btn.addEventListener("click", async () => {
        const ok = await Layout.confirmDialog({
          title: I18n.t("admin.revokeButton"),
          description: I18n.t("admin.revokeConfirmDesc"),
          confirmLabel: I18n.t("admin.revokeButton"),
          cancelLabel: I18n.t("common.cancel"),
          danger: true,
        });
        if (!ok) return;
        try {
          await Api.patch(`/api-keys/${btn.dataset.revokeKey}/revoke`, {}, { auth: true });
          Layout.toast(I18n.t("admin.keyRevoked"), "success");
          loadApiKeys();
        } catch (err) {
          Layout.toast(err.message, "error");
        }
      })
    );
  }

  function showCreatedKeyModal(keyData) {
    const backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop open";
    backdrop.innerHTML = `
      <div class="modal">
        <h3>${I18n.t("admin.keyCreatedTitle")}</h3>
        <div class="form-error visible" style="background:var(--color-accent-light); color:var(--color-accent-dark);">${I18n.t("admin.keyCreatedWarning")}</div>
        <div class="card card-pad mono" style="word-break:break-all; font-size:0.85rem; background:var(--color-bg-alt);">${keyData.api_key}</div>
        <div class="row" style="justify-content:flex-end; margin-top:16px;">
          <button class="btn btn-ghost" id="copy-key-btn">${I18n.t("common.copy")}</button>
          <button class="btn btn-primary" id="close-key-modal">${I18n.t("common.close")}</button>
        </div>
      </div>`;
    modalHost.appendChild(backdrop);
    backdrop.querySelector("#copy-key-btn").addEventListener("click", () => {
      navigator.clipboard.writeText(keyData.api_key);
      Layout.toast(I18n.t("common.copied"), "success");
    });
    const close = () => {
      backdrop.remove();
      loadApiKeys();
    };
    backdrop.querySelector("#close-key-modal").addEventListener("click", close);
    backdrop.addEventListener("click", (e) => { if (e.target === backdrop) close(); });
  }

  document.getElementById("add-api-key-btn").addEventListener("click", () => {
    openFormModal({
      title: I18n.t("admin.addApiKey"),
      fields: [{ name: "name", label: I18n.t("admin.keyName"), required: true }],
      initialValues: {},
      onSubmit: async (values) => {
        const created = await Api.post("/api-keys", values, { auth: true });
        showCreatedKeyModal(created);
      },
    });
  });

  // ============================================================
  // Theme (per-clinic branding)
  // ============================================================
  async function loadTheme() {
    const host = document.getElementById("theme-editor");
    host.innerHTML = `<div class="spinner"></div>`;
    let data;
    try {
      data = await Api.get("/admin/theme", { auth: true });
    } catch (err) {
      Layout.toast(err.message, "error");
      return;
    }
    renderThemeEditor(host, data);
  }

  function renderThemeEditor(host, data) {
    const eff = data.effective || {};
    const ov = data.overrides || {};
    const colors = eff.colors || {};
    const ovGet = (path) => path.split(".").reduce((o, k) => (o == null ? undefined : o[k]), ov);

    const colorRow = (key, labelKey) => `
      <div class="field">
        <label>${I18n.t("admin." + labelKey)}</label>
        <div class="row" style="gap:10px; align-items:center;">
          <input type="color" data-theme-color="${key}" value="${esc(colors[key] || "#000000")}" style="width:52px; height:40px; padding:2px;">
          <span class="mono muted" data-color-hex="${key}">${esc(colors[key] || "")}</span>
        </div>
      </div>`;

    const bilingual = (labelKey, arVal, trVal, arAttr, trAttr) => `
      <div class="field">
        <label>${I18n.t("admin." + labelKey)}</label>
        <div class="grid grid-2" style="gap:10px;">
          <input type="text" ${arAttr} placeholder="${I18n.t("admin.themeArabic")}" value="${esc(arVal || "")}">
          <input type="text" ${trAttr} placeholder="${I18n.t("admin.themeTurkish")}" value="${esc(trVal || "")}">
        </div>
      </div>`;

    host.innerHTML = `
      <div class="card card-pad" style="margin-bottom:18px;">
        <p class="muted" style="margin:0;">
          ${I18n.t("admin.themeCurrentPreset")}: <strong>${esc(eff.label || eff.preset || "")}</strong>
        </p>
      </div>

      <form id="theme-form">
        <div class="card card-pad" style="margin-bottom:18px;">
          <h4 style="margin-top:0;" data-i18n="admin.themeColors"></h4>
          <div class="grid grid-3">
            ${colorRow("primary", "themePrimary")}
            ${colorRow("secondary", "themeSecondary")}
            ${colorRow("accent", "themeAccent")}
          </div>
          <div class="field" style="margin-top:8px;">
            <label data-i18n="admin.themeLogoUrl"></label>
            <input type="text" data-theme-field="logo_url" value="${esc(ov.logo_url || "")}" placeholder="https://…/logo.png">
          </div>
        </div>

        <div class="card card-pad" style="margin-bottom:18px;">
          <h4 style="margin-top:0;" data-i18n="admin.themeTextsTitle"></h4>
          ${bilingual("themeDisplayName", ovGet("name.ar"), ovGet("name.tr"), 'data-theme-field="name.ar"', 'data-theme-field="name.tr"')}
          ${bilingual("themeHeroTitle", ovGet("hero.title.ar"), ovGet("hero.title.tr"), 'data-theme-field="hero.title.ar"', 'data-theme-field="hero.title.tr"')}
          ${bilingual("themeHeroSubtitle", ovGet("hero.subtitle.ar"), ovGet("hero.subtitle.tr"), 'data-theme-field="hero.subtitle.ar"', 'data-theme-field="hero.subtitle.tr"')}
          <div class="field">
            <label data-i18n="admin.themeContactPhone"></label>
            <input type="text" data-theme-field="contact.phone" value="${esc(ovGet("contact.phone") || "")}">
          </div>
          ${bilingual("themeContactAddress", ovGet("contact.address.ar"), ovGet("contact.address.tr"), 'data-theme-field="contact.address.ar"', 'data-theme-field="contact.address.tr"')}
          ${bilingual("themeFooterText", ovGet("footer.ar"), ovGet("footer.tr"), 'data-theme-field="footer.ar"', 'data-theme-field="footer.tr"')}
        </div>

        <div class="row" style="justify-content:flex-end; gap:10px;">
          <button type="button" class="btn btn-danger-ghost" id="theme-reset-btn" data-i18n="admin.themeReset"></button>
          <button type="submit" class="btn btn-primary">${I18n.t("common.save")}</button>
        </div>
      </form>`;
    I18n.translateDom(host);

    // Track loaded colours so we only persist the ones the admin actually
    // changes (untouched colours stay driven by the preset).
    const initialColors = { primary: colors.primary, secondary: colors.secondary, accent: colors.accent };

    host.querySelectorAll("[data-theme-color]").forEach((input) => {
      input.addEventListener("input", () => {
        const key = input.dataset.themeColor;
        // Live preview: recolour the whole admin UI as you pick.
        document.documentElement.style.setProperty(`--color-${key}`, input.value);
        const hex = host.querySelector(`[data-color-hex="${key}"]`);
        if (hex) hex.textContent = input.value;
      });
    });

    host.querySelector("#theme-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const payload = buildThemePayload(host, ov, initialColors);
      await saveTheme(host, payload);
    });

    host.querySelector("#theme-reset-btn").addEventListener("click", async () => {
      const ok = await Layout.confirmDialog({
        title: I18n.t("admin.themeReset"),
        description: I18n.t("admin.confirmDeleteGeneric"),
        confirmLabel: I18n.t("admin.themeReset"),
        cancelLabel: I18n.t("common.cancel"),
        danger: true,
      });
      if (!ok) return;
      await saveTheme(host, {});
    });
  }

  function buildThemePayload(host, ov, initialColors) {
    const payload = {};

    // Colours: keep an existing override, or add one only when changed.
    const colors = {};
    host.querySelectorAll("[data-theme-color]").forEach((input) => {
      const key = input.dataset.themeColor;
      const changed = (initialColors[key] || "").toLowerCase() !== input.value.toLowerCase();
      const wasOverride = ov.colors && Object.prototype.hasOwnProperty.call(ov.colors, key);
      if (changed || wasOverride) colors[key] = input.value;
    });
    if (Object.keys(colors).length) payload.colors = colors;

    // Text/URL fields keyed by dotted path -> nested object; drop empties.
    host.querySelectorAll("[data-theme-field]").forEach((input) => {
      const val = input.value.trim();
      if (!val) return;
      const parts = input.dataset.themeField.split(".");
      let node = payload;
      parts.forEach((p, i) => {
        if (i === parts.length - 1) node[p] = val;
        else node = node[p] = node[p] || {};
      });
    });
    return payload;
  }

  async function saveTheme(host, payload) {
    try {
      const data = await Api.put("/admin/theme", payload, { auth: true });
      Layout.toast(I18n.t("admin.savedSuccess"), "success");
      // Apply + cache so the change shows across the site immediately.
      if (window.Theme) {
        Theme.apply(data.effective);
        try { localStorage.setItem(Theme._key(), JSON.stringify(data.effective)); } catch (_) {}
      }
      renderThemeEditor(host, data);
    } catch (err) {
      Layout.toast(err.message, "error");
    }
  }

  // ============================================================
  // Boot
  // ============================================================
  await refreshCache();
  loadOverview();
})();
