/* auth.js — Login/logout, session management, token persistence */

const Auth = {
  _user: null,

  getUser() { return this._user; },
  getRole() { return this._user?.role || ''; },
  isAdmin() { return this._user?.role === 'ADMIN'; },

  async login(username, password) {
    const data = await Api.postUrlEncoded('/api/auth/token', { username, password });
    Api.setToken(data.access_token);
    this._user = {
      username: data.username,
      full_name: data.full_name,
      role: data.role,
      token: data.access_token,
    };
    sessionStorage.setItem('wh_token', data.access_token);
    sessionStorage.setItem('wh_user', JSON.stringify(this._user));
    return this._user;
  },

  logout() {
    Api.clearToken();
    this._user = null;
    sessionStorage.removeItem('wh_token');
    sessionStorage.removeItem('wh_user');
  },

  restoreSession() {
    const token = sessionStorage.getItem('wh_token');
    const user = sessionStorage.getItem('wh_user');
    if (token && user) {
      Api.setToken(token);
      this._user = JSON.parse(user);
      return true;
    }
    return false;
  },
};
