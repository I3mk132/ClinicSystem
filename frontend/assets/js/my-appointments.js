(async function () {
  await I18n.init();
  Layout.mount("my-appointments");
  if (!Auth.requireAuth()) return;

  let appointments = [];

  async function load() {
    try {
      appointments = await Api.get("/appointments/me", { auth: true });
    } catch (err) {
      Layout.toast(err.message, "error");
      return;
    }
    render();
  }

  function ticketHtml(appt) {
    const deptName = I18n.lang === "ar" ? appt.department.name_ar : appt.department.name_tr;
    const canCancel = appt.status === "confirmed" && appt.appointment_date >= new Date().toISOString().split("T")[0];
    return `
      <div class="ticket" data-id="${appt.id}">
        <div class="ticket-main">
          <span class="badge badge-${appt.status}" style="margin-bottom:8px;">${I18n.statusLabel(appt.status)}</span>
          <div class="ticket-title">${esc(appt.doctor.full_name)}</div>
          <div class="ticket-sub">${esc(deptName)} · ${I18n.formatDate(appt.appointment_date)}</div>
          ${appt.notes ? `<div class="ticket-sub">📝 ${esc(appt.notes)}</div>` : ""}
          ${canCancel ? `<div class="ticket-actions"><button class="btn btn-danger-ghost btn-sm" data-cancel="${appt.id}" data-i18n="myAppointments.cancelButton"></button></div>` : ""}
        </div>
        <div class="ticket-stub">
          <span class="time mono">${I18n.formatTime(appt.start_time)}</span>
          <span class="date mono">${appt.appointment_date.slice(5)}</span>
        </div>
      </div>`;
  }

  function render() {
    const today = new Date().toISOString().split("T")[0];
    const upcoming = appointments.filter((a) => a.appointment_date >= today && a.status !== "cancelled");
    const past = appointments.filter((a) => a.appointment_date < today || a.status === "cancelled");

    document.getElementById("empty-state").hidden = appointments.length > 0;
    document.getElementById("upcoming-section").hidden = upcoming.length === 0;
    document.getElementById("past-section").hidden = past.length === 0;

    document.getElementById("upcoming-list").innerHTML = upcoming.map(ticketHtml).join("");
    document.getElementById("past-list").innerHTML = past.map(ticketHtml).join("");

    I18n.translateDom(document.getElementById("upcoming-list"));
    I18n.translateDom(document.getElementById("past-list"));

    document.querySelectorAll("[data-cancel]").forEach((btn) => {
      btn.addEventListener("click", () => handleCancel(Number(btn.dataset.cancel)));
    });
  }

  async function handleCancel(id) {
    const ok = await Layout.confirmDialog({
      title: I18n.t("myAppointments.cancelConfirmTitle"),
      description: I18n.t("myAppointments.cancelConfirmDesc"),
      confirmLabel: I18n.t("myAppointments.cancelButton"),
      cancelLabel: I18n.t("myAppointments.keepIt"),
      danger: true,
    });
    if (!ok) return;

    try {
      await Api.post(`/appointments/${id}/cancel`, {}, { auth: true });
      Layout.toast(I18n.t("myAppointments.cancelledSuccess"), "success");
      load();
    } catch (err) {
      Layout.toast(err.message, "error");
    }
  }

  document.addEventListener("clinic:langchange", render);

  load();
})();
