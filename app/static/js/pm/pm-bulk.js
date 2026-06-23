/** Board bulk selection and operations. */
(function() {
  window.pmBulkMode = false;
  window.pmBulkSelected = new Set();

  window.pmToggleBulkMode = function(on) {
    window.pmBulkMode = !!on;
    if (!window.pmBulkMode) window.pmBulkSelected.clear();
    document.body.classList.toggle('pm-bulk-mode', window.pmBulkMode);
    document.querySelectorAll('.pm-bulk-checkbox').forEach((cb) => {
      cb.classList.toggle('hidden', !window.pmBulkMode);
    });
    const bar = document.getElementById('pmBulkBar');
    if (bar) bar.classList.toggle('hidden', !window.pmBulkMode);
    pmBulkUpdateCount();
    pmPopulateBulkLabelSelect();
  };

  window.pmPopulateBulkLabelSelect = function() {
    const sel = document.getElementById('pmBulkLabel');
    if (!sel) return;
    const labels = window.pmProjectLabelsCache || [];
    const prev = sel.value;
    sel.innerHTML = '<option value="">Add label…</option>';
    labels.forEach((lb) => sel.appendChild(new Option(lb.name, String(lb.id))));
    if (prev) sel.value = prev;
  };

  window.pmBulkUpdateCount = function() {
    const el = document.getElementById('pmBulkCount');
    if (el) el.textContent = String(window.pmBulkSelected.size);
  };

  window.pmAttachBulkCheckbox = function(taskEl, taskId) {
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.className = 'pm-bulk-checkbox hidden absolute top-2 left-2 z-10';
    cb.checked = window.pmBulkSelected.has(String(taskId));
    cb.onclick = (e) => {
      e.stopPropagation();
      const sid = String(taskId);
      if (cb.checked) window.pmBulkSelected.add(sid);
      else window.pmBulkSelected.delete(sid);
      pmBulkUpdateCount();
    };
    taskEl.style.position = 'relative';
    taskEl.prepend(cb);
  };

  window.pmBulkMove = async function(columnId) {
    const ids = Array.from(window.pmBulkSelected);
    if (!ids.length || !columnId) return;
    const API = window.PM_API_BASE || '/api';
    const board = window.lastBoardData;
    for (const id of ids) {
      const task = pmFindTaskById(board, id);
      const col = (board?.columns || []).find((c) => String(c.id) === String(columnId));
      if (task && col && !pmWarnBlockedMove(task, col.title)) continue;
      await pmApiPATCH(`${API}/tasks/${id}`, { column_id: parseInt(columnId, 10) });
    }
    window.pmBulkSelected.clear();
    pmToggleBulkMode(false);
    if (typeof loadBoard === 'function' && window.currentProjectId) {
      await loadBoard(window.currentProjectId);
    }
  };

  window.pmBulkDelete = async function() {
    const ids = Array.from(window.pmBulkSelected);
    if (!ids.length || !confirm(`Delete ${ids.length} task(s)?`)) return;
    const API = window.PM_API_BASE || '/api';
    for (const id of ids) {
      await pmApiDELETE(`${API}/tasks/${id}`);
    }
    window.pmBulkSelected.clear();
    pmToggleBulkMode(false);
    if (typeof loadBoard === 'function' && window.currentProjectId) {
      await loadBoard(window.currentProjectId);
    }
  };

  window.pmBulkSetPriority = async function(priority) {
    const ids = Array.from(window.pmBulkSelected);
    if (!ids.length) return;
    const API = window.PM_API_BASE || '/api';
    for (const id of ids) {
      await pmApiPATCH(`${API}/tasks/${id}`, { priority });
    }
    pmToggleBulkMode(false);
    if (typeof loadBoard === 'function' && window.currentProjectId) {
      await loadBoard(window.currentProjectId);
    }
  };

  window.pmBulkAssign = async function(userIds) {
    const ids = Array.from(window.pmBulkSelected);
    if (!ids.length || !userIds || !userIds.length) return;
    const API = window.PM_API_BASE || '/api';
    for (const id of ids) {
      await pmApiPATCH(`${API}/tasks/${id}`, { assignees: userIds });
    }
    pmToggleBulkMode(false);
    if (typeof loadBoard === 'function' && window.currentProjectId) {
      await loadBoard(window.currentProjectId);
    }
  };

  window.pmBulkSetDueDate = async function(endDate) {
    const ids = Array.from(window.pmBulkSelected);
    if (!ids.length || !endDate) return;
    const API = window.PM_API_BASE || '/api';
    for (const id of ids) {
      await pmApiPATCH(`${API}/tasks/${id}`, { end_date: endDate });
    }
    pmToggleBulkMode(false);
    if (typeof loadBoard === 'function' && window.currentProjectId) {
      await loadBoard(window.currentProjectId);
    }
  };

  window.pmBulkAddLabel = async function(labelId) {
    const ids = Array.from(window.pmBulkSelected);
    if (!ids.length || !labelId) return;
    const API = window.PM_API_BASE || '/api';
    const board = window.lastBoardData;
    for (const id of ids) {
      const task = pmFindTaskById(board, id);
      const existing = (task?.labels || []).map((l) => l.id);
      if (existing.includes(parseInt(labelId, 10))) continue;
      await pmApiPATCH(`${API}/tasks/${id}`, { labels: [...existing, parseInt(labelId, 10)] });
    }
    pmToggleBulkMode(false);
    if (typeof loadBoard === 'function' && window.currentProjectId) {
      await loadBoard(window.currentProjectId);
    }
  };

  window.pmWireBulkBar = function() {
    const dueBtn = document.getElementById('pmBulkDueBtn');
    if (dueBtn) {
      dueBtn.onclick = () => {
        const d = (document.getElementById('pmBulkDueDate') || {}).value;
        if (!d) return;
        pmBulkSetDueDate(d);
      };
    }
    const labelSel = document.getElementById('pmBulkLabel');
    if (labelSel) {
      labelSel.onchange = () => {
        const v = labelSel.value;
        if (!v) return;
        pmBulkAddLabel(v);
        labelSel.value = '';
      };
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', pmWireBulkBar);
  } else {
    pmWireBulkBar();
  }
})();
