/* app.js — Main application controller: routing, navigation, warehouse selector */

// ── Global toast utility ──────────────────────────────────────────────────────
function showToast(message, type = 'info') {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.className = `toast toast-${type}`;
  toast.classList.remove('hidden');
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => toast.classList.add('hidden'), 3500);
}

// ── Main App ──────────────────────────────────────────────────────────────────
const App = {
  currentView: 'dashboard',
  currentWarehouseId: null,

  async init() {
    this._bindLogin();
    this._bindLogout();
    this._bindNavigation();
    this._bindWarehouseSelector();
    this._bindSidebarToggle();

    // Try restore session
    if (Auth.restoreSession()) {
      await this._showApp();
    }
  },

  // ── Login ─────────────────────────────────────────────────────────────────
  _bindLogin() {
    document.getElementById('login-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const errEl = document.getElementById('login-error');
      errEl.classList.add('hidden');

      const btn = document.getElementById('login-btn');
      btn.disabled = true;
      document.getElementById('login-btn-text').textContent = 'Signing in…';
      document.getElementById('login-spinner').classList.remove('hidden');

      const username = document.getElementById('login-username').value.trim();
      const password = document.getElementById('login-password').value;

      try {
        await Auth.login(username, password);
        await this._showApp();
      } catch (err) {
        errEl.textContent = err.message;
        errEl.classList.remove('hidden');
      } finally {
        btn.disabled = false;
        document.getElementById('login-btn-text').textContent = 'Sign In';
        document.getElementById('login-spinner').classList.add('hidden');
      }
    });

    // Password toggle
    document.getElementById('toggle-pw').addEventListener('click', () => {
      const pw = document.getElementById('login-password');
      pw.type = pw.type === 'password' ? 'text' : 'password';
    });
  },

  // ── Logout ────────────────────────────────────────────────────────────────
  _bindLogout() {
    document.getElementById('logout-btn').addEventListener('click', () => {
      Auth.logout();
      document.getElementById('login-page').classList.add('active');
      document.getElementById('login-page').classList.remove('hidden');
      document.getElementById('app-page').classList.add('hidden');
      document.getElementById('app-page').classList.remove('active');
      document.getElementById('login-form').reset();
    });
  },

  // ── App setup after login ─────────────────────────────────────────────────
  async _showApp() {
    const user = Auth.getUser();
    document.getElementById('login-page').classList.remove('active');
    document.getElementById('login-page').classList.add('hidden');
    document.getElementById('app-page').classList.remove('hidden');
    document.getElementById('app-page').classList.add('active');

    // Update sidebar user info
    document.getElementById('sidebar-username').textContent = user.full_name || user.username;
    document.getElementById('sidebar-role').textContent = user.role;
    document.getElementById('user-avatar').textContent = (user.username || 'U')[0].toUpperCase();

    // Role badge
    const roleBadge = document.getElementById('role-badge');
    roleBadge.textContent = user.role;
    roleBadge.className = `badge ${user.role === 'ADMIN' ? 'badge-admin' : 'badge-manager'}`;

    // Show admin-only nav items
    if (Auth.isAdmin()) {
      document.querySelectorAll('.admin-only').forEach(el => el.classList.remove('hidden'));
    }

    // Server health check
    this._checkHealth();

    // Load warehouses into selector
    await this.loadWarehouses();

    // Upload module init
    Upload.init();
    Upload.populateWarehouseSelect();

    // Default to dashboard
    this._switchView('dashboard');
  },

  async _checkHealth() {
    try {
      await Api.get('/api/monitoring/health');
      document.getElementById('server-status').className = 'status-dot status-ok';
      document.getElementById('server-status').title = 'Server online';
    } catch {
      document.getElementById('server-status').className = 'status-dot status-error';
      document.getElementById('server-status').title = 'Server unreachable';
    }
  },

  // ── Navigation ────────────────────────────────────────────────────────────
  _bindNavigation() {
    document.querySelectorAll('.nav-btn').forEach(btn => {
      btn.addEventListener('click', () => this._switchView(btn.dataset.view));
    });
  },

  _switchView(view) {
    this.currentView = view;
    document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));

    const viewEl = document.getElementById(`view-${view}`);
    const navBtn = document.getElementById(`nav-${view}`);
    if (viewEl) viewEl.classList.add('active');
    if (navBtn) navBtn.classList.add('active');

    const titles = {
      dashboard: 'Dashboard', grid: 'Warehouse Grid', forecast: 'AI Forecast',
      reports: 'Operational Reports', upload: 'Upload Dataset', admin: 'Admin Panel',
      monitoring: 'Monitoring',
    };
    document.getElementById('page-title').textContent = titles[view] || 'WarehouseAI';

    // Load view data
    const whId = this.currentWarehouseId;
    switch (view) {
      case 'dashboard': Dashboard.load(whId); break;
      case 'grid': Grid.load(whId); break;
      case 'forecast': Forecast.load(whId); break;
      case 'reports':
        Reports.setWarehouse(whId);
        Reports.load();
        this._bindReportForm();
        break;
      case 'upload':
        Upload.setWarehouse(whId);
        Upload.loadDatasets();
        Upload.loadDatasetSelect();
        this._bindUploadForm();
        break;
      case 'admin': Admin.load(); this._bindAdminForms(); break;
      case 'monitoring': Monitoring.load(); break;
    }
  },

  // ── Warehouse Selector ────────────────────────────────────────────────────
  async loadWarehouses() {
    const sel = document.getElementById('warehouse-selector');
    const prev = sel.value;
    try {
      const warehouses = await Api.get('/api/warehouses/');
      sel.innerHTML = '<option value="">Select Warehouse…</option>';
      warehouses.forEach(wh => {
        const opt = document.createElement('option');
        opt.value = wh.id;
        opt.textContent = `${wh.name}`;
        sel.appendChild(opt);
      });
      // Restore or auto-select first
      if (prev && sel.querySelector(`option[value="${prev}"]`)) {
        sel.value = prev;
        this.currentWarehouseId = prev;
      } else if (warehouses.length === 1) {
        sel.value = warehouses[0].id;
        this.currentWarehouseId = warehouses[0].id;
        this._onWarehouseChange(warehouses[0].id);
      }
    } catch { /* server may not have warehouses yet */ }
  },

  _bindWarehouseSelector() {
    document.getElementById('warehouse-selector').addEventListener('change', (e) => {
      this.currentWarehouseId = e.target.value;
      Upload.setWarehouse(e.target.value);
      Reports.setWarehouse(e.target.value);
      this._onWarehouseChange(e.target.value);
    });
  },

  _onWarehouseChange(whId) {
    // Reload current view with new warehouse
    this._switchView(this.currentView);
  },

  // ── Sidebar toggle ────────────────────────────────────────────────────────
  _bindSidebarToggle() {
    document.getElementById('sidebar-toggle').addEventListener('click', () => {
      document.getElementById('sidebar').classList.toggle('open');
    });
  },

  // ── Form bindings (called once per view activation) ───────────────────────
  _reportFormBound: false,
  _bindReportForm() {
    if (this._reportFormBound) return;
    this._reportFormBound = true;
    document.getElementById('new-report-btn').addEventListener('click', () => Reports.openModal());
    document.getElementById('close-report-modal').addEventListener('click', () => Reports.closeModal());
    document.getElementById('cancel-report').addEventListener('click', () => Reports.closeModal());
    document.getElementById('report-modal').querySelector('.modal-backdrop')
      .addEventListener('click', () => Reports.closeModal());
    document.getElementById('report-form').addEventListener('submit', (e) => Reports.submitReport(e));
    document.getElementById('load-insights-btn').addEventListener('click', () => Reports.loadInsights());
  },

  _uploadFormBound: false,
  _bindUploadForm() {
    if (this._uploadFormBound) return;
    this._uploadFormBound = true;
    document.getElementById('upload-form').addEventListener('submit', (e) => Upload.submit(e));
    document.getElementById('run-analysis-btn').addEventListener('click', () => Upload.runAnalysis());
  },

  _adminFormBound: false,
  _bindAdminForms() {
    if (this._adminFormBound) return;
    this._adminFormBound = true;
    document.getElementById('create-warehouse-form').addEventListener('submit', (e) => Admin.createWarehouse(e));
    document.getElementById('create-user-form').addEventListener('submit', (e) => Admin.createUser(e));
    document.getElementById('refresh-metrics-btn')?.addEventListener('click', () => Monitoring.load());
  },

  // Grid filter binding
  _gridFiltersBound: false,
};

// ── Grid filter controls ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  App.init();

  document.getElementById('grid-refresh-btn').addEventListener('click', () => {
    Grid.load(App.currentWarehouseId);
  });
  document.getElementById('grid-zone-filter').addEventListener('change', () => {
    Grid.load(App.currentWarehouseId);
  });
  document.getElementById('grid-status-filter').addEventListener('change', () => {
    Grid.load(App.currentWarehouseId);
  });
  document.getElementById('refresh-metrics-btn')?.addEventListener('click', () => {
    Monitoring.load();
  });
});
