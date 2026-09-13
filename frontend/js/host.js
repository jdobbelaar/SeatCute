(function () {
  const API = window.SeatCuteAPI;
  const FMT = window.SeatCuteFormat;
  const SIZES = API.SIZES;

  let selectedTableId = null;
  let refreshTimer = null;

  // ---------------- view toggle ----------------

  const tabHost = document.getElementById('tab-host');
  const tabAdmin = document.getElementById('tab-admin');
  const viewHost = document.getElementById('view-host');
  const viewAdmin = document.getElementById('view-admin');
  const connectionError = document.getElementById('connection-error');

  function showConnectionError(err) {
    const detail = err && err.message ? err.message : 'connection failed';
    connectionError.textContent = `Could not reach the backend at ${window.SeatCuteConfig.API_BASE_URL} — make sure it's running, then try again. (${detail})`;
    connectionError.hidden = false;
  }

  function hideConnectionError() {
    connectionError.hidden = true;
  }

  tabHost.addEventListener('click', () => switchView('host'));
  tabAdmin.addEventListener('click', () => switchView('admin'));

  function switchView(name) {
    const isHost = name === 'host';
    tabHost.classList.toggle('active', isHost);
    tabAdmin.classList.toggle('active', !isHost);
    viewHost.classList.toggle('active', isHost);
    viewAdmin.classList.toggle('active', !isHost);
    if (isHost) {
      renderHost();
    } else {
      renderAdmin();
    }
  }

  // ---------------- host view ----------------

  const tablesContainer = document.getElementById('tables-container');
  const queuesContainer = document.getElementById('queues-container');
  const selectionText = document.getElementById('selection-text');
  const btnBypass = document.getElementById('btn-bypass');

  btnBypass.addEventListener('click', async () => {
    if (!selectedTableId) return;
    btnBypass.disabled = true;
    try {
      await API.seatBypass({ tableId: selectedTableId });
      selectedTableId = null;
      await renderHost();
    } catch (err) {
      alert(err.message || 'Could not seat that table.');
      btnBypass.disabled = false;
    }
  });

  async function renderHost() {
    let tables, queueEntries;
    try {
      [tables, queueEntries] = await Promise.all([API.listTables(), API.listQueue()]);
    } catch (err) {
      showConnectionError(err);
      return;
    }
    hideConnectionError();

    // Selection may have gone stale (e.g. the table was seated elsewhere).
    if (selectedTableId && !tables.some((t) => t.id === selectedTableId && t.status === 'available')) {
      selectedTableId = null;
    }

    renderTables(tables);
    renderQueues(queueEntries);
    renderSelectionBar(tables);
  }

  function renderSelectionBar(tables) {
    if (selectedTableId) {
      const table = tables.find((t) => t.id === selectedTableId);
      selectionText.innerHTML = `Selected: <strong>${FMT.escapeHtml(table ? table.label : '')}</strong> — click Seat on a queue entry, or Bypass Queue for a walk-in.`;
      btnBypass.disabled = false;
    } else {
      selectionText.textContent = 'No table selected — select an available table below to seat a party.';
      btnBypass.disabled = true;
    }
  }

  function renderTables(tables) {
    tablesContainer.innerHTML = '';
    for (const size of SIZES) {
      const group = tables.filter((t) => t.size === size);
      const wrap = document.createElement('div');
      wrap.className = 'size-group';

      const heading = document.createElement('h3');
      heading.textContent = `${size}-Seat Tables`;
      wrap.appendChild(heading);

      const grid = document.createElement('div');
      grid.className = 'table-grid';

      if (group.length === 0) {
        const note = document.createElement('p');
        note.className = 'empty-note';
        note.textContent = 'No tables of this size configured.';
        wrap.appendChild(note);
      } else {
        for (const table of group) {
          grid.appendChild(renderTableCard(table));
        }
        wrap.appendChild(grid);
      }

      tablesContainer.appendChild(wrap);
    }
  }

  function renderTableCard(table) {
    const card = document.createElement('div');
    const classes = ['table-card', table.status];
    if (table.pendingRemoval) classes.push('pending');
    if (table.id === selectedTableId) classes.push('selected');
    card.className = classes.join(' ');

    const label = document.createElement('div');
    label.className = 'label';
    label.textContent = table.label;
    card.appendChild(label);

    const statusLine = document.createElement('div');
    statusLine.className = 'status-line';
    if (table.status === 'available') {
      statusLine.textContent = 'Available';
    } else {
      statusLine.textContent = `Occupied — ${table.elapsedMinutes} min elapsed, free by ${FMT.clockTime(table.freeAt)}`;
    }
    card.appendChild(statusLine);

    if (table.status === 'occupied' && table.party) {
      const partyLine = document.createElement('div');
      partyLine.className = 'party-line';
      partyLine.textContent = `${table.party.name} · ${FMT.phoneDisplay(table.party.phone)}`;
      card.appendChild(partyLine);
    }

    if (table.pendingRemoval) {
      const flag = document.createElement('div');
      flag.className = 'pending-flag';
      flag.textContent = 'Retiring on release';
      card.appendChild(flag);
    }

    if (table.status === 'available') {
      card.addEventListener('click', () => {
        selectedTableId = selectedTableId === table.id ? null : table.id;
        renderHost();
      });
    } else if (table.status === 'occupied') {
      const releaseRow = document.createElement('div');
      releaseRow.className = 'release-row';
      const releaseBtn = document.createElement('button');
      releaseBtn.type = 'button';
      releaseBtn.className = 'btn btn-small btn-outline';
      releaseBtn.textContent = 'Release';
      releaseBtn.addEventListener('click', async (e) => {
        e.stopPropagation();
        releaseBtn.disabled = true;
        try {
          await API.releaseTable(table.id);
          await renderHost();
        } catch (err) {
          alert(err.message || 'Could not release that table.');
          releaseBtn.disabled = false;
        }
      });
      releaseRow.appendChild(releaseBtn);
      card.appendChild(releaseRow);
    }

    return card;
  }

  function renderQueues(queueEntries) {
    queuesContainer.innerHTML = '';
    for (const size of SIZES) {
      const entries = queueEntries.filter((q) => q.queueSize === size);

      const col = document.createElement('div');
      const heading = document.createElement('h3');
      heading.textContent = `${size}-Seat Queue`;
      col.appendChild(heading);

      if (entries.length === 0) {
        const note = document.createElement('p');
        note.className = 'empty-note';
        note.textContent = 'No one waiting.';
        col.appendChild(note);
      } else {
        const list = document.createElement('ul');
        list.className = 'queue-list';
        for (const entry of entries) {
          list.appendChild(renderQueueEntry(entry));
        }
        col.appendChild(list);
      }

      queuesContainer.appendChild(col);
    }
  }

  function renderQueueEntry(entry) {
    const li = document.createElement('li');
    li.className = 'queue-entry';

    const nameRow = document.createElement('div');
    nameRow.className = 'name-row';
    nameRow.innerHTML = `<span>#${entry.position} ${FMT.escapeHtml(entry.name)}</span><span>${FMT.escapeHtml(FMT.phoneDisplay(entry.phone))}</span>`;
    li.appendChild(nameRow);

    const metaRow = document.createElement('div');
    metaRow.className = 'meta-row';
    const waitText =
      entry.projectedAt === null
        ? 'Wait unknown (no tables of this size)'
        : `~${FMT.durationWords(entry.projectedWaitMs)} wait · by ${FMT.clockTime(entry.projectedAt)}`;
    metaRow.textContent = `Party of ${entry.partySize} · ${waitText}`;
    li.appendChild(metaRow);

    const actions = document.createElement('div');
    actions.className = 'actions';

    const seatBtn = document.createElement('button');
    seatBtn.type = 'button';
    seatBtn.className = 'btn btn-small btn-primary';
    seatBtn.textContent = 'Seat';
    seatBtn.disabled = !selectedTableId;
    seatBtn.addEventListener('click', async () => {
      if (!selectedTableId) return;
      seatBtn.disabled = true;
      try {
        await API.seatFromQueue({ tableId: selectedTableId, queueEntryId: entry.id });
        selectedTableId = null;
        await renderHost();
      } catch (err) {
        alert(err.message || 'Could not seat this party.');
        await renderHost();
      }
    });
    actions.appendChild(seatBtn);

    const dismissBtn = document.createElement('button');
    dismissBtn.type = 'button';
    dismissBtn.className = 'btn btn-small btn-outline';
    dismissBtn.textContent = 'Dismiss';
    dismissBtn.addEventListener('click', async () => {
      dismissBtn.disabled = true;
      try {
        await API.dismissQueueEntry(entry.id);
        await renderHost();
      } catch (err) {
        alert(err.message || 'Could not dismiss this entry.');
        dismissBtn.disabled = false;
      }
    });
    actions.appendChild(dismissBtn);

    li.appendChild(actions);
    return li;
  }

  // ---------------- admin view ----------------

  const adminConfigBody = document.getElementById('admin-config-body');
  const btnSaveConfig = document.getElementById('btn-save-config');
  const saveStatus = document.getElementById('save-status');

  // Renders the form rows from a config, without touching the save-status
  // message -- callers decide whether this is a fresh view (clear it) or a
  // post-save refresh (leave the "Saved." message in place).
  async function renderAdminForm() {
    const config = await API.getConfig();
    adminConfigBody.innerHTML = '';
    for (const size of SIZES) {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${size}-Seat</td>
        <td><input type="number" min="0" step="1" data-field="count" data-size="${size}" value="${config.counts[size]}" /></td>
        <td><input type="number" min="1" step="1" data-field="turnover" data-size="${size}" value="${config.turnover[size]}" /></td>
      `;
      adminConfigBody.appendChild(row);
    }
  }

  async function renderAdmin() {
    try {
      await renderAdminForm();
    } catch (err) {
      showConnectionError(err);
      return;
    }
    hideConnectionError();
    saveStatus.textContent = '';
  }

  btnSaveConfig.addEventListener('click', async () => {
    const newConfig = { counts: {}, turnover: {} };
    for (const size of SIZES) {
      const countInput = adminConfigBody.querySelector(`input[data-field="count"][data-size="${size}"]`);
      const turnoverInput = adminConfigBody.querySelector(`input[data-field="turnover"][data-size="${size}"]`);
      newConfig.counts[size] = countInput.value;
      newConfig.turnover[size] = turnoverInput.value;
    }
    btnSaveConfig.disabled = true;
    try {
      await API.saveConfig(newConfig);
      await renderAdminForm();
      hideConnectionError();
      saveStatus.textContent = 'Saved.';
    } catch (err) {
      alert(err.message || 'Could not save changes.');
    } finally {
      btnSaveConfig.disabled = false;
    }
  });

  // ---------------- boot ----------------

  renderHost();
  refreshTimer = setInterval(() => {
    if (viewHost.classList.contains('active')) renderHost();
  }, window.SeatCuteConfig.HOST_REFRESH_INTERVAL_MS);
})();
