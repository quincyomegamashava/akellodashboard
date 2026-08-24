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
  let aceEditor = null;
  let externalDdlAllowed = true;
  let migStatusCache = null;
  let migDiagnosticsCache = null;
  let migPreflightCache = null;
  let migConfirmCallback = null;

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
    if (name === 'sql') initAceEditor();
    if (name === 'migrations' && currentDb === 'app') loadMigrations();
    if (name === 'activity') loadActivity();
    if (name === 'er') loadERDiagram();
    if (name === 'overview') loadOverview();
  }

  function initAceEditor() {
    if (aceEditor || typeof ace === 'undefined') return;
    const el = $('#sqlEditorAce');
    if (!el) return;
    aceEditor = ace.edit('sqlEditorAce');
    aceEditor.setTheme('ace/theme/github');
    aceEditor.session.setMode('ace/mode/sql');
    aceEditor.setValue('SELECT * FROM user LIMIT 10;', -1);
    aceEditor.setOptions({ fontSize: '14px', showPrintMargin: false });
  }

  function getSqlQuery() {
    if (aceEditor) return aceEditor.getValue();
    return $('#sqlEditor')?.value || '';
  }

  function applyDdlUiState() {
    const wrap = $('#panel-tables');
    const blocked = currentDb !== 'app' && !externalDdlAllowed;
    if (wrap) wrap.classList.toggle('studio-ddl-disabled', blocked);
    $$('.studio-ddl-action').forEach((el) => {
      el.disabled = blocked;
    });
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
    const cur = data.databases.find((d) => d.key === currentDb);
    externalDdlAllowed = cur ? cur.external_ddl_allowed !== false : true;
    updateExternalWarning();
    applyDdlUiState();
  }

  function selectDatabase(key) {
    currentDb = key;
    currentTable = null;
    const sel = $('#dbSelector');
    if (sel) sel.value = key;
    api('/databases').then((data) => {
      if (data.success) {
        const cur = data.databases.find((d) => d.key === currentDb);
        updateConnectionStatus(cur);
        externalDdlAllowed = cur ? cur.external_ddl_allowed !== false : true;
        updateExternalWarning();
        applyDdlUiState();
      }
    });
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
    const blocked = $('#externalDdlBlocked');
    if (banner) {
      banner.classList.toggle('visible', currentDb !== 'app');
      if (currentDb !== 'app') {
        banner.innerHTML =
          '<i class="fas fa-exclamation-triangle"></i> You are viewing an <strong>external production database</strong>. DDL changes are irreversible.';
      }
    }
    if (blocked) blocked.classList.toggle('visible', currentDb !== 'app' && !externalDdlAllowed);
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
    const rowsEl = $('#kpiRows');
    if (rowsEl) {
      rowsEl.textContent = o.total_rows == null ? '—' : (o.row_count_approximate ? '~' : '') + formatNum(o.total_rows);
    }
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
    const data = await api(`/${currentDb}/tables?search=${encodeURIComponent(search)}&include_counts=false`);
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
        <span class="row-count">${t.row_count != null ? formatNum(t.row_count) : ''}</span>
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
        <td>${idx.name ? `<button class="studio-btn studio-btn-sm studio-btn-danger studio-ddl-action" onclick="SchemaStudio.dropIndex('${escapeAttr(idx.name)}')">Drop</button>` : ''}</td>
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
    const filter = $('#dataFilter')?.value || '';
    let url = `/${currentDb}/tables/${encodeURIComponent(currentTable)}/rows?page=${dataPage}&per_page=50&order_by=${encodeURIComponent(orderBy)}`;
    if (filter) url += `&filter=${encodeURIComponent(filter)}`;
    const data = await api(url);
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
    const query = getSqlQuery();
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
    const prefix = $('#erPrefixFilter')?.value || '';
    const data = await api(`/${currentDb}/relations?prefix=${encodeURIComponent(prefix)}`);
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

  $('#erPrefixFilter')?.addEventListener('input', debounce(loadERDiagram, 400));

  $('#btnExportCsv')?.addEventListener('click', () => {
    if (!currentTable) return toast('Select a table first', 'error');
    window.location.href = `${API}/${currentDb}/tables/${encodeURIComponent(currentTable)}/export`;
  });

  function showMigConfirm(title, message, callback) {
    $('#migConfirmTitle').textContent = title;
    $('#migConfirmMessage').textContent = message;
    $('#migConfirmInput').value = '';
    migConfirmCallback = callback;
    openModal('migConfirmModal');
  }

  $('#btnMigConfirm')?.addEventListener('click', async () => {
    if ($('#migConfirmInput')?.value?.trim() !== 'MIGRATE') {
      toast('Type MIGRATE to confirm', 'error');
      return;
    }
    closeModal('migConfirmModal');
    if (migConfirmCallback) await migConfirmCallback();
    migConfirmCallback = null;
  });

  function afterDdlSuccess(res) {
    if (res.suggest_generate_migration) openModal('migrationNudgeModal');
    loadTableTree();
    loadOverview();
  }

  $('#btnNudgeGenerate')?.addEventListener('click', () => {
    closeModal('migrationNudgeModal');
    migGenerate();
  });

  async function loadMigrations() {
    if (currentDb !== 'app') {
      $('#migrationsContent').innerHTML = '<div class="studio-empty">Migrations are only available for the application database.</div>';
      return;
    }
    const [status, diagnostics, health] = await Promise.all([
      api('/app/migrations/status'),
      api('/app/migrations/diagnostics'),
      api('/app/migrations/health'),
    ]);
    migStatusCache = status;
    migDiagnosticsCache = diagnostics;
    const panel = $('#migrationsContent');
    if (!panel) return;

    const healthy = status.is_healthy;
    const pending = status.pending_revisions || [];
    panel.innerHTML = `
      <div class="studio-mig-status ${healthy ? 'healthy' : 'unhealthy'}">
        <strong>Revision:</strong> ${escapeHtml(status.current_revision || 'none')}
        · <strong>Pending:</strong> ${pending.length}
        · <strong>Healthy:</strong> ${healthy ? 'Yes' : 'No'}
      </div>
      <div id="migHealthRecs" class="text-sm mb-3"></div>
      <div class="flex flex-wrap gap-2 mb-4">
        <button class="studio-btn studio-btn-primary" id="migBtnUpgradeAll">Upgrade all</button>
        <button class="studio-btn" id="migBtnUpgradeNext">Apply next</button>
        <button class="studio-btn" id="migBtnGenerate">Generate migration</button>
        <button class="studio-btn" id="migBtnPreflight">Preflight</button>
        <button class="studio-btn" id="migBtnFix">Fix migrations</button>
        <button class="studio-btn" id="migBtnMerge">Merge heads</button>
        <button class="studio-btn" id="migBtnRepair">Repair chain</button>
        <button class="studio-btn" id="migBtnAlign">Align schema</button>
        <button class="studio-btn" id="migBtnSync">Sync revision</button>
        <button class="studio-btn studio-btn-danger" id="migBtnDowngrade">Downgrade one</button>
      </div>
      <h4 class="font-bold text-sm mb-2">Pending migrations</h4>
      <table class="studio-table mb-4"><thead><tr><th>Revision</th><th>Message</th></tr></thead>
      <tbody>${pending.map((r) => `<tr><td><code>${escapeHtml(r.revision)}</code></td><td>${escapeHtml(r.message || '')}</td></tr>`).join('') || '<tr><td colspan="2">None</td></tr>'}</tbody></table>
      <div id="migPreflightResult"></div>
      <div id="migResult" class="studio-sql-preview mt-3 hidden"></div>
      <div id="migHistory"></div>`;

    const recs = health.recommendations || [];
    const recEl = $('#migHealthRecs');
    if (recEl && recs.length) {
      recEl.innerHTML = recs.map((r) => `<div class="mb-1"><strong>${escapeHtml(r.title || '')}</strong>: ${escapeHtml(r.message || '')}</div>`).join('');
    }

    $('#migBtnUpgradeAll')?.addEventListener('click', () => showMigConfirm('Upgrade all', 'Apply all pending migrations to the application database.', () => migUpgrade('all')));
    $('#migBtnUpgradeNext')?.addEventListener('click', () => showMigConfirm('Apply next', 'Apply the next pending migration only.', () => migUpgrade('next')));
    $('#migBtnGenerate')?.addEventListener('click', () => migGenerate());
    $('#migBtnPreflight')?.addEventListener('click', () => migPreflight());
    $('#migBtnDowngrade')?.addEventListener('click', () => showMigConfirm('Downgrade', 'Roll back one migration revision.', () => migDowngrade()));
    $('#migBtnFix')?.addEventListener('click', () => showMigConfirm('Fix migrations', 'Run full migration recovery (backup, orphans, merge, upgrade).', () => migFix()));
    $('#migBtnMerge')?.addEventListener('click', () => showMigConfirm('Merge heads', 'Merge multiple Alembic heads into one.', () => migMerge()));
    $('#migBtnRepair')?.addEventListener('click', () => {
      const suggested = diagnostics.inferred_stamp_revision || diagnostics.current_revision || status.current_revision || '';
      const rev = prompt('Stamp revision for repair:', suggested);
      if (!rev) return;
      showMigConfirm('Repair chain', `Repair migration chain and stamp to ${rev}.`, () => migRepair(rev));
    });
    $('#migBtnAlign')?.addEventListener('click', () => showMigConfirm('Align schema', 'Stamp DB to match current schema then upgrade.', () => migAlign()));
    $('#migBtnSync')?.addEventListener('click', () => showMigConfirm('Sync revision', 'Update alembic_version when schema already matches.', () => migSync()));

    updateMigActionButtons(status, diagnostics);
    await migPreflight();

    const hist = await api('/app/migrations/history?limit=10');
    const histEl = $('#migHistory');
    if (histEl && hist.revisions) {
      histEl.innerHTML = `
        <h4 class="font-bold text-sm mb-2 mt-4">Recent history</h4>
        <table class="studio-table"><thead><tr><th>Revision</th><th>Message</th></tr></thead>
        <tbody>${hist.revisions.map((r) => `<tr><td><code>${escapeHtml(r.revision)}</code></td><td>${escapeHtml(r.message || '')}</td></tr>`).join('')}</tbody></table>`;
    }
  }

  function setMigBtnState(id, { hidden = false, disabled = false, title = '' } = {}) {
    const btn = $(id);
    if (!btn) return;
    btn.classList.toggle('hidden', hidden);
    btn.disabled = disabled;
    btn.title = title || '';
  }

  function updateMigActionButtons(status, diagnostics) {
    const enabled = !!(status && status.web_migrations_enabled !== false);
    const needsRepair = !!(status && (status.needs_repair || status.chain_broken));
    const multipleHeads = !!(status && status.multiple_heads) || !!(diagnostics && diagnostics.multiple_heads);
    const hasOrphans = !!(status && status.has_orphan_files) || !!(diagnostics && diagnostics.has_orphan_files);
    const pendingCount = (status && status.pending_count) || 0;
    const preflightReady = !migPreflightCache || migPreflightCache.ready !== false;
    const canSync = !!(status && status.can_sync) || !!(migPreflightCache && migPreflightCache.can_sync);
    const canAlign = !!(status && status.can_align_schema);
    const canDowngrade = !!(status && status.can_downgrade);
    const showFix = needsRepair || multipleHeads || hasOrphans;
    const upgradeBlocked = !enabled || !status || status.is_up_to_date || pendingCount === 0 || needsRepair || !preflightReady;

    setMigBtnState('#migBtnFix', {
      hidden: !showFix,
      disabled: !enabled || !showFix,
    });
    setMigBtnState('#migBtnMerge', {
      hidden: !multipleHeads,
      disabled: !enabled || !multipleHeads || hasOrphans,
      title: hasOrphans ? 'Remove orphan migration files first (use Fix migrations)' : '',
    });
    setMigBtnState('#migBtnRepair', {
      hidden: !(needsRepair && !multipleHeads),
      disabled: !enabled || !needsRepair || multipleHeads,
    });
    setMigBtnState('#migBtnUpgradeAll', {
      disabled: upgradeBlocked,
      title: !preflightReady ? 'Resolve preflight blockers before applying.' : '',
    });
    setMigBtnState('#migBtnUpgradeNext', {
      disabled: upgradeBlocked,
      title: !preflightReady ? 'Resolve preflight blockers before applying.' : '',
    });
    setMigBtnState('#migBtnSync', {
      hidden: !canSync,
      disabled: !enabled || !canSync || needsRepair,
    });
    setMigBtnState('#migBtnAlign', {
      hidden: !canAlign,
      disabled: !enabled || !canAlign || needsRepair,
    });
    setMigBtnState('#migBtnDowngrade', {
      hidden: !canDowngrade,
      disabled: !enabled || !canDowngrade || needsRepair,
    });
    setMigBtnState('#migBtnGenerate', { disabled: !enabled });
    setMigBtnState('#migBtnPreflight', { disabled: false });
  }

  async function migPost(path, body, okMsg) {
    const res = await api(path, { method: 'POST', body: JSON.stringify({ confirm: true, ...body }) });
    const el = $('#migResult');
    if (el) {
      el.classList.remove('hidden');
      el.textContent = res.success ? (res.message || okMsg) : (res.error || 'Failed');
    }
    toast(res.success ? (res.message || okMsg) : res.error, res.success ? 'success' : 'error');
    loadMigrations();
    loadOverview();
    return res;
  }

  async function migUpgrade(mode) {
    await migPost('/app/migrations/upgrade', { mode }, 'Upgrade complete');
  }

  async function migDowngrade() {
    await migPost('/app/migrations/downgrade', { mode: 'one' }, 'Downgrade complete');
  }

  async function migFix() {
    await migPost('/app/migrations/fix', { merge_heads: true, run_upgrade_after: true }, 'Fix complete');
  }

  async function migMerge() {
    await migPost('/app/migrations/merge', {}, 'Merge complete');
  }

  async function migRepair(stampRevision) {
    await migPost('/app/migrations/repair', { stamp_revision: stampRevision }, 'Repair complete');
  }

  async function migAlign() {
    await migPost('/app/migrations/align-schema', {}, 'Align complete');
  }

  async function migSync() {
    await migPost('/app/migrations/sync', {}, 'Sync complete');
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
    migPreflightCache = res;
    updateMigActionButtons(migStatusCache, migDiagnosticsCache);
    const el = $('#migPreflightResult');
    if (!el) return res;
    if (!res.success) {
      el.innerHTML = `<h4 class="font-bold text-sm mb-2">Preflight</h4>
        <p class="text-sm text-rose-600">${escapeHtml(res.error || 'Could not run preflight checks.')}</p>`;
      return res;
    }
    const findings = res.findings || [];
    const severityClass = {
      blocker: 'text-rose-700 font-bold',
      warning: 'text-amber-700 font-semibold',
      info: 'text-slate-600',
    };
    const rows = findings.length
      ? findings.map((item) => {
          const severity = item.severity || 'info';
          return `<tr><td class="${severityClass[severity] || 'text-slate-600'}">${escapeHtml(severity)}</td>
            <td><code>${escapeHtml(item.revision || '')}</code></td>
            <td>${escapeHtml(item.message || '')}</td></tr>`;
        }).join('')
      : '<tr><td colspan="3" class="text-emerald-700">No issues detected for pending migrations.</td></tr>';
    el.innerHTML = `<h4 class="font-bold text-sm mb-2">Preflight</h4>
      <p class="text-sm mb-2">${escapeHtml(res.message || 'Preflight complete.')}</p>
      <table class="studio-table"><thead><tr><th>Severity</th><th>Revision</th><th>Details</th></tr></thead>
      <tbody>${rows}</tbody></table>`;
    return res;
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
        (a, i) => `
      <div class="studio-activity-item" data-idx="${i}" style="cursor:pointer">
        <div><strong>${escapeHtml(a.action)}</strong> on <code>${escapeHtml(a.db_key)}</code> — ${escapeHtml(a.label || '')}</div>
        <div class="time">${escapeHtml(a.occurred_at || '')} · ${escapeHtml(a.actor || 'system')}</div>
        <pre class="studio-activity-sql">${escapeHtml((a.snapshot && (a.snapshot.sql || a.snapshot.query)) || '')}</pre>
      </div>`
      )
      .join('');
    if (data.audit_log_url) {
      const link = $('#auditLogLink');
      if (link) link.href = data.audit_log_url + '?entity_type=schema_ddl';
    }
    $$('.studio-activity-item', el).forEach((item) => {
      item.addEventListener('click', () => item.classList.toggle('expanded'));
    });
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
    if (!externalDdlAllowed && currentDb !== 'app') return toast('External DDL disabled', 'error');
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
      afterDdlSuccess(res);
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
      if (res.suggest_generate_migration) openModal('migrationNudgeModal');
    }
  });

  $('#btnRenameTable')?.addEventListener('click', () => {
    if (!currentTable) return toast('Select a table first', 'error');
    $('#renameTableNewName').value = currentTable;
    openModal('renameTableModal');
  });

  $('#btnSubmitRenameTable')?.addEventListener('click', async () => {
    const newName = $('#renameTableNewName')?.value?.trim();
    const res = await api(`/${currentDb}/tables/${encodeURIComponent(currentTable)}`, {
      method: 'PATCH',
      body: JSON.stringify({
        new_name: newName,
        confirm: true,
        confirmation_text: `RENAME ${currentDb}.${currentTable}`,
      }),
    });
    toast(res.success ? 'Table renamed' : res.error, res.success ? 'success' : 'error');
    if (res.success) {
      closeModal('renameTableModal');
      currentTable = newName;
      afterDdlSuccess(res);
      loadTableDetail(currentTable);
    }
  });

  $('#btnAddIndex')?.addEventListener('click', () => {
    if (!currentTable) return;
    $('#indexName').value = '';
    $('#indexColumns').value = '';
    openModal('addIndexModal');
  });

  $('#btnSubmitAddIndex')?.addEventListener('click', async () => {
    const columns = ($('#indexColumns')?.value || '').split(',').map((s) => s.trim()).filter(Boolean);
    const res = await api(`/${currentDb}/tables/${encodeURIComponent(currentTable)}/indexes`, {
      method: 'POST',
      body: JSON.stringify({
        name: $('#indexName')?.value?.trim(),
        columns,
        unique: $('#indexUnique')?.checked || false,
        confirm: true,
        confirmation_text: `${currentDb}.${currentTable}`,
      }),
    });
    toast(res.success ? 'Index created' : res.error, res.success ? 'success' : 'error');
    if (res.success) {
      closeModal('addIndexModal');
      loadTableDetail(currentTable);
      afterDdlSuccess(res);
    }
  });

  function dropIndex(name) {
    $('#dropTargetLabel').textContent = `DROP INDEX ${currentDb}.${currentTable}.${name}`;
    $('#dropConfirmInput').value = '';
    $('#dropConfirmInput').dataset.action = 'drop_index';
    $('#dropConfirmInput').dataset.indexName = name;
    openModal('dangerModal');
  }

  $('#btnAddFk')?.addEventListener('click', () => {
    if (!currentTable) return;
    openModal('addFkModal');
  });

  $('#btnSubmitAddFk')?.addEventListener('click', async () => {
    const res = await api(`/${currentDb}/tables/${encodeURIComponent(currentTable)}/foreign-keys`, {
      method: 'POST',
      body: JSON.stringify({
        name: $('#fkName')?.value?.trim(),
        columns: ($('#fkLocalCols')?.value || '').split(',').map((s) => s.trim()).filter(Boolean),
        referred_table: $('#fkRefTable')?.value?.trim(),
        referred_columns: ($('#fkRefCols')?.value || '').split(',').map((s) => s.trim()).filter(Boolean),
        on_delete: $('#fkOnDelete')?.value || 'NO ACTION',
        confirm: true,
        confirmation_text: `${currentDb}.${currentTable}`,
      }),
    });
    toast(res.success ? 'Foreign key added' : res.error, res.success ? 'success' : 'error');
    if (res.success) {
      closeModal('addFkModal');
      loadTableDetail(currentTable);
      afterDdlSuccess(res);
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
      if (res.suggest_generate_migration) openModal('migrationNudgeModal');
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
    } else if (action === 'drop_index') {
      const idx = $('#dropConfirmInput')?.dataset.indexName;
      res = await api(`/${currentDb}/tables/${encodeURIComponent(currentTable)}/indexes/${encodeURIComponent(idx)}`, {
        method: 'DELETE',
        body: JSON.stringify({
          confirm: true,
          confirmation_text: `DROP INDEX ${currentDb}.${currentTable}.${idx}`,
        }),
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
      if (action === 'drop_table') {
        currentTable = null;
        clearTableDetail();
      } else if (currentTable) {
        loadTableDetail(currentTable);
      }
      afterDdlSuccess(res);
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
    dropIndex,
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
    applyDdlUiState();
  });
})();
