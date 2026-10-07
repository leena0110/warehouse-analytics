/* reports.js — Operational reports CRUD and insights panel */

const Reports = {
  _warehouseId: null,

  setWarehouse(id) { this._warehouseId = id; },

  async load() {
    await this._loadReports();
  },

  async _loadReports() {
    const el = document.getElementById('reports-list');
    if (!this._warehouseId) {
      el.innerHTML = '<div class="empty-state">Select a warehouse to view reports.</div>';
      return;
    }
    try {
      const reports = await Api.get(`/api/reports/?warehouse_id=${this._warehouseId}&page_size=50`);
      if (!reports.length) {
        el.innerHTML = '<div class="empty-state">No reports yet. Create the first one.</div>';
        return;
      }

      const sevBadge = { LOW: '#22C55E', MEDIUM: '#EAB308', HIGH: '#F97316', CRITICAL: '#EF4444' };

      el.innerHTML = `
        <table>
          <thead><tr><th>Title</th><th>Category</th><th>Severity</th><th>Status</th><th>Date</th><th>Actions</th></tr></thead>
          <tbody>
            ${reports.map(r => `
              <tr>
                <td>${r.title}</td>
                <td><span class="badge">${r.category}</span></td>
                <td><span class="badge" style="color:${sevBadge[r.severity]}">${r.severity}</span></td>
                <td>${r.is_resolved
                  ? '<span class="badge badge-info">Resolved</span>'
                  : '<span class="badge">Open</span>'}</td>
                <td>${new Date(r.created_at).toLocaleDateString()}</td>
                <td>
                  ${!r.is_resolved
                    ? `<button class="btn btn-sm btn-secondary" onclick="Reports._resolve(${r.id})">Resolve</button>`
                    : ''}
                  ${Auth.isAdmin()
                    ? `<button class="btn btn-sm btn-danger" onclick="Reports._delete(${r.id})" style="margin-left:4px">Delete</button>`
                    : ''}
                </td>
              </tr>`).join('')}
          </tbody>
        </table>`;
    } catch (err) {
      el.innerHTML = `<div class="empty-state">Error: ${err.message}</div>`;
    }
  },

  async loadInsights() {
    if (!this._warehouseId) return;
    const panel = document.getElementById('insights-panel');
    panel.innerHTML = '<div class="empty-state"><span class="spinner"></span></div>';

    try {
      const ins = await Api.get(`/api/reports/insights/${this._warehouseId}`);
      const catBreakdown = ins.category_breakdown || {};
      const sevBreakdown = ins.severity_breakdown || {};

      panel.innerHTML = `
        <div class="insight-row"><span class="insight-label">Total Reports</span><span class="insight-value">${ins.total_reports}</span></div>
        <div class="insight-row"><span class="insight-label">Analysis Method</span><span class="insight-value badge badge-info">${ins.method}</span></div>
        ${Object.entries(catBreakdown).map(([k,v]) => `
          <div class="insight-row">
            <span class="insight-label">${k}</span>
            <span class="insight-value">${v} report${v !== 1 ? 's' : ''}</span>
          </div>`).join('')}
        ${Object.entries(sevBreakdown).map(([k,v]) => `
          <div class="insight-row">
            <span class="insight-label">Severity: ${k}</span>
            <span class="insight-value">${v}</span>
          </div>`).join('')}
        ${ins.common_issues.length ? `
          <div style="margin-top:0.75rem;font-size:0.8rem;color:var(--text-secondary)">
            <strong>Common keywords:</strong> ${ins.common_issues.join(', ')}
          </div>` : ''}
        <div style="margin-top:0.75rem;font-size:0.75rem;color:var(--text-muted)">${ins.model_notes || ''}</div>
      `;
    } catch (err) {
      panel.innerHTML = `<div class="empty-state">Error: ${err.message}</div>`;
    }
  },

  openModal() {
    document.getElementById('report-modal').classList.remove('hidden');
  },

  closeModal() {
    document.getElementById('report-modal').classList.add('hidden');
    document.getElementById('report-form').reset();
  },

  async submitReport(e) {
    e.preventDefault();
    if (!this._warehouseId) { showToast('Select a warehouse first.', 'error'); return; }

    const payload = {
      warehouse_id: parseInt(this._warehouseId),
      title: document.getElementById('report-title').value,
      content: document.getElementById('report-content').value,
      category: document.getElementById('report-category').value,
      severity: document.getElementById('report-severity').value,
    };

    try {
      await Api.post('/api/reports/', payload);
      showToast('Report submitted.', 'success');
      this.closeModal();
      await this._loadReports();
    } catch (err) {
      showToast('Failed: ' + err.message, 'error');
    }
  },

  async _resolve(reportId) {
    try {
      await Api.put(`/api/reports/${reportId}/resolve`, {});
      showToast('Report resolved.', 'success');
      await this._loadReports();
    } catch (err) {
      showToast(err.message, 'error');
    }
  },

  async _delete(reportId) {
    if (!confirm('Delete this report?')) return;
    try {
      await Api.delete(`/api/reports/${reportId}`);
      showToast('Report deleted.', 'success');
      await this._loadReports();
    } catch (err) {
      showToast(err.message, 'error');
    }
  },
};
