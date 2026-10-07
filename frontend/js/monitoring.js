/* monitoring.js — Monitoring metrics panel */

const Monitoring = {
  async load() {
    try {
      const metrics = await Api.get('/api/monitoring/metrics');
      this._render(metrics);
    } catch (err) {
      showToast('Could not load metrics: ' + err.message, 'error');
    }
  },

  _render(m) {
    // Top KPIs
    document.getElementById('mon-uptime').textContent = m.uptime_seconds.toLocaleString() + 's';
    document.getElementById('mon-db').textContent = m.database_type === 'azure_sql' ? 'Azure SQL' : 'SQLite (Local)';
    document.getElementById('mon-storage').textContent = m.azure_storage_active ? 'Azure Blob' : 'Local Fallback';
    document.getElementById('mon-runs').textContent = m.counts.analysis_runs;

    // Metrics panel
    const metricsEl = document.getElementById('metrics-panel');
    metricsEl.innerHTML = `
      <div class="metric-row"><span>Environment</span><span class="badge">${m.environment}</span></div>
      <div class="metric-row"><span>Database</span><span>${m.database_type}</span></div>
      <div class="metric-row"><span>Azure Storage Active</span><span style="color:${m.azure_storage_active ? 'var(--green)' : 'var(--yellow)'}">${m.azure_storage_active ? 'Yes' : 'No (local fallback)'}</span></div>
      <div class="metric-row"><span>App Insights Active</span><span style="color:${m.appinsights_active ? 'var(--green)' : 'var(--yellow)'}">${m.appinsights_active ? 'Yes' : 'No'}</span></div>
      <div class="metric-row"><span>Python Version</span><span>${m.server.python}</span></div>
      <div class="metric-row"><span>Server OS</span><span>${m.server.os}</span></div>
      ${m.latest_analysis ? `
        <div class="metric-row"><span>Latest Analysis</span><span>${new Date(m.latest_analysis.run_at).toLocaleString()}</span></div>
        <div class="metric-row"><span>Latest Utilization</span><span>${m.latest_analysis.utilization_pct}%</span></div>
        <div class="metric-row"><span>Latest Risk</span><span class="risk-${m.latest_analysis.risk_level}">${m.latest_analysis.risk_level}</span></div>
      ` : ''}
    `;

    // Dataset metrics
    const dsEl = document.getElementById('dataset-metrics');
    dsEl.innerHTML = `
      <div class="metric-row"><span>Total Warehouses</span><span>${m.counts.warehouses}</span></div>
      <div class="metric-row"><span>Total Datasets</span><span>${m.counts.datasets}</span></div>
      <div class="metric-row"><span>Processed</span><span style="color:var(--green)">${m.counts.datasets_processed}</span></div>
      <div class="metric-row"><span>Failed</span><span style="color:${m.counts.datasets_failed > 0 ? 'var(--red)' : 'var(--text-secondary)'}">${m.counts.datasets_failed}</span></div>
      <div class="metric-row"><span>Analysis Runs</span><span>${m.counts.analysis_runs}</span></div>
    `;
  },
};
