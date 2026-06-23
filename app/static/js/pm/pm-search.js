/** Global PM search and saved views. */
(function() {
  const API = window.PM_API_BASE || '/api';

  window.pmGlobalSearch = async function(q, opts) {
    const o = opts || {};
    const params = new URLSearchParams();
    if (q) params.set('q', q);
    if (o.assigneeMe) params.set('assignee', 'me');
    if (o.status) params.set('status', o.status);
    return pmApiGET(`${API}/pm/search?${params}`);
  };

  window.pmMountGlobalSearch = function(inputEl, resultsEl) {
    if (!inputEl || !resultsEl) return;
    const run = pmDebounce(async () => {
      const q = inputEl.value.trim();
      if (q.length < 2) {
        resultsEl.innerHTML = '';
        resultsEl.classList.add('hidden');
        return;
      }
      try {
        const rows = await pmGlobalSearch(q);
        if (!rows.length) {
          resultsEl.innerHTML = '<div class="px-3 py-2 text-sm text-zinc-500">No matches</div>';
        } else {
          resultsEl.innerHTML = rows.map((r) => `
            <a href="/projectmanagement?project=${r.project_id}&task=${r.task_id}" class="block px-3 py-2 hover:bg-indigo-50 border-b border-zinc-100 text-sm">
              <div class="font-medium text-zinc-900">${r.title}</div>
              <div class="text-xs text-zinc-500">${r.project_name} · ${r.column_title}</div>
            </a>`).join('');
        }
        resultsEl.classList.remove('hidden');
      } catch (e) {
        resultsEl.innerHTML = '<div class="px-3 py-2 text-sm text-red-500">Search failed</div>';
      }
    }, 300);
    inputEl.oninput = run;
    inputEl.onfocus = run;
  };

  window.pmSaveCurrentBoardView = async function(projectId, name) {
    if (!projectId || !name) return;
    const f = window.pmBoardFilters || {};
    await pmApiPOST(`${API}/projects/${projectId}/saved-views`, {
      name,
      filter: f,
    });
  };

  window.pmLoadSavedViews = async function(projectId) {
    if (!projectId) return [];
    return pmApiGET(`${API}/projects/${projectId}/saved-views`);
  };

  window.pmApplySavedView = function(filter) {
    if (!filter || typeof filter !== 'object') return;
    window.pmBoardFilters = { ...window.pmBoardFilters, ...filter };
    if (typeof pmSaveBoardFiltersToStorage === 'function') pmSaveBoardFiltersToStorage();
    const search = document.getElementById('pmBoardSearch');
    if (search) search.value = window.pmBoardFilters.q || '';
    ['pmBoardFilterColumn', 'pmBoardFilterAssignee', 'pmBoardFilterLabel'].forEach((id) => {
      const el = document.getElementById(id);
      if (!el) return;
      const key = id.replace('pmBoardFilter', '').toLowerCase();
      const map = { column: 'column', assignee: 'assignee', label: 'label' };
      if (map[key] && window.pmBoardFilters[map[key]] != null) {
        el.value = window.pmBoardFilters[map[key]];
      }
    });
    ['pmBoardFilterMine', 'pmBoardFilterSubtasks', 'pmBoardFilterFiles'].forEach((id) => {
      const el = document.getElementById(id);
      if (!el) return;
      const key = id.replace('pmBoardFilter', '').toLowerCase();
      if (window.pmBoardFilters[key] != null) el.checked = !!window.pmBoardFilters[key];
    });
    if (typeof pmApplyBoardFilters === 'function') pmApplyBoardFilters();
  };
})();
