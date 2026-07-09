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
      const message = typeof detail === "string" ? detail : response.statusText;
      throw new ApiError(message, response.status, detail);
    }

    return payload;
  },

  get(path, opts) { return this.request("GET", path, opts); },
  post(path, body, opts = {}) { return this.request("POST", path, { ...opts, body }); },
  patch(path, body, opts = {}) { return this.request("PATCH", path, { ...opts, body }); },
  delete(path, opts) { return this.request("DELETE", path, opts); },
};
