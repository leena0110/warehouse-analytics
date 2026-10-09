/* forecast.js — Utilization forecast view */

const Forecast = {
  _chart: null,

  async load(warehouseId) {
    if (!warehouseId) return;

    try {
      const data = await Api.get(`/api/analysis/latest/${warehouseId}`);
      if (!data.forecast) {
        document.getElementById('forecast-model-notes').innerHTML =
          '<p class="text-muted">No forecast trajectory available. Execute an analysis run first.</p>';
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
    const msgs = {
      LOW: 'Capacity operates within normal operational tolerance.',
      MEDIUM: 'Moderate threshold alert. Slot rotation recommended.',
      HIGH: 'High capacity predicted. Plan cargo redistribution.',
      CRITICAL: 'Critical saturation forecasted. Immediate re-slotting required.',
    };

    banner.className = `forecast-banner`;
    const riskBadge = document.getElementById('risk-icon');
    if (riskBadge) {
      riskBadge.textContent = risk;
      riskBadge.className = `badge risk-${risk}`;
    }

    document.getElementById('risk-title').textContent = `Risk Assessment: ${risk}`;
    document.getElementById('risk-detail').textContent =
      `${msgs[risk] || ''} Peak forecast: ${forecast.peak_forecast}%.`;

    // Also update KPI risk badge if element exists
    const kpiRisk = document.getElementById('kpi-risk-val');
    if (kpiRisk) {
      kpiRisk.textContent = risk;
      kpiRisk.className = `kpi-value risk-${risk}`;
    }

    const methodBadge = document.getElementById('forecast-method-badge');
    if (methodBadge) {
      methodBadge.textContent = forecast.method || 'Local Forecasting';
      methodBadge.className = 'badge badge-sm badge-info';
    }
  },

  _renderChart(forecast) {
    const ctx = document.getElementById('forecast-chart').getContext('2d');
    if (this._chart) this._chart.destroy();

    const days = forecast.forecast_days || [];
    const labels = ['Today', ...days.map(d => d.date)];
    const values = [forecast.current_utilization, ...days.map(d => d.predicted_utilization)];

    const gradient = ctx.createLinearGradient(0, 0, 0, 240);
    gradient.addColorStop(0, 'rgba(167, 173, 183, 0.12)');
    gradient.addColorStop(1, 'rgba(167, 173, 183, 0)');

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
          borderColor: '#F2F3F5',
          borderWidth: 2,
          backgroundColor: gradient,
          fill: true,
          tension: 0.3,
          pointBackgroundColor: pointColors,
          pointBorderColor: '#0B0D10',
          pointBorderWidth: 1.5,
          pointRadius: 4,
          pointHoverRadius: 6,
        }, {
          label: 'Critical Saturation Threshold (90%)',
          data: Array(labels.length).fill(90),
          borderColor: 'rgba(220, 53, 69, 0.65)',
          borderDash: [5, 4],
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false,
        }],
      },
      options: {
        plugins: {
          legend: {
            position: 'top',
            labels: { color: '#A7ADB7', font: { size: 11, family: 'Inter' }, padding: 12 }
          },
          tooltip: {
            backgroundColor: '#1B2026',
            borderColor: '#2A3038',
            borderWidth: 1,
            titleColor: '#F2F3F5',
            bodyColor: '#A7ADB7',
            callbacks: { label: ctx => ` ${ctx.dataset.label}: ${ctx.parsed.y.toFixed(1)}%` },
          },
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

  _renderTable(forecast) {
    const days = forecast.forecast_days || [];
    const container = document.getElementById('forecast-table');
    if (!days.length) {
      container.innerHTML = '<div class="empty-state text-muted">No forecast data available.</div>';
      return;
    }

    container.innerHTML = `
      <table>
        <thead><tr><th>Horizon</th><th>Date</th><th>Projected</th><th>Risk</th></tr></thead>
        <tbody>
          <tr>
            <td>Today</td><td class="text-muted">&mdash;</td>
            <td class="mono"><strong>${forecast.current_utilization}%</strong></td>
            <td><span class="badge badge-sm">Current</span></td>
          </tr>
          ${days.map(d => `
            <tr>
              <td>Day ${d.day}</td>
              <td class="text-muted">${d.date}</td>
              <td class="mono"><strong>${d.predicted_utilization}%</strong></td>
              <td><span class="risk-${d.risk_level}">${d.risk_level}</span></td>
            </tr>`).join('')}
        </tbody>
      </table>`;
  },

  _renderNotes(forecast) {
    document.getElementById('forecast-model-notes').innerHTML = `
      <div style="display:flex;gap:1.5rem;flex-wrap:wrap;margin-bottom:0.75rem">
        <div><span class="text-muted">Algorithm Engine:</span> <strong class="mono" style="color:var(--text-primary)">${forecast.method}</strong></div>
        <div><span class="text-muted">Scope:</span> <strong style="color:var(--text-primary)">7-Day Rolling Horizon</strong></div>
        <div><span class="text-muted">Pipeline:</span> <strong style="color:var(--text-primary)">Local Execution</strong></div>
      </div>
      <p class="text-secondary" style="margin-bottom:0.5rem">${forecast.model_notes || ''}</p>
      <p class="text-muted" style="font-size:0.8rem">Heuristic selection logic: LinearRegression is fitted when &ge;5 historical observations exist; ExponentialHeuristic is used when &lt;5 observations exist.</p>
    `;
  },

  _riskColor(util) {
    if (util >= 90) return '#DC3545';
    if (util >= 75) return '#D97706';
    if (util >= 60) return '#D97706';
    return '#2E7D32';
  },
};
