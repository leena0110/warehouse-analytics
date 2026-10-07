/* upload.js — Dataset upload and analysis trigger (admin only) */

const Upload = {
  _selectedFile: null,
  _warehouseId: null,

  setWarehouse(id) { this._warehouseId = id; },

  init() {
    // Drag & drop
    const zone = document.getElementById('file-drop-zone');
    zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('drag-over'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
    zone.addEventListener('drop', e => {
      e.preventDefault();
      zone.classList.remove('drag-over');
      const file = e.dataTransfer.files[0];
      if (file) this._selectFile(file);
    });

    document.getElementById('file-input').addEventListener('change', e => {
      if (e.target.files[0]) this._selectFile(e.target.files[0]);
    });
  },

  _selectFile(file) {
    if (!file.name.toLowerCase().endsWith('.csv')) {
      showToast('Only CSV files are accepted.', 'error');
      return;
    }
    this._selectedFile = file;
    const nameEl = document.getElementById('selected-file-name');
    nameEl.textContent = `📄 ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
    nameEl.classList.remove('hidden');
    document.getElementById('upload-btn').disabled = false;
    document.getElementById('upload-btn-text').textContent = 'Upload Dataset';
    this._clearMessages();
  },

  _clearMessages() {
    ['upload-error', 'upload-success'].forEach(id => {
      document.getElementById(id).classList.add('hidden');
      document.getElementById(id).textContent = '';
    });
  },

  async submit(e) {
    e.preventDefault();
    if (!this._selectedFile) return;

    const whId = document.getElementById('upload-warehouse').value;
    if (!whId) { showToast('Select a warehouse.', 'error'); return; }

    this._setLoading(true);
    this._clearMessages();

    try {
      const formData = new FormData();
      formData.append('file', this._selectedFile);
      formData.append('warehouse_id', whId);

      const result = await Api.postForm('/api/datasets/upload', formData);

      const successEl = document.getElementById('upload-success');
      successEl.textContent = `✅ Processed ${result.rows_processed} slots. Storage: ${result.storage_mode}.` +
        (result.warnings.length ? ` Warnings: ${result.warnings.join('; ')}` : '');
      successEl.classList.remove('hidden');

      showToast('Dataset uploaded and processed!', 'success');
      this._selectedFile = null;
      document.getElementById('selected-file-name').classList.add('hidden');
      document.getElementById('file-input').value = '';

      // Refresh datasets list and analysis select
      await this.loadDatasets();
      await this.loadDatasetSelect();

    } catch (err) {
      const errEl = document.getElementById('upload-error');
      errEl.textContent = '❌ ' + err.message;
      errEl.classList.remove('hidden');
      showToast('Upload failed: ' + err.message, 'error');
    } finally {
      this._setLoading(false);
    }
  },

  _setLoading(loading) {
    document.getElementById('upload-btn').disabled = loading;
    document.getElementById('upload-btn-text').textContent = loading ? 'Uploading…' : 'Upload Dataset';
    document.getElementById('upload-spinner').classList.toggle('hidden', !loading);
  },

  async loadDatasets() {
    const whId = this._warehouseId;
    const el = document.getElementById('datasets-table');
    if (!whId) { el.innerHTML = '<div class="empty-state">Select a warehouse.</div>'; return; }

    try {
      const datasets = await Api.get(`/api/datasets/?warehouse_id=${whId}`);
      if (!datasets.length) { el.innerHTML = '<div class="empty-state">No datasets yet.</div>'; return; }

      const statusColors = { UPLOADED: '#EAB308', PROCESSING: '#3B82F6', PROCESSED: '#22C55E', FAILED: '#EF4444' };

      el.innerHTML = `
        <table>
          <thead><tr><th>File</th><th>Rows</th><th>Storage</th><th>Status</th><th>Uploaded</th><th>Action</th></tr></thead>
          <tbody>${datasets.map(d => `
            <tr>
              <td title="${d.original_filename}">${d.original_filename.substring(0, 20)}…</td>
              <td>${d.row_count?.toLocaleString() || '—'}</td>
              <td><span class="badge">${d.storage_mode}</span></td>
              <td><span class="badge" style="color:${statusColors[d.status]}">${d.status}</span></td>
              <td>${new Date(d.uploaded_at).toLocaleString()}</td>
              <td>
                ${Auth.isAdmin() ? `<button class="btn btn-sm btn-danger" onclick="Upload._deleteDataset(${d.id})">Delete</button>` : ''}
              </td>
            </tr>`).join('')}
          </tbody>
        </table>`;
    } catch (err) {
      el.innerHTML = `<div class="empty-state">Error: ${err.message}</div>`;
    }
  },

  async loadDatasetSelect() {
    const whId = this._warehouseId;
    const sel = document.getElementById('analysis-dataset-select');
    sel.innerHTML = '<option value="">Select dataset…</option>';
    if (!whId) return;
    try {
      const datasets = await Api.get(`/api/datasets/?warehouse_id=${whId}`);
      datasets.filter(d => d.status === 'PROCESSED').forEach(d => {
        const opt = document.createElement('option');
        opt.value = d.id;
        opt.textContent = `#${d.id} — ${d.original_filename} (${d.row_count} rows)`;
        sel.appendChild(opt);
      });
    } catch { /* ignore */ }
  },

  async runAnalysis() {
    const datasetId = document.getElementById('analysis-dataset-select').value;
    if (!datasetId) { showToast('Select a dataset first.', 'error'); return; }

    const btn = document.getElementById('run-analysis-btn');
    const txt = document.getElementById('run-analysis-text');
    const spin = document.getElementById('run-spinner');
    const resultEl = document.getElementById('analysis-result');

    btn.disabled = true;
    txt.textContent = 'Running…';
    spin.classList.remove('hidden');
    resultEl.classList.add('hidden');

    try {
      const result = await Api.post(`/api/analysis/run/${datasetId}`, {});
      resultEl.className = 'alert alert-success mt-2';
      resultEl.textContent = `✅ Analysis complete. Utilization: ${result.stats.utilization_pct}%. Risk: ${result.forecast?.risk_level}.`;
      resultEl.classList.remove('hidden');
      showToast('Analysis complete!', 'success');

      // Refresh dashboard if it's active
      const whId = this._warehouseId || App.currentWarehouseId;
      if (whId) {
        await Dashboard.load(whId);
        await Forecast.load(whId);
      }
    } catch (err) {
      resultEl.className = 'alert alert-error mt-2';
      resultEl.textContent = '❌ ' + err.message;
      resultEl.classList.remove('hidden');
    } finally {
      btn.disabled = false;
      txt.textContent = '▶ Run Analysis';
      spin.classList.add('hidden');
    }
  },

  async _deleteDataset(datasetId) {
    if (!confirm('Delete this dataset and all its slots?')) return;
    try {
      await Api.delete(`/api/datasets/${datasetId}`);
      showToast('Dataset deleted.', 'success');
      await this.loadDatasets();
    } catch (err) {
      showToast(err.message, 'error');
    }
  },

  async populateWarehouseSelect() {
    const sel = document.getElementById('upload-warehouse');
    sel.innerHTML = '<option value="">Select warehouse…</option>';
    try {
      const warehouses = await Api.get('/api/warehouses/');
      warehouses.forEach(wh => {
        const opt = document.createElement('option');
        opt.value = wh.id;
        opt.textContent = `${wh.name} (${wh.warehouse_id})`;
        sel.appendChild(opt);
      });
    } catch { /* ignore */ }
  },
};
