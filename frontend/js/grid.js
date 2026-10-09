/* grid.js — Warehouse 2D Digital Twin matrix visualization and slot inspection */

const Grid = {
  _data: null,
  _activeZoneIndex: 0,
  _selectedSlot: null,
  _zoneMapping: [
    { label: 'Zone 1', code: 'A' },
    { label: 'Zone 2', code: 'B' },
    { label: 'Zone 3', code: 'C' },
    { label: 'Zone 4', code: 'D' },
    { label: 'Zone 5', code: 'E' },
  ],

  init() {
    this._bindZoneTabs();
  },

  _bindZoneTabs() {
    const tabsContainer = document.getElementById('zone-tabs');
    if (!tabsContainer || tabsContainer._bound) return;
    tabsContainer._bound = true;

    tabsContainer.addEventListener('click', (e) => {
      const btn = e.target.closest('.zone-tab-btn');
      if (!btn) return;
      const idx = parseInt(btn.dataset.zoneIdx, 10);
      if (isNaN(idx)) return;
      this._activeZoneIndex = idx;

      // Update tab active classes
      tabsContainer.querySelectorAll('.zone-tab-btn').forEach((b, i) => {
        b.classList.toggle('active', i === idx);
      });

      this._renderActiveZone();
    });
  },

  async load(warehouseId) {
    this._bindZoneTabs();
    const gridEl = document.getElementById('warehouse-grid');
    if (!warehouseId) {
      gridEl.innerHTML = '<div class="empty-state text-muted">Select a warehouse to inspect the digital twin.</div>';
      return;
    }

    const status = document.getElementById('grid-status-filter') ? document.getElementById('grid-status-filter').value : '';

    // Fetch all zones so tab switching is instant and preserves all 400 slots
    let url = `/api/analysis/grid/${warehouseId}`;
    if (status) {
      url += `?status_filter=${encodeURIComponent(status)}`;
    }

    gridEl.innerHTML = '<div class="empty-state text-muted"><span class="spinner"></span> Loading digital twin…</div>';

    try {
      const data = await Api.get(url);
      this._data = data;
      this._populateZoneFilter(data.zones || []);
      this._renderActiveZone();
    } catch (err) {
      gridEl.innerHTML = `<div class="empty-state text-muted">Error loading digital twin: ${err.message}</div>`;
    }
  },

  _populateZoneFilter(zones) {
    const sel = document.getElementById('grid-zone-filter');
    if (!sel) return;
    const current = sel.value;
    while (sel.options.length > 1) sel.remove(1);
    zones.forEach(z => {
      const opt = document.createElement('option');
      opt.value = z;
      opt.textContent = `Zone ${z}`;
      sel.appendChild(opt);
    });
    sel.value = current;
  },

  _renderActiveZone() {
    const data = this._data;
    const gridEl = document.getElementById('warehouse-grid');
    if (!data || !data.grid || !data.grid.length) {
      gridEl.innerHTML = '<div class="empty-state text-muted">No slots found. Upload and analyze a dataset first.</div>';
      return;
    }

    // Determine target zone code for active tab index (0=A, 1=B, etc.)
    const targetMap = this._zoneMapping[this._activeZoneIndex] || this._zoneMapping[0];
    const targetCode = targetMap.code;

    // Find zone in data (or fallback to index)
    let currentZone = data.grid.find(z => String(z.zone).toUpperCase() === targetCode.toUpperCase());
    if (!currentZone && data.grid[this._activeZoneIndex]) {
      currentZone = data.grid[this._activeZoneIndex];
    }
    if (!currentZone) {
      currentZone = data.grid[0];
    }

    // Update active zone title header
    const zoneTitleEl = document.getElementById('dt-active-zone-title');
    if (zoneTitleEl) {
      const zoneName = currentZone ? currentZone.zone : targetCode;
      zoneTitleEl.textContent = `Active: ${targetMap.label} (${zoneName}) • 80 Slots (8 × 10 Matrix)`;
    }

    const zoneStatsEl = document.getElementById('dt-active-zone-stats');
    if (zoneStatsEl) {
      zoneStatsEl.textContent = `Facility total: ${data.total || 400} slots`;
    }

    // Update legend counts
    this._updateLegendCounts(data, currentZone);

    // Build 8 x 10 slot grid HTML
    const statusFilter = (document.getElementById('grid-status-filter')?.value || '').toUpperCase();

    // Column headers 1 through 10
    let colHeadersHtml = '<div class="matrix-col-headers"><div class="matrix-col-header-cell">ROW</div>';
    for (let c = 1; c <= 10; c++) {
      colHeadersHtml += `<div class="matrix-col-header-cell">${c}</div>`;
    }
    colHeadersHtml += '</div>';

    // Matrix rows
    const rows = currentZone.rows || [];
    let rowsHtml = '';

    rows.forEach((rowObj, rIdx) => {
      const rowLabel = rowObj.row || String(rIdx + 1);
      rowsHtml += `<div class="matrix-row">`;
      rowsHtml += `<div class="matrix-row-label">R-${rowLabel}</div>`;

      // Render slots in this row (up to 10 columns)
      const slots = rowObj.slots || [];
      for (let c = 1; c <= 10; c++) {
        const slot = slots.find(s => parseInt(s.col, 10) === c) || slots[c - 1];
        if (slot) {
          const isDimmed = statusFilter && slot.status.toUpperCase() !== statusFilter;
          const isSelected = this._selectedSlot && this._selectedSlot.slot_id === slot.slot_id;
          const statusClass = slot.status ? slot.status.toUpperCase() : 'EMPTY';

          rowsHtml += `
            <div class="slot-cell ${statusClass} ${isDimmed ? 'dimmed' : ''} ${isSelected ? 'selected' : ''}"
                 data-slot-id="${slot.slot_id}"
                 data-zone="${currentZone.zone}"
                 data-zone-label="${targetMap.label}"
                 data-row="${rowLabel}"
                 data-col="${slot.col || c}"
                 data-status="${slot.status}"
                 data-capacity="${slot.capacity ?? 1000}"
                 data-occupancy="${slot.occupancy ?? 0}"
                 data-reason="${slot.blocked_reason || ''}"
                 title="${slot.slot_id} [${slot.status}]">
              ${c}
            </div>
          `;
        } else {
          // Placeholder empty cell
          rowsHtml += `<div class="slot-cell EMPTY dimmed">${c}</div>`;
        }
      }
      rowsHtml += `</div>`;
    });

    gridEl.innerHTML = `<div class="slot-matrix">${colHeadersHtml}${rowsHtml}</div>`;

    // Attach slot interaction events
    this._attachSlotListeners(gridEl);
  },

  _updateLegendCounts(data, currentZone) {
    let counts = { EMPTY: 0, OCCUPIED: 0, RESERVED: 0, BLOCKED: 0 };

    if (currentZone && currentZone.rows) {
      currentZone.rows.forEach(r => {
        (r.slots || []).forEach(s => {
          const st = (s.status || '').toUpperCase();
          if (counts[st] !== undefined) counts[st]++;
        });
      });
    }

    const setEl = (id, count) => {
      const el = document.getElementById(id);
      if (el) el.textContent = `${count} in zone`;
    };

    setEl('legend-count-empty', counts.EMPTY);
    setEl('legend-count-occupied', counts.OCCUPIED);
    setEl('legend-count-reserved', counts.RESERVED);
    setEl('legend-count-blocked', counts.BLOCKED);
  },

  _attachSlotListeners(gridEl) {
    const cells = gridEl.querySelectorAll('.slot-cell[data-slot-id]');
    cells.forEach(cell => {
      // Hover inspects slot
      cell.addEventListener('mouseenter', () => {
        this._inspectSlotFromElement(cell);
      });

      // Click pins/locks inspection
      cell.addEventListener('click', () => {
        cells.forEach(c => c.classList.remove('selected'));
        cell.classList.add('selected');
        this._selectedSlot = {
          slot_id: cell.dataset.slotId,
          zone: cell.dataset.zone,
          zoneLabel: cell.dataset.zoneLabel,
          row: cell.dataset.row,
          col: cell.dataset.col,
          status: cell.dataset.status,
          capacity: cell.dataset.capacity,
          occupancy: cell.dataset.occupancy,
          reason: cell.dataset.reason,
        };
        this._inspectSlot(this._selectedSlot);
      });
    });

    gridEl.addEventListener('mouseleave', () => {
      if (this._selectedSlot) {
        this._inspectSlot(this._selectedSlot);
      } else {
        this._clearInspector();
      }
    });
  },

  _inspectSlotFromElement(cell) {
    const slot = {
      slot_id: cell.dataset.slotId,
      zone: cell.dataset.zone,
      zoneLabel: cell.dataset.zoneLabel,
      row: cell.dataset.row,
      col: cell.dataset.col,
      status: cell.dataset.status,
      capacity: cell.dataset.capacity,
      occupancy: cell.dataset.occupancy,
      reason: cell.dataset.reason,
    };
    this._inspectSlot(slot);
  },

  _inspectSlot(slot) {
    const placeholder = document.getElementById('inspector-placeholder');
    const details = document.getElementById('inspector-details');
    const badge = document.getElementById('inspector-status-badge');

    if (!slot || !details) return;

    if (placeholder) placeholder.classList.add('hidden');
    details.classList.remove('hidden');

    document.getElementById('insp-slot-id').textContent = slot.slot_id;
    document.getElementById('insp-zone').textContent = `${slot.zoneLabel || 'Zone'} (${slot.zone})`;
    document.getElementById('insp-pos').textContent = `Row ${slot.row}, Col ${slot.col}`;
    document.getElementById('insp-status').textContent = slot.status;
    document.getElementById('insp-capacity').textContent = `${Number(slot.capacity || 0).toLocaleString()} units`;
    document.getElementById('insp-occupancy').textContent = `${Number(slot.occupancy || 0).toLocaleString()} units`;

    const reasonRow = document.getElementById('insp-reason-row');
    if (reasonRow) {
      if (slot.reason) {
        reasonRow.classList.remove('hidden');
        document.getElementById('insp-reason').textContent = slot.reason;
      } else {
        reasonRow.classList.add('hidden');
      }
    }

    if (badge) {
      badge.textContent = slot.status;
      badge.className = `badge badge-sm badge-status ${slot.status.toLowerCase()}`;
      badge.classList.remove('hidden');
    }
  },

  _clearInspector() {
    const placeholder = document.getElementById('inspector-placeholder');
    const details = document.getElementById('inspector-details');
    const badge = document.getElementById('inspector-status-badge');

    if (placeholder) placeholder.classList.remove('hidden');
    if (details) details.classList.add('hidden');
    if (badge) badge.classList.add('hidden');
  },
};
