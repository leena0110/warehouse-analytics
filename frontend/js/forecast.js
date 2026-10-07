/* forecast.js — AI/ML utilization forecast view */

const Forecast = {
  _chart: null,

  async load(warehouseId) {
    if (!warehouseId) return;

    try {
      const data = await Api.get(`/api/analysis/latest/${warehouseId}`);
      if (!data.forecast) {
        document.getElementById('forecast-model-notes').innerHTML =
          '<p>No forecast data. Run an analysis first.</p>';
        return;
      }
      this._renderBanner(data.forecast, data.risk_level);
      this._renderChart(data.forecast);
      this._renderTable(data.forecast);
      this._renderNotes(data.forecast);
    } catch (err) {
      showToast('Could not load forecast: ' + err.message, 'error');
    }
  },

  _renderBanner(forecast, risk) {
    const banner = document.getElementById('risk-banner');
    const icons = { LOW: '✅', MEDIUM: '⚠️', HIGH: '🔥', CRITICAL: '🚨' };
    const msgs = {
      LOW: 'Utilization is within safe range.',
      MEDIUM: 'Monitor utilization — approaching moderate levels.',
      HIGH: 'High utilization predicted. Plan redistribution.',
      CRITICAL: 'Critical capacity forecasted. Immediate action required.',
    };
    banner.className = `forecast-banner risk-${risk}`;
    document.getElementById('risk-icon').textContent = icons[risk] || '⚠️';
    document.getElementById('risk-title').textContent = `Risk Level: ${risk}`;
    document.getElementById('risk-detail').textContent =
      `${msgs[risk] || ''} Peak forecast: ${forecast.peak_forecast}%`;

    // Also update KPI risk badge
    const kpiRisk = document.getElementById('kpi-risk-val');
    if (kpiRisk) { kpiRisk.textContent = risk; kpiRisk.className = `kpi-value risk-${risk}`; }

    document.getElementById('forecast-method-badge').textContent = forecast.method || '';
  },

  _renderChart(forecast) {
    const ctx = document.getElementById('forecast-chart').getContext('2d');
    if (this._chart) this._chart.destroy();

    const days = forecast.forecast_days || [];
    const labels = ['Today', ...days.map(d => d.date)];
    const values = [forecast.current_utilization, ...days.map(d => d.predicted_utilization)];

    const gradient = ctx.createLinearGradient(0, 0, 0, 260);
    gradient.addColorStop(0, 'rgba(59,130,246,0.4)');
    gradient.addColorStop(1, 'rgba(59,130,246,0)');

    // Color each point by risk
    const pointColors = [
      this._riskColor(forecast.current_utilization),
      ...days.map(d => this._riskColor(d.predicted_utilization)),
    ];

    this._chart = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: 'Utilization %',
          data: values,
          borderColor: '#3B82F6',
          backgroundColor: gradient,
          fill: true,
          tension: 0.4,
          pointBackgroundColor: pointColors,
          pointRadius: 5,
          pointHoverRadius: 8,
        }, {
          label: 'Critical Threshold (90%)',
          data: Array(labels.length).fill(90),
          borderColor: 'rgba(239,68,68,0.5)',
          borderDash: [6, 4],
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false,
        }],
      },
      options: {
        plugins: {
          legend: { labels: { color: '#94A3B8', font: { size: 11 } } },
          tooltip: {
            callbacks: { label: ctx => ` ${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)}%` },
          },
        },
        scales: {
          y: {
            min: 0, max: 100,
            ticks: { color: '#94A3B8', callback: v => `${v}%` },
            grid: { color: 'rgba(255,255,255,0.05)' },
          },
          x: { ticks: { color: '#94A3B8' }, grid: { display: false } },
        },
        animation: { duration: 700 },
      },
    });
  },

  _renderTable(forecast) {
    const days = forecast.forecast_days || [];
    if (!days.length) { document.getElementById('forecast-table').innerHTML = '<div class="empty-state">No forecast data.</div>'; return; }

    document.getElementById('forecast-table').innerHTML = `
      <table>
        <thead><tr><th>Day</th><th>Date</th><th>Utilization</th><th>Risk</th></tr></thead>
        <tbody>
          <tr>
            <td>Today</td><td>—</td>
            <td><strong>${forecast.current_utilization}%</strong></td>
            <td>Current</td>
          </tr>
          ${days.map(d => `
            <tr>
              <td>Day ${d.day}</td>
              <td>${d.date}</td>
              <td><strong>${d.predicted_utilization}%</strong></td>
              <td class="risk-${d.risk_level}">${d.risk_level}</td>
            </tr>`).join('')}
        </tbody>
      </table>`;
  },

  _renderNotes(forecast) {
    document.getElementById('forecast-model-notes').innerHTML = `
      <p><strong>Forecast Method:</strong> ${forecast.method}</p>
      <p style="margin-top:0.5rem">${forecast.model_notes}</p>
    `;
  },

  _riskColor(util) {
    if (util >= 90) return '#EF4444';
    if (util >= 75) return '#F97316';
    if (util >= 60) return '#EAB308';
    return '#22C55E';
  },
};
