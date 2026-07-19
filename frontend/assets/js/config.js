/**
 * Frontend configuration.
 * This is the ONLY place the backend URL is defined - change it here when
 * you deploy the API somewhere else (and nowhere else in the codebase).
 */
window.CLINIC_CONFIG = {
  API_BASE_URL: "https://clinic-api.dijivoo.com/api/v1",

  // Which clinic (tenant) this frontend deployment belongs to. Sent as the
  // `X-Clinic` header on every API request (see api.js) so the backend knows
  // which clinic's data to serve. Must match a clinic `slug` in the backend
  // (the seed creates one with slug "demo"). One deployed frontend = one clinic.
  CLINIC_SLUG: "demo",

  // Shown in the navbar / footer / booking confirmation until you replace
  // it with your real clinic branding. See README for how to customize.
  CLINIC_NAME: {
    ar: "عيادة ديجيفو الطبية",
    tr: "dijivoo Klinik",
  },
  CLINIC_LOGO_URL: "https://cdn-clinic.dijivoo.com/logo.png" // e.g. "assets/images/logo.png" - falls back to a generated mark
};
