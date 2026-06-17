/**
 * Database Schema Studio — client application
 */
(function () {
  'use strict';

  const API = '/api/admin/schema-studio';
  let currentDb = 'app';
  let currentTable = null;
  let currentTab = 'structure';
  let dataPage = 1;
  let columnTypes = [];
  let network = null;

  const $ = (sel, ctx) => (ctx || document).querySelector(sel);
  const $$ = (sel, ctx) => [...(ctx || document).querySelectorAll(sel)];

  function toast(msg, type) {
    const el = $('#studioToast');
    if (!el) return;
    el.textContent = msg;
    el.className = 'studio-toast show ' + (type || 'success');
    setTimeout(() => el.classList.remove('show'), 4000);
  }

  async function api(path, opts) {
    const res = await fetch(API + path, {
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      credentials: 'same-origin',
      ...opts,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok && !data.error) data.error = res.statusText;
    return data;
  }

  function formatBytes(n) {
    if (n == null) return '—';
    if (n < 1024) return n + ' B';
    if (n < 1048576) return (n / 1024).toFixed(1) + ' KB';
    return (n / 1048576).toFixed(1) + ' MB';
  }

  function formatNum(n) {
    return (n ?? 0).toLocaleString();
  }

  // --- Navigation ---

  function switchPanel(name) {
    $$('.studio-nav-item').forEach((b) => b.classList.toggle('active', b.dataset.panel === name));
    $$('.studio-panel').forEach((p) => p.classList.toggle('active', p.id === 'panel-' + name));
    if (name === 'migrations' && currentDb === 'app') loadMigrations();
    if (name === 'activity') loadActivity();
    if (name === 'er') loadERDiagram();
    if (name === 'overview') loadOverview();
  }

  $$('.studio-nav-item').forEach((btn) => {
    btn.addEventListener('click', () => switchPanel(btn.dataset.panel));
  });

  // --- Database selector ---

  async function loadDatabases() {
    const data = await api('/databases');
    if (!data.success) {
      toast(data.error || 'Failed to load databases', 'error');
      return;
    }
    const sel = $('#dbSelector');
    const cards = $('#dbCards');
    if (sel) {
      sel.innerHTML = data.databases
        .map(
          (d) =>
            `<option value="${d.key}" ${d.key === currentDb ? 'selected' : ''}>${d.name} (${d.dialect})</option>`
        )
        .join('');
    }
    if (cards) {
      cards.innerHTML = data.databases
        .map(
          (d) => `
        <div class="studio-db-card" data-db="${d.key}">
          <h4>${escapeHtml(d.name)}</h4>
          <div class="meta">
            <span class="studio-badge ${d.status === 'connected' ? 'studio-badge-pk' : ''}">${d.status}</span>
            ${d.dialect} · ${d.table_count} tables
            ${d.is_external ? '<br><i class="fas fa-exclamation-triangle"></i> Production external DB' : ''}
          </div>
        </div>`
        )
        .join('');
      $$('.studio-db-card', cards).forEach((card) => {
        card.addEventListener('click', () => selectDatabase(card.dataset.db));
      });
    }
    updateConnectionStatus(data.databases.find((d) => d.key === currentDb));
    updateExternalWarning();
  }

  function selectDatabase(key) {
    currentDb = key;
    currentTable = null;
    const sel = $('#dbSelector');
    if (sel) sel.value = key;
    updateExternalWarning();
    loadOverview();
    loadTableTree();
    clearTableDetail();
    api('/databases').then((data) => {
      if (data.success) updateConnectionStatus(data.databases.find((d) => d.key === currentDb));
    });
  }

  function updateConnectionStatus(db) {
    const dot = $('#connDot');
    const label = $('#connLabel');
    if (!db || !dot) return;
    dot.className = 'studio-status-dot ' + (db.status === 'connected' ? 'connected' : 'disconnected');
    if (label) label.textContent = db.status === 'connected' ? 'Connected' : 'Disconnected';
  }

  function updateExternalWarning() {
    const banner = $('#externalWarning');
    if (banner) banner.classList.toggle('visible', currentDb !== 'app');
  }

  $('#dbSelector')?.addEventListener('change', (e) => selectDatabase(e.target.value));
  $('#refreshBtn')?.addEventListener('click', () => {
    loadDatabases();
    loadOverview();
    loadTableTree();
    if (currentTable) loadTableDetail(currentTable);
  });

  // --- Overview ---

  async function loadOverview() {
    const data = await api(`/${currentDb}/overview`);
    if (!data.success) return;
    const o = data.overview;
    $('#kpiTables').textContent = formatNum(o.table_count);
    $('#kpiRows').textContent = formatNum(o.total_rows);
    $('#kpiIndexes').textContent = formatNum(o.index_count);
    $('#kpiFks').textContent = formatNum(o.fk_count);
    $('#kpiSize').textContent = o.size_bytes != null ? formatBytes(o.size_bytes) : '—';
    $('#kpiMigration').textContent = o.migration_revision || '—';
    const migRow = $('#kpiMigrationRow');
    if (migRow) migRow.style.display = currentDb === 'app' ? '' : 'none';
  }

  // --- Table tree ---

  async function loadTableTree() {
    const search = $('#tableSearch')?.value || '';
    const data = await api(`/${currentDb}/tables?search=${encodeURIComponent(search)}`);
    const tree = $('#tableTree');
    if (!tree) return;
    if (!data.success) {
      tree.innerHTML = '<div class="studio-empty">Failed to load tables</div>';
      return;
    }
    if (!data.tables.length) {
      tree.innerHTML = '<div class="studio-empty">No tables found</div>';
      return;
    }
    tree.innerHTML = data.tables
      .map(
        (t) => `
      <div class="studio-tree-item ${t.name === currentTable ? 'selected' : ''}" data-table="${escapeAttr(t.name)}">
        <i class="fas fa-table text-indigo-400"></i>
        <span>${escapeHtml(t.name)}</span>
        <span class="row-count">${formatNum(t.row_count)}</span>
      </div>`
      )
      .join('');
    $$('.studio-tree-item', tree).forEach((item) => {
      item.addEventListener('click', () => {
        currentTable = item.dataset.table;
        $$('.studio-tree-item', tree).forEach((i) => i.classList.remove('selected'));
        item.classList.add('selected');
        loadTableDetail(currentTable);
        switchPanel('tables');
      });
    });
  }

  $('#tableSearch')?.addEventListener('input', debounce(loadTableTree, 300));

  function clearTableDetail() {
    $('#tableDetailTitle').textContent = 'Select a table';
    $('#structureBody').innerHTML = '';
    $('#dataHead').innerHTML = '';
    $('#dataBody').innerHTML = '';
    $('#indexesBody').innerHTML = '';
    $('#fksBody').innerHTML = '';
  }

  // --- Table detail ---

  async function loadTableDetail(name) {
    const data = await api(`/${currentDb}/tables/${encodeURIComponent(name)}`);
    if (!data.success) {
      toast(data.error || 'Failed to load table', 'error');
      return;
    }
    const t = data.table;
    columnTypes = t.column_types || [];
    $('#tableDetailTitle').textContent = t.name + ' (' + formatNum(t.row_count) + ' rows)';
    renderStructure(t);
    renderIndexes(t);
    renderFks(t);
    if (currentTab === 'data') loadTableData();
  }

  function renderStructure(t) {
    const body = $('#structureBody');
    if (!body) return;
    body.innerHTML = t.columns
      .map(
        (c) => `
      <tr>
        <td><strong>${escapeHtml(c.name)}</strong>
          ${t.primary_keys.includes(c.name) ? '<span class="studio-badge studio-badge-pk">PK</span>' : ''}
        </td>
        <td><code>${escapeHtml(c.type)}</code></td>
        <td>${c.nullable ? 'YES' : 'NO'}</td>
        <td>${escapeHtml(c.default ?? '—')}</td>
        <td>
          <button class="studio-btn studio-btn-sm" onclick="SchemaStudio.editColumn('${escapeAttr(c.name)}')">Edit</button>
          <button class="studio-btn studio-btn-sm studio-btn-danger" onclick="SchemaStudio.dropColumn('${escapeAttr(c.name)}')">Drop</button>
        </td>
      </tr>`
      )
      .join('');
  }

  function renderIndexes(t) {
    const body = $('#indexesBody');
    if (!body) return;
    if (!t.indexes.length) {
      body.innerHTML = '<tr><td colspan="3" class="studio-empty">No indexes</td></tr>';
      return;
    }
    body.innerHTML = t.indexes
      .map(
        (idx) => `
      <tr>
        <td>${escapeHtml(idx.name || '—')}</td>
        <td>${(idx.column_names || []).join(', ')}</td>
        <td>${idx.unique ? 'Yes' : 'No'}</td>
      </tr>`
      )
      .join('');
  }

  function renderFks(t) {
    const body = $('#fksBody');
    if (!body) return;
    if (!t.foreign_keys.length) {
      body.innerHTML = '<tr><td colspan="3" class="studio-empty">No foreign keys</td></tr>';
      return;
    }
    body.innerHTML = t.foreign_keys
      .map(
        (fk) => `
      <tr>
        <td>${(fk.constrained_columns || []).join(', ')}</td>
        <td>${escapeHtml(fk.referred_table || '')}</td>
        <td>${(fk.referred_columns || []).join(', ')}</td>
      </tr>`
      )
      .join('');
  }

  async function loadTableData() {
    if (!currentTable) return;
    const orderBy = $('#dataOrderBy')?.value || '';
    const data = await api(
      `/${currentDb}/tables/${encodeURIComponent(currentTable)}/rows?page=${dataPage}&per_page=50&order_by=${encodeURIComponent(orderBy)}`
    );
    if (!data.success) return;
    const head = $('#dataHead');
    const body = $('#dataBody');
    if (head) head.innerHTML = '<tr>' + data.columns.map((c) => `<th>${escapeHtml(c)}</th>`).join('') + '</tr>';
    if (body) {
      body.innerHTML = data.rows
        .map(
          (row) =>
            '<tr>' + data.columns.map((c) => `<td>${escapeHtml(String(row[c] ?? ''))}</td>`).join('') + '</tr>'
        )
        .join('');
    }
    const pag = $('#dataPagination');
    if (pag) {
      pag.innerHTML = `
        <button class="studio-btn studio-btn-sm" ${dataPage <= 1 ? 'disabled' : ''} onclick="SchemaStudio.prevPage()">Prev</button>
        <span>Page ${data.page} / ${data.total_pages} (${formatNum(data.total)} rows)</span>
        <button class="studio-btn studio-btn-sm" ${dataPage >= data.total_pages ? 'disabled' : ''} onclick="SchemaStudio.nextPage()">Next</button>`;
    }
  }

  $$('.studio-tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      currentTab = tab.dataset.tab;
      $$('.studio-tab').forEach((t) => t.classList.toggle('active', t.dataset.tab === currentTab));
      $$('.studio-tab-pane').forEach((p) => p.classList.toggle('active', p.id === 'tab-' + currentTab));
      if (currentTab === 'data' && currentTable) loadTableData();
    });
  });

  // --- SQL Console ---

  $('#runSqlBtn')?.addEventListener('click', async () => {
    const query = $('#sqlEditor')?.value || '';
    const allowWrite = $('#sqlAllowWrite')?.checked || false;
    const result = await api(`/${currentDb}/query`, {
      method: 'POST',
      body: JSON.stringify({ query, allow_write: allowWrite }),
    });
    const out = $('#sqlResults');
    if (!out) return;
    if (!result.success) {
      out.innerHTML = `<div class="text-red-600 p-3">${escapeHtml(result.error)}</div>`;
      return;
    }
    if (result.type === 'select') {
      const cols = result.columns || [];
      out.innerHTML = `
        <p class="text-sm text-slate-500 p-2">${result.row_count} rows in ${result.execution_time?.toFixed(3)}s</p>
        <div style="overflow:auto;max-height:400px">
          <table class="studio-table"><thead><tr>${cols.map((c) => `<th>${escapeHtml(c)}</th>`).join('')}</tr></thead>
          <tbody>${(result.data || []).map((row) => '<tr>' + cols.map((c) => `<td>${escapeHtml(String(row[c] ?? ''))}</td>`).join('') + '</tr>').join('')}</tbody></table>
        </div>`;
    } else {
      out.innerHTML = `<div class="p-3 text-emerald-700">Affected ${result.affected_rows} rows (${result.execution_time?.toFixed(3)}s)</div>`;
    }
  });

  // --- ER Diagram ---

  async function loadERDiagram() {
    const data = await api(`/${currentDb}/relations`);
    const container = $('#erCanvas');
    if (!container || !data.success) return;

    if (typeof vis === 'undefined') {
      container.innerHTML = '<div class="studio-empty">vis-network library not loaded</div>';
      return;
    }

    const nodes = new vis.DataSet(
      (data.nodes || []).map((n) => ({
        id: n.id,
        label: n.label,
        shape: 'box',
        color: { background: '#eef2ff', border: '#4f46e5' },
        font: { size: 12 },
      }))
    );
    const edges = new vis.DataSet(
      (data.edges || []).map((e, i) => ({
        id: i,
        from: e.from,
        to: e.to,
        arrows: 'to',
        label: e.label,
        font: { size: 10, align: 'middle' },
      }))
    );

    if (network) network.destroy();
    network = new vis.Network(
      container,
      { nodes, edges },
      {
        layout: { hierarchical: { direction: 'UD', sortMethod: 'directed' } },
        physics: { enabled: false },
        interaction: { hover: true },
      }
    );
    network.on('click', (params) => {
      if (params.nodes.length) {
        currentTable = params.nodes[0];
        loadTableDetail(currentTable);
        switchPanel('tables');
        loadTableTree();
      }
    });
  }

  // --- Migrations ---

  async function loadMigrations() {
    if (currentDb !== 'app') {
      $('#migrationsPanel').innerHTML = '<div class="studio-empty">Migrations are only available for the application database.</div>';
      return;
    }
    const status = await api('/app/migrations/status');
    const panel = $('#migrationsContent');
    if (!panel) return;

    const healthy = status.is_healthy;
    panel.innerHTML = `
      <div class="studio-mig-status ${healthy ? 'healthy' : 'unhealthy'}">
        <strong>Revision:</strong> ${escapeHtml(status.current_revision || 'none')}
        · <strong>Heads:</strong> ${(status.head_revisions || []).join(', ') || '—'}
        · <strong>Pending:</strong> ${(status.pending_revisions || []).length}
      </div>
      <div class="flex flex-wrap gap-2 mb-4">
        <button class="studio-btn studio-btn-primary" onclick="SchemaStudio.migUpgrade('all')">Upgrade all</button>
        <button class="studio-btn" onclick="SchemaStudio.migUpgrade('next')">Apply next</button>
        <button class="studio-btn" onclick="SchemaStudio.migGenerate()">Generate migration</button>
        <button class="studio-btn" onclick="SchemaStudio.migPreflight()">Preflight</button>
        <button class="studio-btn studio-btn-danger" onclick="SchemaStudio.migDowngrade()">Downgrade one</button>
      </div>
      <h4 class="font-bold text-sm mb-2">Pending migrations</h4>
      <table class="studio-table mb-4"><thead><tr><th>Revision</th><th>Message</th></tr></thead>
      <tbody>${(status.pending_revisions || []).map((r) => `<tr><td><code>${escapeHtml(r.revision)}</code></td><td>${escapeHtml(r.message || '')}</td></tr>`).join('') || '<tr><td colspan="2">None</td></tr>'}</tbody></table>
      <div id="migPreflightResult"></div>`;

    const hist = await api('/app/migrations/history?limit=10');
    if (hist.revisions) {
      panel.innerHTML += `
        <h4 class="font-bold text-sm mb-2 mt-4">Recent history</h4>
        <table class="studio-table"><thead><tr><th>Revision</th><th>Message</th></tr></thead>
        <tbody>${hist.revisions.map((r) => `<tr><td><code>${escapeHtml(r.revision)}</code></td><td>${escapeHtml(r.message || '')}</td></tr>`).join('')}</tbody></table>`;
    }
  }

  async function migUpgrade(mode) {
    if (!confirm('Apply migrations? This modifies the application database.')) return;
    const res = await api('/app/migrations/upgrade', {
      method: 'POST',
      body: JSON.stringify({ confirm: true, mode }),
    });
    toast(res.success ? res.message || 'Upgrade complete' : res.error, res.success ? 'success' : 'error');
    loadMigrations();
    loadOverview();
  }

  async function migDowngrade() {
    if (!confirm('Downgrade one migration step?')) return;
    const res = await api('/app/migrations/downgrade', {
      method: 'POST',
      body: JSON.stringify({ confirm: true, mode: 'one' }),
    });
    toast(res.success ? 'Downgrade complete' : res.error, res.success ? 'success' : 'error');
    loadMigrations();
  }

  async function migGenerate() {
    const message = prompt('Migration message:', 'Schema studio autogenerate');
    if (!message) return;
    const res = await api('/app/migrations/generate', {
      method: 'POST',
      body: JSON.stringify({ confirm: true, message }),
    });
    toast(res.success ? res.message : res.error, res.success ? 'success' : 'error');
    loadMigrations();
  }

  async function migPreflight() {
    const res = await api('/app/migrations/preflight');
    const el = $('#migPreflightResult');
    if (!el) return;
    const issues = res.issues || [];
    el.innerHTML = `<h4 class="font-bold text-sm mb-2">Preflight</h4>
      <p class="text-sm mb-2">${escapeHtml(res.summary || '')}</p>
      ${issues.length ? '<ul class="text-sm">' + issues.map((i) => `<li>${escapeHtml(i.message || JSON.stringify(i))}</li>`).join('') + '</ul>' : '<p class="text-sm text-emerald-600">No issues detected</p>'}`;
  }

  // --- Activity ---

  async function loadActivity() {
    const data = await api('/activity?limit=50');
    const el = $('#activityList');
    if (!el || !data.success) return;
    if (!data.activity.length) {
      el.innerHTML = '<div class="studio-empty">No DDL activity yet</div>';
      return;
    }
    el.innerHTML = data.activity
      .map(
        (a) => `
      <div class="studio-activity-item">
        <div><strong>${escapeHtml(a.action)}</strong> on <code>${escapeHtml(a.db_key)}</code> — ${escapeHtml(a.label || '')}</div>
        <div class="time">${escapeHtml(a.occurred_at || '')} · ${escapeHtml(a.actor || 'system')}</div>
      </div>`
      )
      .join('');
  }

  // --- Modals / DDL ---

  function openModal(id) {
    $(`#${id}`)?.classList.add('open');
  }
  function closeModal(id) {
    $(`#${id}`)?.classList.remove('open');
  }

  $$('[data-close-modal]').forEach((btn) => {
    btn.addEventListener('click', () => closeModal(btn.dataset.closeModal));
  });

  $('#btnCreateTable')?.addEventListener('click', () => {
    $('#createTableName').value = '';
    $('#createTableColumns').innerHTML = '';
    addColumnRow();
    loadColumnTypesForModal();
    openModal('createTableModal');
  });

  async function loadColumnTypesForModal() {
    const data = await api(`/${currentDb}/column-types`);
    columnTypes = data.types || ['TEXT', 'INTEGER'];
    $$('.col-type-select').forEach((sel) => {
      const val = sel.value;
      sel.innerHTML = columnTypes.map((t) => `<option value="${escapeAttr(t)}">${escapeHtml(t)}</option>`).join('');
      if (val) sel.value = val;
    });
  }

  function addColumnRow() {
    const wrap = $('#createTableColumns');
    if (!wrap) return;
    const row = document.createElement('div');
    row.className = 'studio-col-row';
    row.innerHTML = `
      <div class="studio-form-group" style="margin:0"><label>Name</label><input type="text" class="col-name" placeholder="column_name"></div>
      <div class="studio-form-group" style="margin:0"><label>Type</label><select class="col-type-select">${columnTypes.map((t) => `<option>${escapeHtml(t)}</option>`).join('')}</select></div>
      <div class="studio-form-group" style="margin:0"><label>PK</label><input type="checkbox" class="col-pk"></div>
      <div class="studio-form-group" style="margin:0"><label>Null</label><input type="checkbox" class="col-null" checked></div>
      <button type="button" class="studio-btn studio-btn-sm studio-btn-danger" onclick="this.parentElement.remove()"><i class="fas fa-times"></i></button>`;
    wrap.appendChild(row);
  }

  $('#btnAddColumnRow')?.addEventListener('click', addColumnRow);

  $('#btnPreviewCreateTable')?.addEventListener('click', async () => {
    const payload = buildCreateTablePayload();
    const res = await api(`/${currentDb}/ddl/preview`, {
      method: 'POST',
      body: JSON.stringify({ operation: 'create_table', ...payload }),
    });
    $('#createTableSqlPreview').textContent = res.sql || res.error || '';
  });

  $('#btnSubmitCreateTable')?.addEventListener('click', async () => {
    const payload = buildCreateTablePayload();
    payload.confirm = true;
    payload.confirmation_text = `${currentDb}.${payload.name}`;
    const res = await api(`/${currentDb}/tables`, { method: 'POST', body: JSON.stringify(payload) });
    toast(res.success ? 'Table created' : res.error, res.success ? 'success' : 'error');
    if (res.success) {
      closeModal('createTableModal');
      loadTableTree();
      loadOverview();
    }
  });

  function buildCreateTablePayload() {
    const name = $('#createTableName')?.value?.trim();
    const columns = [];
    $$('#createTableColumns .studio-col-row').forEach((row) => {
      const n = $('.col-name', row)?.value?.trim();
      if (!n) return;
      columns.push({
        name: n,
        type: $('.col-type-select', row)?.value || 'TEXT',
        primary_key: $('.col-pk', row)?.checked || false,
        nullable: $('.col-null', row)?.checked !== false,
      });
    });
    return { name, columns };
  }

  $('#btnAddColumn')?.addEventListener('click', async () => {
    if (!currentTable) return toast('Select a table first', 'error');
    const types = await api(`/${currentDb}/column-types`);
    columnTypes = types.types || [];
    $('#addColName').value = '';
    $('#addColType').innerHTML = columnTypes.map((t) => `<option>${escapeHtml(t)}</option>`).join('');
    openModal('addColumnModal');
  });

  $('#btnSubmitAddColumn')?.addEventListener('click', async () => {
    const column = {
      name: $('#addColName')?.value?.trim(),
      type: $('#addColType')?.value,
      nullable: $('#addColNullable')?.checked !== false,
    };
    const res = await api(`/${currentDb}/tables/${encodeURIComponent(currentTable)}/columns`, {
      method: 'POST',
      body: JSON.stringify({
        column,
        confirm: true,
        confirmation_text: `${currentDb}.${currentTable}`,
      }),
    });
    toast(res.success ? 'Column added' : res.error, res.success ? 'success' : 'error');
    if (res.success) {
      closeModal('addColumnModal');
      loadTableDetail(currentTable);
    }
  });

  function editColumn(name) {
    $('#editColName').value = name;
    $('#editColNewName').value = name;
    openModal('editColumnModal');
    api(`/${currentDb}/column-types`).then((d) => {
      columnTypes = d.types || [];
      $('#editColType').innerHTML = columnTypes.map((t) => `<option>${escapeHtml(t)}</option>`).join('');
    });
  }

  $('#btnSubmitEditColumn')?.addEventListener('click', async () => {
    const name = $('#editColName')?.value;
    const res = await api(
      `/${currentDb}/tables/${encodeURIComponent(currentTable)}/columns/${encodeURIComponent(name)}`,
      {
        method: 'PATCH',
        body: JSON.stringify({
          changes: {
            type: $('#editColType')?.value,
            nullable: $('#editColNullable')?.checked,
          },
          confirm: true,
          confirmation_text: `${currentDb}.${currentTable}`,
        }),
      }
    );
    toast(res.success ? 'Column updated' : res.error, res.success ? 'success' : 'error');
    if (res.success) {
      closeModal('editColumnModal');
      loadTableDetail(currentTable);
    }
  });

  function dropColumn(name) {
    $('#dropTargetLabel').textContent = `DROP ${currentDb}.${currentTable}.${name}`;
    $('#dropConfirmInput').value = '';
    $('#dropConfirmInput').dataset.action = 'drop_column';
    $('#dropConfirmInput').dataset.column = name;
    openModal('dangerModal');
  }

  $('#btnDropTable')?.addEventListener('click', () => {
    if (!currentTable) return;
    $('#dropTargetLabel').textContent = `DROP ${currentDb}.${currentTable}`;
    $('#dropConfirmInput').value = '';
    $('#dropConfirmInput').dataset.action = 'drop_table';
    openModal('dangerModal');
  });

  $('#btnConfirmDanger')?.addEventListener('click', async () => {
    const expected = $('#dropTargetLabel')?.textContent?.replace('DROP ', '') || '';
    const typed = $('#dropConfirmInput')?.value?.trim();
    const action = $('#dropConfirmInput')?.dataset.action;
    if (typed !== expected && typed !== `DROP ${expected}`) {
      toast('Confirmation text does not match', 'error');
      return;
    }
    let res;
    if (action === 'drop_table') {
      res = await api(`/${currentDb}/tables/${encodeURIComponent(currentTable)}`, {
        method: 'DELETE',
        body: JSON.stringify({ confirm: true, confirmation_text: `DROP ${currentDb}.${currentTable}` }),
      });
    } else {
      const col = $('#dropConfirmInput')?.dataset.column;
      res = await api(
        `/${currentDb}/tables/${encodeURIComponent(currentTable)}/columns/${encodeURIComponent(col)}`,
        {
          method: 'DELETE',
          body: JSON.stringify({
            confirm: true,
            confirmation_text: `DROP ${currentDb}.${currentTable}.${col}`,
          }),
        }
      );
    }
    toast(res.success ? 'Done' : res.error, res.success ? 'success' : 'error');
    if (res.success) {
      closeModal('dangerModal');
      currentTable = null;
      clearTableDetail();
      loadTableTree();
      loadOverview();
    }
  });

  // --- Utils ---

  function escapeHtml(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }
  function escapeAttr(s) {
    return String(s).replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function debounce(fn, ms) {
    let t;
    return (...args) => {
      clearTimeout(t);
      t = setTimeout(() => fn(...args), ms);
    };
  }

  function prevPage() {
    if (dataPage > 1) {
      dataPage--;
      loadTableData();
    }
  }
  function nextPage() {
    dataPage++;
    loadTableData();
  }

  window.SchemaStudio = {
    editColumn,
    dropColumn,
    prevPage,
    nextPage,
    loadData: loadTableData,
    migUpgrade,
    migDowngrade,
    migGenerate,
    migPreflight,
  };

  // Init
  loadDatabases().then(() => {
    loadOverview();
    loadTableTree();
  });
})();
