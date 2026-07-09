(async function () {
  await I18n.init();
  Layout.mount("booking");

  const DRAFT_KEY = "clinic_booking_draft";

  const state = {
    department: null,
    doctor: null,
    date: null,
    slot: null, // { start_time, end_time }
  };

  const panels = document.querySelectorAll("[data-panel]");
  const steps = document.querySelectorAll(".wizard-step");

  function goto(stepNumber) {
    panels.forEach((p) => (p.hidden = Number(p.dataset.panel) !== stepNumber));
    steps.forEach((s) => {
      const n = Number(s.dataset.step);
      s.classList.toggle("active", n === stepNumber);
      s.classList.toggle("done", n < stepNumber);
    });
    window.scrollTo({ top: 220, behavior: "smooth" });
  }

  // ------------------------------ Step 1: Departments ------------------------------
  async function loadDepartments() {
    const grid = document.getElementById("department-grid");
    grid.innerHTML = `<div class="skeleton" style="height:140px;"></div><div class="skeleton" style="height:140px;"></div><div class="skeleton" style="height:140px;"></div>`;
    let departments;
    try {
      departments = await Api.get("/departments");
    } catch (err) {
      Layout.toast(err.message, "error");
      return;
    }
    grid.innerHTML = departments
      .map(
        (d) => `
      <button type="button" class="dept-card" data-id="${d.id}">
        <div class="dept-icon">${Icons.svg(d.icon)}</div>
        <h3>${I18n.lang === "ar" ? d.name_ar : d.name_tr}</h3>
        <p>${(I18n.lang === "ar" ? d.description_ar : d.description_tr) || ""}</p>
      </button>`
      )
      .join("");

    grid.querySelectorAll(".dept-card").forEach((card) => {
      card.addEventListener("click", () => {
        const dept = departments.find((d) => d.id === Number(card.dataset.id));
        selectDepartment(dept);
      });
    });

    return departments;
  }

  function selectDepartment(dept) {
    state.department = dept;
    state.doctor = null;
    state.slot = null;
    document.querySelectorAll("#department-grid .dept-card").forEach((c) => c.classList.toggle("selected", Number(c.dataset.id) === dept.id));
    loadDoctors(dept.id);
    goto(2);
  }

  // -------------------------------- Step 2: Doctors --------------------------------
  async function loadDoctors(departmentId) {
    const grid = document.getElementById("doctor-grid");
    grid.innerHTML = `<div class="skeleton" style="height:160px;"></div><div class="skeleton" style="height:160px;"></div>`;
    let doctors;
    try {
      doctors = await Api.get("/doctors", { params: { department_id: departmentId } });
    } catch (err) {
      Layout.toast(err.message, "error");
      return;
    }

    if (!doctors.length) {
      grid.innerHTML = `<p class="muted">${I18n.t("admin.noData")}</p>`;
      return;
    }

    grid.innerHTML = doctors
      .map((doc) => {
        const initials = doc.full_name.split(" ").map((w) => w[0]).slice(0, 2).join("");
        const title = I18n.lang === "ar" ? doc.title_ar : doc.title_tr;
        const bio = I18n.lang === "ar" ? doc.bio_ar : doc.bio_tr;
        return `
        <button type="button" class="doctor-card" data-id="${doc.id}">
          <div class="doctor-avatar" ${doc.photo_url ? `style="background-image:url('${doc.photo_url}')"` : ""}>${doc.photo_url ? "" : initials}</div>
          <h3>${doc.full_name}</h3>
          ${title ? `<div class="doctor-title">${title}</div>` : ""}
          ${bio ? `<p class="bio">${bio}</p>` : ""}
        </button>`;
      })
      .join("");

    grid.querySelectorAll(".doctor-card").forEach((card) => {
      card.addEventListener("click", () => {
        const doc = doctors.find((d) => d.id === Number(card.dataset.id));
        selectDoctor(doc);
      });
    });
  }

  function selectDoctor(doc) {
    state.doctor = doc;
    state.slot = null;
    document.querySelectorAll("#doctor-grid .doctor-card").forEach((c) => c.classList.toggle("selected", Number(c.dataset.id) === doc.id));
    initDateStep();
    goto(3);
  }

  // ----------------------------- Step 3: Date & Time -----------------------------
  const dateInput = document.getElementById("date-input");
  const slotsGrid = document.getElementById("slots-grid");
  const slotsEmpty = document.getElementById("slots-empty");
  const toConfirmBtn = document.getElementById("to-confirm-btn");

  async function initDateStep() {
    const today = new Date().toISOString().split("T")[0];
    dateInput.min = today;
    if (!state.date) state.date = today;
    dateInput.value = state.date;

    await renderWorksOn();
    loadSlots();
  }

  async function renderWorksOn() {
    const el = document.getElementById("doctor-works-on");
    try {
      const availabilities = await Api.get("/availabilities", { params: { doctor_id: state.doctor.id } });
      const days = [...new Set(availabilities.map((a) => a.weekday))].sort();
      el.textContent = days.length ? `${I18n.t("booking.worksOn")} ${days.map((d) => I18n.dayName(d)).join("، ")}` : "";
    } catch {
      el.textContent = "";
    }
  }

  dateInput.addEventListener("change", () => {
    state.date = dateInput.value;
    state.slot = null;
    toConfirmBtn.disabled = true;
    loadSlots();
  });

  async function loadSlots() {
    toConfirmBtn.disabled = true;
    slotsGrid.innerHTML = `<div class="skeleton" style="height:44px;"></div><div class="skeleton" style="height:44px;"></div><div class="skeleton" style="height:44px;"></div>`;
    slotsEmpty.hidden = true;

    let slots;
    try {
      slots = await Api.get(`/doctors/${state.doctor.id}/available-slots`, { params: { date: state.date } });
    } catch (err) {
      Layout.toast(err.message, "error");
      return;
    }

    if (!slots.length) {
      slotsGrid.innerHTML = "";
      slotsEmpty.hidden = false;
      slotsEmpty.textContent = I18n.t("booking.noAvailability");
      return;
    }

    slotsGrid.innerHTML = slots
      .map(
        (s) => `<button type="button" class="time-slot mono ${s.is_available ? "" : "disabled"}"
                   data-start="${s.start_time}" data-end="${s.end_time}" ${s.is_available ? "" : "disabled"}>
                   ${I18n.formatTime(s.start_time)}
                 </button>`
      )
      .join("");

    slotsGrid.querySelectorAll(".time-slot:not(.disabled)").forEach((btn) => {
      btn.addEventListener("click", () => {
        slotsGrid.querySelectorAll(".time-slot").forEach((b) => b.classList.remove("selected"));
        btn.classList.add("selected");
        state.slot = { start_time: btn.dataset.start, end_time: btn.dataset.end };
        toConfirmBtn.disabled = false;
      });
    });
  }

  toConfirmBtn.addEventListener("click", () => {
    if (!Auth.isLoggedIn()) {
      localStorage.setItem(
        DRAFT_KEY,
        JSON.stringify({
          department_id: state.department.id,
          doctor_id: state.doctor.id,
          date: state.date,
          start_time: state.slot.start_time,
        })
      );
      window.location.href = "login.html?next=booking.html";
      return;
    }
    renderSummary();
    goto(4);
  });

  // -------------------------------- Step 4: Confirm --------------------------------
  function renderSummary() {
    const name = I18n.lang === "ar" ? state.department.name_ar : state.department.name_tr;
    document.getElementById("summary-doctor").textContent = state.doctor.full_name;
    document.getElementById("summary-department").textContent = name;
    document.getElementById("summary-date").textContent = I18n.formatDate(state.date);
    document.getElementById("summary-time").textContent = I18n.formatTime(state.slot.start_time);
    document.getElementById("summary-day").textContent = state.date;
  }

  document.getElementById("confirm-btn").addEventListener("click", async () => {
    const errorBox = document.getElementById("confirm-error");
    errorBox.classList.remove("visible");
    const btn = document.getElementById("confirm-btn");
    btn.disabled = true;

    try {
      await Api.post(
        "/appointments",
        {
          doctor_id: state.doctor.id,
          department_id: state.department.id,
          appointment_date: state.date,
          start_time: state.slot.start_time,
          notes: document.getElementById("notes-input").value.trim() || null,
        },
        { auth: true }
      );
      localStorage.removeItem(DRAFT_KEY);
      goto(5);
    } catch (err) {
      if (err.status === 409) {
        errorBox.textContent = I18n.t("booking.slotTaken");
        errorBox.classList.add("visible");
        goto(3);
        loadSlots();
      } else {
        errorBox.textContent = err.message;
        errorBox.classList.add("visible");
      }
    } finally {
      btn.disabled = false;
    }
  });

  document.getElementById("book-another-btn").addEventListener("click", () => {
    state.department = null;
    state.doctor = null;
    state.slot = null;
    document.getElementById("notes-input").value = "";
    goto(1);
  });

  // ------------------------------------ Back buttons ------------------------------------
  document.querySelectorAll("[data-back]").forEach((btn) => {
    btn.addEventListener("click", () => goto(Number(btn.dataset.back)));
  });

  // ------------------------------------ Bootstrapping ------------------------------------
  async function bootstrap() {
    const departments = await loadDepartments();

    // Restore a booking that was interrupted by a login redirect
    const draftRaw = localStorage.getItem(DRAFT_KEY);
    if (draftRaw && Auth.isLoggedIn()) {
      try {
        const draft = JSON.parse(draftRaw);
        const dept = departments.find((d) => d.id === draft.department_id);
        if (dept) {
          state.department = dept;
          const doctors = await Api.get("/doctors", { params: { department_id: dept.id } });
          const doc = doctors.find((d) => d.id === draft.doctor_id);
          if (doc) {
            state.doctor = doc;
            state.date = draft.date;
            const slots = await Api.get(`/doctors/${doc.id}/available-slots`, { params: { date: draft.date } });
            const slot = slots.find((s) => s.start_time === draft.start_time && s.is_available);
            if (slot) {
              state.slot = slot;
              renderSummary();
              goto(4);
              localStorage.removeItem(DRAFT_KEY);
              return;
            }
          }
        }
      } catch {
        /* fall through to normal flow */
      }
      localStorage.removeItem(DRAFT_KEY);
    }

    // Preselect department from ?department=ID (e.g. linked from the homepage)
    const params = new URLSearchParams(window.location.search);
    const preselectId = Number(params.get("department"));
    if (preselectId) {
      const dept = departments.find((d) => d.id === preselectId);
      if (dept) selectDepartment(dept);
    }
  }

  bootstrap();
})();
