/* dashboard.js — Dashboard KPIs, charts, recommendations, analysis history */

const Dashboard = {
  distChart: null,
  zoneChart: null,
  gaugeChart: null,

  async load(warehouseId) {
    if (!warehouseId) {
      document.getElementById('dashboard-alert').className = 'alert alert-info';
      document.getElementById('dashboard-alert').textContent = 'Select a warehouse from the top bar to view its dashboard.';
      document.getElementById('dashboard-alert').classList.remove('hidden');
      return;
    }
    document.getElementById('dashboard-alert').classList.add('hidden');

    try {
      const data = await Api.get(`/api/analysis/latest/${warehouseId}`);
      this._renderKPIs(data.stats, data.risk_level);
      this._renderCharts(data.stats);
      this._renderRecommendations(data.recommendations || []);
      await this._loadHistory(warehouseId);
    } catch (err) {
      if (err.message.includes('No analysis')) {
        document.getElementById('dashboard-alert').className = 'alert alert-warning';
        document.getElementById('dashboard-alert').textContent = 'No analysis found. Upload a dataset and run an analysis first.';
        document.getElementById('dashboard-alert').classList.remove('hidden');
      } else {
        showToast(err.message, 'error');
      }
    }
  },

  _renderKPIs(stats, risk) {
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
  },

  _renderCharts(stats) {
    // ── Gauge (doughnut) ─────────────────────────────────────
    const gaugeCtx = document.getElementById('gauge-chart').getContext('2d');
    if (this.gaugeChart) this.gaugeChart.destroy();
    const util = stats.utilization_pct;
    const color = util >= 90 ? '#EF4444' : util >= 75 ? '#F97316' : util >= 60 ? '#EAB308' : '#22C55E';
    this.gaugeChart = new Chart(gaugeCtx, {
      type: 'doughnut',
      data: {
        datasets: [{
          data: [util, 100 - util],
          backgroundColor: [color, 'rgba(255,255,255,0.05)'],
          borderWidth: 0,
          borderRadius: 4,
        }],
      },
      options: {
        cutout: '72%',
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        animation: { animateRotate: true, duration: 800 },
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
          backgroundColor: ['#EF4444', '#22C55E', '#EAB308', '#6B7280'],
          borderWidth: 0,
          borderRadius: 3,
        }],
      },
      options: {
        plugins: {
          legend: { position: 'bottom', labels: { color: '#94A3B8', font: { size: 11 } } },
          tooltip: { callbacks: { label: ctx => ` ${ctx.label}: ${ctx.parsed.toLocaleString()}` } },
        },
        animation: { duration: 600 },
      },
    });

    // ── Zone utilization (bar) ───────────────────────────────
    const zoneCtx = document.getElementById('zone-chart').getContext('2d');
    if (this.zoneChart) this.zoneChart.destroy();
    const zoneStats = stats.zone_stats || {};
    const zoneLabels = Object.keys(zoneStats);
    const zoneUtils = zoneLabels.map(z => zoneStats[z].utilization_pct);
    const zoneColors = zoneUtils.map(u => u >= 90 ? '#EF4444' : u >= 75 ? '#F97316' : u >= 60 ? '#EAB308' : '#22C55E');

    this.zoneChart = new Chart(zoneCtx, {
      type: 'bar',
      data: {
        labels: zoneLabels.length ? zoneLabels : ['No zones'],
        datasets: [{
          label: 'Utilization %',
          data: zoneUtils.length ? zoneUtils : [0],
          backgroundColor: zoneColors,
          borderRadius: 4,
        }],
      },
      options: {
        plugins: { legend: { display: false } },
        scales: {
          y: {
            min: 0, max: 100,
            ticks: { color: '#94A3B8', callback: v => `${v}%` },
            grid: { color: 'rgba(255,255,255,0.05)' },
          },
          x: { ticks: { color: '#94A3B8' }, grid: { display: false } },
        },
        animation: { duration: 600 },
      },
    });
  },

  _renderRecommendations(recs) {
    const icons = { CRITICAL: '🚨', WARNING: '⚠️', FORECAST: '🔮', ZONE: '📍', INFO: 'ℹ️', OK: '✅' };
    const el = document.getElementById('recommendations-list');
    document.getElementById('rec-count').textContent = recs.length;

    if (!recs.length) {
      el.innerHTML = '<div class="empty-state">No recommendations available.</div>';
      return;
    }
    el.innerHTML = recs.map(r => `
      <div class="rec-item ${r.type}">
        <span class="rec-icon">${icons[r.type] || '•'}</span>
        <div class="rec-content">
          <div class="rec-title">${r.title} <span class="badge badge-sm">${r.priority}</span></div>
          <div class="rec-desc">${r.description}</div>
        </div>
      </div>
    `).join('');
  },

  async _loadHistory(warehouseId) {
    try {
      const runs = await Api.get(`/api/analysis/history/${warehouseId}?limit=10`);
      const el = document.getElementById('analysis-history-table');
      if (!runs.length) { el.innerHTML = '<div class="empty-state">No analysis runs yet.</div>'; return; }

      el.innerHTML = `
        <table>
          <thead><tr>
            <th>Run ID</th><th>Utilization</th><th>Slots</th><th>Risk</th><th>Duration</th><th>Run At</th>
          </tr></thead>
          <tbody>${runs.map(r => `
            <tr>
              <td>#${r.id}</td>
              <td><strong>${r.utilization_pct}%</strong></td>
              <td>${r.total_slots.toLocaleString()}</td>
              <td class="risk-${r.risk_level}">${r.risk_level || '—'}</td>
              <td>${r.duration_ms ? r.duration_ms + 'ms' : '—'}</td>
              <td>${new Date(r.run_at).toLocaleString()}</td>
            </tr>`).join('')}
          </tbody>
        </table>`;
    } catch { /* not critical */ }
  },
};
