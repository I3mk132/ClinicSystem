/**
 * Tiny inline-SVG icon set for department cards. Add more keys as your
 * clinic's departments grow — icon is just a string stored on the
 * Department record (see backend/app/models/department.py).
 */
const Icons = {
  set: {
    stethoscope: '<path d="M6 3v6a4 4 0 0 0 8 0V3M10 13v2a5 5 0 0 0 10 0v-2.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/><circle cx="20.5" cy="10" r="1.8" stroke="currentColor" stroke-width="1.6"/><circle cx="6" cy="3" r="1.4" stroke="currentColor" stroke-width="1.4"/><circle cx="14" cy="3" r="1.4" stroke="currentColor" stroke-width="1.4"/>',
    tooth: '<path d="M12 3c2.5 0 4.5 1.4 5.4 2.7.9 1.4 1 3 .6 5.6-.3 2-.6 3.6-1 5.2-.4 1.6-1.1 3-2.2 3-1.3 0-1.3-2.6-1.6-4.3-.2-1.1-.6-1.9-1.2-1.9s-1 .8-1.2 1.9c-.3 1.7-.3 4.3-1.6 4.3-1.1 0-1.8-1.4-2.2-3-.4-1.6-.7-3.2-1-5.2-.4-2.6-.3-4.2.6-5.6C7.5 4.4 9.5 3 12 3Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>',
    sparkles: '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M18.4 5.6l-2.8 2.8M8.4 15.6l-2.8 2.8" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>',
    baby: '<circle cx="12" cy="9" r="4" stroke="currentColor" stroke-width="1.7"/><path d="M6 21c0-3.9 2.7-6.5 6-6.5s6 2.6 6 6.5M10 8.2c.5.5 1.3.5 1.8 0M14.2 8.2c.5.5 1.3.5 1.8 0" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>',
    bone: '<path d="M7 17 17 7M6 8.5A2.25 2.25 0 1 0 8.5 6a2.25 2.25 0 0 0-2.5-2.2A2.25 2.25 0 1 0 3.5 6 2.25 2.25 0 0 0 6 8.5ZM15.5 18A2.25 2.25 0 1 0 18 20.5a2.25 2.25 0 0 0 2.5-2.2A2.25 2.25 0 1 0 20.5 16 2.25 2.25 0 0 0 15.5 18Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>',
    heart: '<path d="M12 20.5s-7.5-4.6-9.7-9.3C.8 7.7 2.7 4 6.3 4c2 0 3.5 1 5.7 3 2.2-2 3.7-3 5.7-3 3.6 0 5.5 3.7 4 7.2-2.2 4.7-9.7 9.3-9.7 9.3Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>',
    eye: '<path d="M2 12s3.5-6.5 10-6.5S22 12 22 12s-3.5 6.5-10 6.5S2 12 2 12Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><circle cx="12" cy="12" r="2.6" stroke="currentColor" stroke-width="1.6"/>',
    brain: '<path d="M9 4a3 3 0 0 0-3 3 3 3 0 0 0-1 5.8A3 3 0 0 0 8 17a3 3 0 0 0 5-2v-8a3 3 0 0 0-4-3Zm6 0a3 3 0 0 1 3 3 3 3 0 0 1 1 5.8A3 3 0 0 1 16 17a3 3 0 0 1-2-.8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>',
  },

  svg(key, size = 26) {
    const path = this.set[key] || this.set.stethoscope;
    return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">${path}</svg>`;
  },

  options() {
    return Object.keys(this.set);
  },
};
