/* dashboard.js — Dashboard KPIs, charts, recommendations, analysis history */

const Dashboard = {
  distChart: null,
  zoneChart: null,
  gaugeChart: null,

  async load(warehouseId) {
    if (!warehouseId) {
      document.getElementById('dashboard-alert').className = 'alert alert-info';
      document.getElementById('dashboard-alert').textContent = 'Select a warehouse from the top bar to inspect operations.';
      document.getElementById('dashboard-alert').classList.remove('hidden');
      return;
    }
    document.getElementById('dashboard-alert').classList.add('hidden');

    try {
      const data = await Api.get(`/api/analysis/latest/${warehouseId}`);
      this._renderKPIs(data.stats, data.risk_level, data.run_at);
      this._renderCharts(data.stats);
      this._renderRecommendations(data.recommendations || []);
      await this._loadHistory(warehouseId);
    } catch (err) {
      if (err.message.includes('No analysis')) {
        document.getElementById('dashboard-alert').className = 'alert alert-warning';
        document.getElementById('dashboard-alert').textContent = 'No analysis runs found. Upload a dataset and execute an analysis run first.';
        document.getElementById('dashboard-alert').classList.remove('hidden');
      } else {
        showToast(err.message, 'error');
      }
    }
  },

  _renderKPIs(stats, risk, runAt) {
    document.getElementById('kpi-total-val').textContent = stats.total_slots.toLocaleString();
    document.getElementById('kpi-occ-val').textContent = stats.occupied_slots.toLocaleString();
    document.getElementById('kpi-emp-val').textContent = stats.empty_slots.toLocaleString();
    document.getElementById('kpi-res-val').textContent = stats.reserved_slots.toLocaleString();
    document.getElementById('kpi-blk-val').textContent = stats.blocked_slots.toLocaleString();
    document.getElementById('kpi-util-val').textContent = `${stats.utilization_pct}%`;
    document.getElementById('kpi-cap-val').textContent = stats.available_capacity.toLocaleString();

    const riskEl = document.getElementById('kpi-risk-val');
    riskEl.textContent = risk || '—';
    riskEl.className = `kpi-value risk-${risk}`;

    document.getElementById('gauge-label').textContent = `${stats.utilization_pct}%`;

    const tsEl = document.getElementById('overview-timestamp');
    if (tsEl && runAt) {
      tsEl.textContent = `Last analysis: ${new Date(runAt).toLocaleString()}`;
    }

    const whSel = document.getElementById('warehouse-selector');
    const whNameEl = document.getElementById('overview-wh-name');
    if (whSel && whNameEl && whSel.selectedOptions[0]) {
      const name = whSel.selectedOptions[0].text;
      if (name && !name.includes('Select')) {
        whNameEl.textContent = `Warehouse Overview — ${name}`;
      }
    }
  },

  _renderCharts(stats) {
    // ── Gauge (doughnut) ─────────────────────────────────────
    const gaugeCtx = document.getElementById('gauge-chart').getContext('2d');
    if (this.gaugeChart) this.gaugeChart.destroy();
    const util = stats.utilization_pct;
    // Muted semantic palette
    const color = util >= 90 ? '#DC3545' : util >= 75 ? '#D97706' : util >= 60 ? '#D97706' : '#2E7D32';

    this.gaugeChart = new Chart(gaugeCtx, {
      type: 'doughnut',
      data: {
        datasets: [{
          data: [util, 100 - util],
          backgroundColor: [color, '#1B2026'],
          borderWidth: 0,
          borderRadius: 2,
        }],
      },
      options: {
        cutout: '76%',
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        animation: { animateRotate: true, duration: 600 },
      },
    });

    // ── Distribution (doughnut) ──────────────────────────────
    const distCtx = document.getElementById('distribution-chart').getContext('2d');
    if (this.distChart) this.distChart.destroy();
    this.distChart = new Chart(distCtx, {
      type: 'doughnut',
      data: {
        labels: ['Occupied', 'Empty', 'Reserved', 'Blocked'],
        datasets: [{
          data: [stats.occupied_slots, stats.empty_slots, stats.reserved_slots, stats.blocked_slots],
          backgroundColor: ['#DC3545', '#2E7D32', '#D97706', '#64748B'],
          borderWidth: 0,
          borderRadius: 2,
        }],
      },
      options: {
        plugins: {
          legend: {
            position: 'bottom',
            labels: { color: '#A7ADB7', font: { size: 11, family: 'Inter' }, padding: 14 }
          },
          tooltip: {
            backgroundColor: '#1B2026',
            borderColor: '#2A3038',
            borderWidth: 1,
            titleColor: '#F2F3F5',
            bodyColor: '#A7ADB7',
            callbacks: { label: ctx => ` ${ctx.label}: ${ctx.parsed.toLocaleString()} slots` }
          },
        },
        animation: { duration: 500 },
      },
    });

    // ── Zone utilization (bar) ───────────────────────────────
    const zoneCtx = document.getElementById('zone-chart').getContext('2d');
    if (this.zoneChart) this.zoneChart.destroy();
    const zoneStats = stats.zone_stats || {};
    const zoneLabels = Object.keys(zoneStats);
    const zoneUtils = zoneLabels.map(z => zoneStats[z].utilization_pct);
    const zoneColors = zoneUtils.map(u => u >= 90 ? '#DC3545' : u >= 75 ? '#D97706' : u >= 60 ? '#D97706' : '#2E7D32');

    this.zoneChart = new Chart(zoneCtx, {
      type: 'bar',
      data: {
        labels: zoneLabels.length ? zoneLabels.map(z => `Zone ${z}`) : ['No zones'],
        datasets: [{
          label: 'Utilization %',
          data: zoneUtils.length ? zoneUtils : [0],
          backgroundColor: zoneColors,
          borderRadius: 3,
        }],
      },
      options: {
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: '#1B2026',
            borderColor: '#2A3038',
            borderWidth: 1,
            titleColor: '#F2F3F5',
            bodyColor: '#A7ADB7',
            callbacks: { label: ctx => ` Utilization: ${ctx.parsed.y}%` }
          }
        },
        scales: {
          y: {
            min: 0, max: 100,
            ticks: { color: '#737B86', callback: v => `${v}%`, font: { size: 10, family: 'JetBrains Mono' } },
            grid: { color: 'rgba(42, 48, 56, 0.5)' },
            border: { display: false }
          },
          x: {
            ticks: { color: '#A7ADB7', font: { size: 11, family: 'Inter' } },
            grid: { display: false },
            border: { display: false }
          },
        },
        animation: { duration: 500 },
      },
    });
  },

  _renderRecommendations(recs) {
    const el = document.getElementById('recommendations-list');
    document.getElementById('rec-count').textContent = recs.length;

    if (!recs.length) {
      el.innerHTML = '<div class="empty-state text-muted">No operational recommendations at this time.</div>';
      return;
    }

    el.innerHTML = recs.map(r => `
      <div class="rec-item">
        <div class="rec-badge-col">
          <span class="badge ${r.priority === 'P1' || r.type === 'CRITICAL' ? 'badge-admin' : 'badge-manager'}">${r.priority || r.type}</span>
        </div>
        <div class="rec-content">
          <div class="rec-title">
            <span>${r.title}</span>
            <span class="badge badge-sm">${r.type}</span>
          </div>
          <div class="rec-desc">${r.description}</div>
        </div>
      </div>
    `).join('');
  },

  async _loadHistory(warehouseId) {
    try {
      const runs = await Api.get(`/api/analysis/history/${warehouseId}?limit=10`);
      const el = document.getElementById('analysis-history-table');
      if (!runs.length) {
        el.innerHTML = '<div class="empty-state text-muted">No analysis runs recorded.</div>';
        return;
      }

      el.innerHTML = `
        <table>
          <thead><tr>
            <th>Run</th><th>Utilization</th><th>Slots</th><th>Risk Assessment</th><th>Computation Time</th><th>Timestamp</th>
          </tr></thead>
          <tbody>${runs.map(r => `
            <tr>
              <td class="mono">#${r.id}</td>
              <td class="mono"><strong>${r.utilization_pct}%</strong></td>
              <td class="mono">${r.total_slots.toLocaleString()}</td>
              <td><span class="risk-${r.risk_level}">${r.risk_level || '—'}</span></td>
              <td class="mono">${r.duration_ms ? r.duration_ms + 'ms' : '—'}</td>
              <td class="text-muted">${new Date(r.run_at).toLocaleString()}</td>
            </tr>`).join('')}
          </tbody>
        </table>`;
    } catch { /* not critical */ }
  },
};
