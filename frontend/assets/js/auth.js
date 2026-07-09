/**
 * Session management. The JWT and a copy of the user profile are kept in
 * localStorage so the person stays logged in across page loads/tabs -
 * this is a static multi-page site, there is no server-rendered session.
 */
const Auth = {
  TOKEN_KEY: "clinic_token",
  USER_KEY: "clinic_user",

  getToken() {
    return localStorage.getItem(this.TOKEN_KEY);
  },

  getUser() {
    const raw = localStorage.getItem(this.USER_KEY);
    return raw ? JSON.parse(raw) : null;
  },

  isLoggedIn() {
    return !!this.getToken();
  },

  isAdmin() {
    return this.getUser()?.role === "admin";
  },

  setSession(token, user) {
    localStorage.setItem(this.TOKEN_KEY, token);
    localStorage.setItem(this.USER_KEY, JSON.stringify(user));
  },

  clearSession() {
    localStorage.removeItem(this.TOKEN_KEY);
    localStorage.removeItem(this.USER_KEY);
  },

  logout() {
    this.clearSession();
    window.location.href = "index.html";
  },

  /** Call at the top of pages that require login. Redirects if not authenticated. */
  requireAuth() {
    if (!this.isLoggedIn()) {
      const next = encodeURIComponent(window.location.pathname.split("/").pop());
      window.location.href = `login.html?next=${next}`;
      return false;
    }
    return true;
  },

  /** Call at the top of admin pages. Redirects non-admins away. */
  requireAdmin() {
    if (!this.requireAuth()) return false;
    if (!this.isAdmin()) {
      window.location.href = "index.html";
      return false;
    }
    return true;
  },
};
