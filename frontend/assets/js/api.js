/**
 * Minimal API client used by every page.
 * Wraps fetch() to: attach the JWT if present, build query strings,
 * parse JSON, and normalize errors into ApiError with a readable message.
 */
class ApiError extends Error {
  constructor(message, status, detail) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

/**
 * Escape a value for safe interpolation into innerHTML templates.
 * MUST be applied to every API-driven string (names, notes, bios, ...) -
 * otherwise a patient registering as `<img onerror=...>` becomes stored XSS
 * that runs in the admin panel.
 */
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

const Api = {
  baseUrl: window.CLINIC_CONFIG.API_BASE_URL,

  _buildUrl(path, params) {
    const url = new URL(this.baseUrl.replace(/\/$/, "") + path);
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== "") {
          url.searchParams.set(key, value);
        }
      });
    }
    return url.toString();
  },

  async request(method, path, { body, params, auth = false } = {}) {
    const headers = { "Content-Type": "application/json" };
    // Identify the tenant on every request so the backend serves this clinic's
    // data (multi-tenant). Slug lives in config.js.
    const slug = window.CLINIC_CONFIG.CLINIC_SLUG;
    if (slug) headers["X-Clinic"] = slug;
    if (auth) {
      const token = Auth.getToken();
      if (token) headers["Authorization"] = `Bearer ${token}`;
    }

    let response;
    try {
      response = await fetch(this._buildUrl(path, params), {
        method,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });
    } catch (networkError) {
      throw new ApiError(
        "تعذر الاتصال بالخادم / Sunucuya bağlanılamadı",
        0,
        networkError.message
      );
    }

    if (response.status === 204) return null;

    let payload = null;
    const text = await response.text();
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        payload = null;
      }
    }

    if (!response.ok) {
      const detail = payload?.detail;
      let message;
      if (typeof detail === "string") {
        message = detail;
      } else if (Array.isArray(detail)) {
        // FastAPI validation errors (422) come as [{loc, msg, type}, ...]
        message = detail.map((d) => d.msg || "").filter(Boolean).join(" · ");
      }
      // statusText is often empty over HTTP/2 - always have a fallback.
      if (!message) message = response.statusText || `HTTP ${response.status}`;
      throw new ApiError(message, response.status, detail);
    }

    return payload;
  },

  get(path, opts) { return this.request("GET", path, opts); },
  post(path, body, opts = {}) { return this.request("POST", path, { ...opts, body }); },
  put(path, body, opts = {}) { return this.request("PUT", path, { ...opts, body }); },
  patch(path, body, opts = {}) { return this.request("PATCH", path, { ...opts, body }); },
  delete(path, opts) { return this.request("DELETE", path, opts); },

  /**
   * Upload an image to Cloudflare R2 (Session 4) in three hops:
   *   1. ask the backend for a presigned PUT URL (validates type/size, mints a
   *      clinic-prefixed object key),
   *   2. PUT the raw bytes straight to R2 - a bare fetch, NOT through request():
   *      the presign signs the Content-Type, and any extra header (Authorization,
   *      X-Clinic) would break the signature, so we send only Content-Type,
   *   3. confirm back to the API to persist the MediaAsset row.
   * Returns the created MediaAsset. `meta` may carry {alt_ar, alt_tr, section_id}.
   */
  async uploadMedia(file, kind, meta = {}) {
    const presign = await this.post(
      "/admin/media/presign",
      { kind, content_type: file.type, size_bytes: file.size, filename: file.name },
      { auth: true }
    );

    let putRes;
    try {
      putRes = await fetch(presign.upload_url, {
        method: "PUT",
        headers: presign.required_headers,
        body: file,
      });
    } catch (networkError) {
      throw new ApiError("تعذر رفع الملف / Dosya yüklenemedi", 0, networkError.message);
    }
    if (!putRes.ok) {
      throw new ApiError(`R2 upload failed (HTTP ${putRes.status})`, putRes.status);
    }

    return this.post(
      "/admin/media",
      {
        object_key: presign.object_key,
        kind,
        content_type: presign.content_type,
        size_bytes: file.size,
        alt_ar: meta.alt_ar ?? null,
        alt_tr: meta.alt_tr ?? null,
        section_id: meta.section_id ?? null,
      },
      { auth: true }
    );
  },
};
