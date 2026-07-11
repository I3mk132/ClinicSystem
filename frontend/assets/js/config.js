/**
 * Frontend configuration.
 * This is the ONLY place the backend URL is defined - change it here when
 * you deploy the API somewhere else (and nowhere else in the codebase).
 */
window.CLINIC_CONFIG = {
  API_BASE_URL: "https://clinic-api-6khk.onrender.com/api/v1",

  // Shown in the navbar / footer / booking confirmation until you replace
  // it with your real clinic branding. See README for how to customize.
  CLINIC_NAME: {
    ar: "عيادة النموذج الطبية",
    tr: "Örnek Klinik",
  },
  CLINIC_LOGO_URL: "assets/img/Logo_Nbg.png", // e.g. "assets/images/logo.png" - falls back to a generated mark
};
