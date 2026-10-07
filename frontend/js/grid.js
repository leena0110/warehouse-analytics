/* grid.js — Warehouse digital twin grid visualization */

const Grid = {
  _data: null,

  async load(warehouseId) {
    const gridEl = document.getElementById('warehouse-grid');
    if (!warehouseId) {
      gridEl.innerHTML = '<div class="empty-state">Select a warehouse to view the grid.</div>';
      return;
    }

    const zone = document.getElementById('grid-zone-filter').value;
    const status = document.getElementById('grid-status-filter').value;

    let url = `/api/analysis/grid/${warehouseId}`;
    const params = [];
    if (zone) params.push(`zone_filter=${encodeURIComponent(zone)}`);
    if (status) params.push(`status_filter=${encodeURIComponent(status)}`);
    if (params.length) url += '?' + params.join('&');

    gridEl.innerHTML = '<div class="empty-state"><span class="spinner"></span> Loading grid…</div>';

    try {
      const data = await Api.get(url);
      this._data = data;
      this._populateZoneFilter(data.zones || []);
      this._render(data);
    } catch (err) {
      gridEl.innerHTML = `<div class="empty-state">Error loading grid: ${err.message}</div>`;
    }
  },

  _populateZoneFilter(zones) {
    const sel = document.getElementById('grid-zone-filter');
    const current = sel.value;
    // Keep first "All Zones" option
    while (sel.options.length > 1) sel.remove(1);
    zones.forEach(z => {
      const opt = document.createElement('option');
      opt.value = z; opt.textContent = `Zone ${z}`;
      sel.appendChild(opt);
    });
    sel.value = current;
  },

  _render(data) {
    const gridEl = document.getElementById('warehouse-grid');
    if (!data.grid || !data.grid.length) {
      gridEl.innerHTML = '<div class="empty-state">No slots found. Upload and process a dataset first.</div>';
      return;
    }

    const countEl = `<div style="margin-bottom:0.75rem;font-size:0.8rem;color:var(--text-secondary)">
      Total slots: <strong>${data.total}</strong>
    </div>`;

    const zonesHtml = data.grid.map(zone => `
      <div class="grid-zone">
        <div class="grid-zone-title">Zone ${zone.zone}</div>
        ${zone.rows.map(row => `
          <div class="grid-row">
            <span class="grid-row-label">${row.row}</span>
            ${row.slots.map(slot => `
              <div class="grid-slot ${slot.status}" title="${slot.slot_id}: ${slot.status}">
                <div class="slot-tooltip">
                  <strong>${slot.slot_id}</strong><br>
                  Status: ${slot.status}<br>
                  Capacity: ${slot.capacity}<br>
                  Occupancy: ${slot.occupancy}
                  ${slot.blocked_reason ? `<br>Reason: ${slot.blocked_reason}` : ''}
                </div>
              </div>
            `).join('')}
          </div>
        `).join('')}
      </div>
    `).join('');

    gridEl.innerHTML = countEl + zonesHtml;
  },
};
