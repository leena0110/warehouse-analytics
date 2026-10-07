/* api.js — Centralized API client with auth token injection and error handling */

const API_BASE = '';  // Same origin — backend serves frontend

const Api = {
  _token: null,

  setToken(token) { this._token = token; },
  clearToken() { this._token = null; },

  _headers(extra = {}) {
    const h = { 'Content-Type': 'application/json', ...extra };
    if (this._token) h['Authorization'] = `Bearer ${this._token}`;
    return h;
  },

  async _fetch(url, options = {}) {
    try {
      const res = await fetch(API_BASE + url, options);
      if (res.status === 204) return null;
      const data = await res.json().catch(() => ({ detail: res.statusText }));
      if (!res.ok) {
        const msg = data?.detail || data?.message || `HTTP ${res.status}`;
        throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
      }
      return data;
    } catch (err) {
      if (err.name === 'TypeError') throw new Error('Cannot reach server. Is the backend running?');
      throw err;
    }
  },

  get(url) {
    return this._fetch(url, { headers: this._headers() });
  },

  post(url, body) {
    return this._fetch(url, {
      method: 'POST',
      headers: this._headers(),
      body: JSON.stringify(body),
    });
  },

  put(url, body) {
    return this._fetch(url, {
      method: 'PUT',
      headers: this._headers(),
      body: JSON.stringify(body),
    });
  },

  delete(url) {
    return this._fetch(url, { method: 'DELETE', headers: this._headers() });
  },

  async postForm(url, formData) {
    const headers = {};
    if (this._token) headers['Authorization'] = `Bearer ${this._token}`;
    return this._fetch(url, { method: 'POST', headers, body: formData });
  },

  async postUrlEncoded(url, params) {
    const headers = { 'Content-Type': 'application/x-www-form-urlencoded' };
    if (this._token) headers['Authorization'] = `Bearer ${this._token}`;
    return this._fetch(url, {
      method: 'POST',
      headers,
      body: new URLSearchParams(params).toString(),
    });
  },
};
