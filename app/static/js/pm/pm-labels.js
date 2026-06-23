/** Project label management and pickers. */
(function() {
  const API = window.PM_API_BASE || '/api';

  window.pmProjectLabels = [];

  window.pmLoadProjectLabels = async function(projectId) {
    if (!projectId) {
      window.pmProjectLabels = [];
      return [];
    }
    const labels = await pmApiGET(`${API}/projects/${projectId}/labels`);
    window.pmProjectLabels = labels || [];
    return window.pmProjectLabels;
  };

  window.pmRenderLabelChips = function(labels, container) {
    if (!container) return;
    container.innerHTML = '';
    (labels || []).forEach((lb) => {
      const chip = document.createElement('span');
      chip.className = 'pm-label-chip';
      chip.textContent = lb.name;
      chip.style.backgroundColor = lb.color || '#6366f1';
      container.appendChild(chip);
    });
  };

  window.pmMountLabelPicker = function(mount, options) {
    const opts = options || {};
    const selected = new Set((opts.selected || []).map((l) => String(l.id || l)));
    const multi = opts.multi !== false;

    function render() {
      mount.innerHTML = '';
      mount.className = 'flex flex-wrap gap-1.5';
      (window.pmProjectLabels || []).forEach((lb) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        const on = selected.has(String(lb.id));
        btn.className = 'pm-label-chip cursor-pointer border-2 ' + (on ? 'border-zinc-900 ring-1' : 'border-transparent opacity-70');
        btn.textContent = lb.name;
        btn.style.backgroundColor = lb.color || '#6366f1';
        btn.onclick = () => {
          const sid = String(lb.id);
          if (multi) {
            if (selected.has(sid)) selected.delete(sid);
            else selected.add(sid);
          } else {
            selected.clear();
            selected.add(sid);
          }
          render();
          if (typeof opts.onChange === 'function') opts.onChange(pmGetSelectedLabelIds());
        };
        mount.appendChild(btn);
      });
      if (!(window.pmProjectLabels || []).length) {
        mount.innerHTML = '<span class="text-xs text-zinc-500 italic">No labels — manage in project settings</span>';
      }
    }

    function pmGetSelectedLabelIds() {
      return Array.from(selected).map((x) => parseInt(x, 10));
    }

    render();
    return { getSelectedIds: pmGetSelectedLabelIds, refresh: render };
  };

  window.pmOpenLabelManager = function(projectId, onDone) {
    if (!projectId || typeof openModal !== 'function') return;
    openModal('Manage labels', async (c) => {
      await pmLoadProjectLabels(projectId);
      c.innerHTML = `
        <div class="grid gap-3">
          <div id="pm-label-list" class="space-y-2 max-h-48 overflow-y-auto"></div>
          <div class="flex gap-2">
            <input id="pm-new-label-name" class="flex-1 border rounded px-2 py-1.5 text-sm" placeholder="New label name" />
            <input id="pm-new-label-color" type="color" value="#6366f1" class="w-10 h-9 border rounded" />
            <button type="button" id="pm-add-label-btn" class="px-3 py-1.5 bg-indigo-600 text-white rounded text-sm">Add</button>
          </div>
        </div>`;
      const list = c.querySelector('#pm-label-list');

      async function refreshList() {
        await pmLoadProjectLabels(projectId);
        list.innerHTML = (window.pmProjectLabels || []).map((lb) => `
          <div class="flex items-center gap-2 border rounded px-2 py-1.5" data-lid="${lb.id}">
            <span class="pm-label-chip" style="background:${lb.color}">${lb.name}</span>
            <input type="color" value="${lb.color}" data-color-edit="${lb.id}" class="w-8 h-7" />
            <button type="button" data-del-label="${lb.id}" class="text-xs text-red-600 ml-auto">Delete</button>
          </div>`).join('') || '<p class="text-sm text-zinc-500 italic">No labels yet</p>';
        list.querySelectorAll('[data-del-label]').forEach((btn) => {
          btn.onclick = async () => {
            if (!confirm('Delete this label?')) return;
            await pmApiDELETE(`${API}/projects/${projectId}/labels/${btn.dataset.delLabel}`);
            await refreshList();
          };
        });
        list.querySelectorAll('[data-color-edit]').forEach((inp) => {
          inp.onchange = async () => {
            await pmApiPATCH(`${API}/projects/${projectId}/labels/${inp.dataset.colorEdit}`, { color: inp.value });
            await refreshList();
          };
        });
      }

      await refreshList();
      c.querySelector('#pm-add-label-btn').onclick = async () => {
        const name = c.querySelector('#pm-new-label-name').value.trim();
        const color = c.querySelector('#pm-new-label-color').value;
        if (!name) return;
        await pmApiPOST(`${API}/projects/${projectId}/labels`, { name, color });
        c.querySelector('#pm-new-label-name').value = '';
        await refreshList();
      };
    }, async () => {
      if (typeof onDone === 'function') await onDone();
    }, false);
  };
})();
