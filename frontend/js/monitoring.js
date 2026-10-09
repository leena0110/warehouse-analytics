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

    const insEl = document.getElementById('mon-insights-active');
    if (insEl) {
      insEl.textContent = m.appinsights_active ? 'Active' : 'Inactive';
      insEl.style.color = m.appinsights_active ? 'var(--status-empty)' : 'var(--text-muted)';
    }

    // Metrics panel
    const metricsEl = document.getElementById('metrics-panel');
    metricsEl.innerHTML = `
      <div class="metric-row"><span>Deployment Environment</span><span class="badge">${m.environment}</span></div>
      <div class="metric-row"><span>Database Engine</span><span>${m.database_type}</span></div>
      <div class="metric-row"><span>Azure Blob Storage</span><span style="color:${m.azure_storage_active ? 'var(--status-empty)' : 'var(--status-reserved)'}">${m.azure_storage_active ? 'Connected (warehouse-data)' : 'Local File Fallback'}</span></div>
      <div class="metric-row"><span>Azure Application Insights</span><span style="color:${m.appinsights_active ? 'var(--status-empty)' : 'var(--text-muted)'}">${m.appinsights_active ? 'Active Telemetry' : 'Standby / Local Logs'}</span></div>
      <div class="metric-row"><span>Python Runtime</span><span>${m.server.python}</span></div>
      <div class="metric-row"><span>Host OS</span><span>${m.server.os}</span></div>
      ${m.latest_analysis ? `
        <div class="metric-row"><span>Latest Analysis Run</span><span>${new Date(m.latest_analysis.run_at).toLocaleString()}</span></div>
        <div class="metric-row"><span>Latest Utilization</span><span class="mono">${m.latest_analysis.utilization_pct}%</span></div>
        <div class="metric-row"><span>Assessed Risk Level</span><span class="risk-${m.latest_analysis.risk_level}">${m.latest_analysis.risk_level}</span></div>
      ` : ''}
    `;

    // Dataset metrics
    const dsEl = document.getElementById('dataset-metrics');
    dsEl.innerHTML = `
      <div class="metric-row"><span>Registered Facilities</span><span>${m.counts.warehouses}</span></div>
      <div class="metric-row"><span>Total Datasets</span><span>${m.counts.datasets}</span></div>
      <div class="metric-row"><span>Processed Datasets</span><span style="color:var(--status-empty)">${m.counts.datasets_processed}</span></div>
      <div class="metric-row"><span>Failed Uploads</span><span style="color:${m.counts.datasets_failed > 0 ? 'var(--status-occupied)' : 'var(--text-secondary)'}">${m.counts.datasets_failed}</span></div>
      <div class="metric-row"><span>Completed Analysis Pipelines</span><span>${m.counts.analysis_runs}</span></div>
    `;
  },
};
