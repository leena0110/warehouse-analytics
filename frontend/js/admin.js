/* admin.js — Warehouse and user management (admin only) */

const Admin = {
  async load() {
    await Promise.all([this.loadWarehouses(), this.loadUsers()]);
  },

  async loadWarehouses() {
    const el = document.getElementById('warehouses-admin-list');
    try {
      const warehouses = await Api.get('/api/warehouses/');
      if (!warehouses.length) {
        el.innerHTML = '<div class="empty-state">No warehouses yet.</div>';
        return;
      }
      el.innerHTML = `
        <table>
          <thead><tr><th>ID</th><th>Name</th><th>Location</th><th>Rows</th><th>Cols</th><th>Action</th></tr></thead>
          <tbody>${warehouses.map(wh => `
            <tr>
              <td><code>${wh.warehouse_id}</code></td>
              <td>${wh.name}</td>
              <td>${wh.location || '—'}</td>
              <td>${wh.total_rows}</td>
              <td>${wh.total_columns}</td>
              <td><button class="btn btn-sm btn-danger" onclick="Admin._deleteWarehouse(${wh.id}, '${wh.name}')">Delete</button></td>
            </tr>`).join('')}
          </tbody>
        </table>`;
    } catch (err) {
      el.innerHTML = `<div class="empty-state">Error: ${err.message}</div>`;
    }
  },

  async createWarehouse(e) {
    e.preventDefault();
    const msgEl = document.getElementById('wh-create-msg');
    msgEl.classList.add('hidden');

    const payload = {
      warehouse_id: document.getElementById('wh-id').value.trim(),
      name: document.getElementById('wh-name').value.trim(),
      location: document.getElementById('wh-location').value.trim(),
    };

    try {
      await Api.post('/api/warehouses/', payload);
      showToast('Warehouse created.', 'success');
      document.getElementById('create-warehouse-form').reset();
      await this.loadWarehouses();
      await App.loadWarehouses(); // refresh top-bar selector
    } catch (err) {
      msgEl.className = 'alert alert-error mt-2';
      msgEl.textContent = err.message;
      msgEl.classList.remove('hidden');
    }
  },

  async _deleteWarehouse(id, name) {
    if (!confirm(`Delete warehouse "${name}" and ALL its data? This cannot be undone.`)) return;
    try {
      await Api.delete(`/api/warehouses/${id}`);
      showToast('Warehouse deleted.', 'success');
      await this.loadWarehouses();
      await App.loadWarehouses();
    } catch (err) {
      showToast(err.message, 'error');
    }
  },

  async loadUsers() {
    const el = document.getElementById('users-list');
    try {
      const users = await Api.get('/api/auth/users');
      el.innerHTML = `
        <table>
          <thead><tr><th>Username</th><th>Role</th><th>Status</th><th>Last Login</th><th>Action</th></tr></thead>
          <tbody>${users.map(u => `
            <tr>
              <td>${u.username}<br><small style="color:var(--text-muted)">${u.email}</small></td>
              <td><span class="badge ${u.role === 'ADMIN' ? 'badge-admin' : 'badge-manager'}">${u.role}</span></td>
              <td>${u.is_active ? '<span style="color:var(--green)">Active</span>' : '<span style="color:var(--red)">Inactive</span>'}</td>
              <td>${u.last_login ? new Date(u.last_login).toLocaleDateString() : 'Never'}</td>
              <td>${u.is_active && u.username !== Auth.getUser().username
                ? `<button class="btn btn-sm btn-danger" onclick="Admin._deactivateUser(${u.id}, '${u.username}')">Deactivate</button>`
                : ''}</td>
            </tr>`).join('')}
          </tbody>
        </table>`;
    } catch (err) {
      el.innerHTML = `<div class="empty-state">Error: ${err.message}</div>`;
    }
  },

  async createUser(e) {
    e.preventDefault();
    const msgEl = document.getElementById('user-create-msg');
    msgEl.classList.add('hidden');

    const payload = {
      username: document.getElementById('new-username').value.trim(),
      email: document.getElementById('new-email').value.trim(),
      password: document.getElementById('new-password').value,
      role: document.getElementById('new-role').value,
    };

    try {
      await Api.post('/api/auth/users', payload);
      showToast('User created.', 'success');
      document.getElementById('create-user-form').reset();
      await this.loadUsers();
    } catch (err) {
      msgEl.className = 'alert alert-error mt-2';
      msgEl.textContent = err.message;
      msgEl.classList.remove('hidden');
    }
  },

  async _deactivateUser(id, username) {
    if (!confirm(`Deactivate user "${username}"?`)) return;
    try {
      await Api.put(`/api/auth/users/${id}/deactivate`, {});
      showToast('User deactivated.', 'success');
      await this.loadUsers();
    } catch (err) {
      showToast(err.message, 'error');
    }
  },
};
