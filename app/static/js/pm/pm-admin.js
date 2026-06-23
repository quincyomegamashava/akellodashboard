/** PM admin: workflow, custom fields, roles, webhooks, programs. */
(function() {
  const API = window.PM_API_BASE || '/api';

  function byId(id) {
    return document.getElementById(id);
  }

  window.pmOpenColumnWorkflow = function(columnId, columnTitle) {
    if (!columnId || typeof openModal !== 'function') return;
    openModal(`Column rules: ${columnTitle || ''}`, async (c) => {
      const rules = await pmApiGET(`${API}/columns/${columnId}/workflow`);
      c.innerHTML = `
        <div class="grid gap-3 text-sm">
          <label class="flex items-center gap-2"><input type="checkbox" id="wf_req_assignee" ${rules.require_assignee ? 'checked' : ''} /> Require assignee to enter column</label>
          <label class="flex items-center gap-2"><input type="checkbox" id="wf_req_due" ${rules.require_due_date ? 'checked' : ''} /> Require due date</label>
          <label class="flex items-center gap-2">Min progress % <input type="number" id="wf_min_prog" min="0" max="100" value="${rules.min_progress != null ? rules.min_progress : ''}" class="border rounded w-20 px-1" /></label>
        </div>`;
    }, async () => {
      const minRaw = (byId('wf_min_prog') || {}).value;
      await pmApiPATCH(`${API}/columns/${columnId}/workflow`, {
        require_assignee: !!(byId('wf_req_assignee') || {}).checked,
        require_due_date: !!(byId('wf_req_due') || {}).checked,
        min_progress: minRaw === '' ? null : parseInt(minRaw, 10),
      });
    });
  };

  window.pmRenderCustomFieldsAdmin = async function(mount, projectId) {
    if (!mount || !projectId) return;
    const fields = await pmApiGET(`${API}/projects/${projectId}/custom-fields`);
    mount.innerHTML = `
      <div class="border-t pt-3 mt-2">
        <div class="text-sm font-medium text-zinc-700 mb-2">Custom fields</div>
        <div class="space-y-1 mb-2">${(fields || []).map((f) => `
          <div class="flex items-center gap-2 text-xs border rounded px-2 py-1">
            <span class="font-medium">${esc(f.name)}</span>
            <span class="text-zinc-500">(${f.field_type})</span>
            ${f.required_on_close ? '<span class="text-amber-600">required on close</span>' : ''}
            <button type="button" class="text-red-600 ml-auto pm-cf-del" data-id="${f.id}">Delete</button>
          </div>`).join('') || '<span class="text-zinc-500 italic text-xs">None defined</span>'}
        <div class="flex flex-wrap gap-2 mt-2">
          <input id="pmCfName" class="border rounded px-2 py-1 text-sm" placeholder="Field name" />
          <select id="pmCfType" class="border rounded px-2 py-1 text-sm"><option value="text">Text</option><option value="number">Number</option><option value="date">Date</option><option value="select">Select</option></select>
          <input id="pmCfOptions" class="border rounded px-2 py-1 text-sm" placeholder="Options (comma-separated)" />
          <label class="text-xs flex items-center gap-1"><input type="checkbox" id="pmCfRequiredClose" /> Required on close</label>
          <button type="button" id="pmCfAdd" class="text-xs px-2 py-1 bg-indigo-600 text-white rounded">Add</button>
        </div>
      </div>`;
    mount.querySelector('#pmCfAdd').onclick = async () => {
      const name = (byId('pmCfName') || {}).value.trim();
      const field_type = (byId('pmCfType') || {}).value;
      const opts = ((byId('pmCfOptions') || {}).value || '').split(',').map((s) => s.trim()).filter(Boolean);
      if (!name) return;
      await pmApiPOST(`${API}/projects/${projectId}/custom-fields`, {
        name, field_type, options: opts,
        required_on_close: !!(byId('pmCfRequiredClose') || {}).checked,
      });
      await pmRenderCustomFieldsAdmin(mount, projectId);
      if (typeof pmLoadCustomFields === 'function') await pmLoadCustomFields(projectId);
    };
    mount.querySelectorAll('.pm-cf-del').forEach((btn) => {
      btn.onclick = async () => {
        if (!confirm('Delete field?')) return;
        await pmApiDELETE(`${API}/projects/${projectId}/custom-fields/${btn.dataset.id}`);
        await pmRenderCustomFieldsAdmin(mount, projectId);
      };
    });
  };

  window.pmRenderMemberRoles = async function(listMount, projectId) {
    if (!listMount || !projectId) return;
    const roles = await pmApiGET(`${API}/projects/${projectId}/members/roles`);
    listMount.querySelectorAll('[data-member-role]').forEach((sel) => {
      const uid = sel.getAttribute('data-member-role');
      const row = (roles || []).find((r) => String(r.user_id) === String(uid));
      if (row) sel.value = row.role || 'contributor';
      sel.onchange = async () => {
        await pmApiPATCH(`${API}/projects/${projectId}/members/roles`, { user_id: parseInt(uid, 10), role: sel.value });
      };
    });
  };

  window.pmRenderWebhooksAdmin = async function(mount, projectId) {
    if (!mount || !projectId) return;
    let hooks = [];
    try { hooks = await pmApiGET(`${API}/projects/${projectId}/webhooks`); } catch (e) { /* admin only */ }
    mount.innerHTML = `
      <div class="border-t pt-3 mt-2">
        <div class="text-sm font-medium text-zinc-700 mb-2">Webhooks</div>
        <div id="pmWhList" class="space-y-2 mb-2">
        ${(hooks || []).map((h) => `
          <div class="text-xs border rounded px-2 py-1" data-wh-id="${h.id}">
            <div class="flex flex-wrap items-center gap-2">
              <span class="flex-1 truncate">${esc(h.url)}</span>
              <span class="text-zinc-500">${(h.events || []).join(', ')}</span>
              <button type="button" class="text-indigo-600 pm-wh-test" data-id="${h.id}">Test</button>
              <button type="button" class="text-zinc-600 pm-wh-log" data-id="${h.id}">Log</button>
            </div>
            <div class="pm-wh-deliveries hidden mt-1 text-[10px] text-zinc-500 border-t pt-1"></div>
          </div>`).join('') || '<p class="text-xs text-zinc-500">No webhooks</p>'}
        </div>
        <div class="grid gap-2 mt-2">
          <input id="pmWhUrl" class="border rounded px-2 py-1 text-sm" placeholder="https://…" />
          <label class="text-xs"><input type="checkbox" id="pmWhCreated" /> task.created</label>
          <label class="text-xs"><input type="checkbox" id="pmWhMoved" checked /> task.moved</label>
          <label class="text-xs"><input type="checkbox" id="pmWhCompleted" checked /> task.completed</label>
          <button type="button" id="pmWhAdd" class="text-xs px-2 py-1 bg-indigo-600 text-white rounded w-fit">Add webhook</button>
        </div>
      </div>`;
    mount.querySelectorAll('.pm-wh-test').forEach((btn) => {
      btn.onclick = async () => {
        try {
          const r = await pmApiPOST(`${API}/projects/${projectId}/webhooks/${btn.dataset.id}/test`, {});
          alert(r.status_code ? `Test sent (HTTP ${r.status_code})` : `Test failed: ${r.error || 'unknown'}`);
        } catch (e) { alert(e.message || e); }
      };
    });
    mount.querySelectorAll('.pm-wh-log').forEach((btn) => {
      btn.onclick = async () => {
        const row = btn.closest('[data-wh-id]');
        const box = row ? row.querySelector('.pm-wh-deliveries') : null;
        if (!box) return;
        box.classList.toggle('hidden');
        if (box.classList.contains('hidden')) return;
        try {
          const rows = await pmApiGET(`${API}/projects/${projectId}/webhooks/${btn.dataset.id}/deliveries`);
          box.innerHTML = (rows || []).length
            ? rows.map((d) => `<div>${d.created_at ? d.created_at.slice(0, 19) : ''} · ${esc(d.event)} · ${d.status_code || '—'}${d.error ? ' · ' + esc(d.error) : ''}</div>`).join('')
            : 'No deliveries yet';
        } catch (e) { box.textContent = 'Could not load log'; }
      };
    });
    const add = mount.querySelector('#pmWhAdd');
    if (add) {
      add.onclick = async () => {
        const url = (byId('pmWhUrl') || {}).value.trim();
        const events = [];
        if ((byId('pmWhCreated') || {}).checked) events.push('task.created');
        if ((byId('pmWhMoved') || {}).checked) events.push('task.moved');
        if ((byId('pmWhCompleted') || {}).checked) events.push('task.completed');
        if (!url) return;
        await pmApiPOST(`${API}/projects/${projectId}/webhooks`, { url, events });
        await pmRenderWebhooksAdmin(mount, projectId);
      };
    }
  };

  window.pmWireProgramsModal = function() {
    const btn = document.getElementById('pmManageProgramsBtn');
    const backdrop = document.getElementById('pmProgramsModalBackdrop');
    const closeBtn = document.getElementById('pmProgramsModalClose');
    const list = document.getElementById('pmProgramsList');
    const createBtn = document.getElementById('pmCreateProgramBtn');
    if (!btn || !backdrop) return;
    async function refreshList() {
      const progs = await pmApiGET(`${API}/pm/programs`);
      let projects = [];
      try { projects = await pmApiGET(`${API}/projects`); } catch (e) { /* ignore */ }
      list.innerHTML = (progs || []).map((p) => `
        <div class="border rounded p-2" data-prog-id="${p.id}">
          <div class="font-medium">${esc(p.name)}</div>
          <select multiple class="pm-prog-projects border rounded text-xs w-full mt-1 min-h-[4rem]" data-prog="${p.id}">
            ${(projects || []).map((pr) => `<option value="${pr.id}" ${(p.project_ids || []).some((id) => String(id) === String(pr.id)) ? 'selected' : ''}>${esc(pr.name)}</option>`).join('')}
          </select>
          <button type="button" class="text-xs text-indigo-600 mt-1 pm-prog-save" data-prog="${p.id}">Save projects</button>
        </div>`).join('') || '<p class="text-zinc-500">No programs</p>';
      list.querySelectorAll('.pm-prog-save').forEach((btn) => {
        btn.onclick = async () => {
          try {
            const sel = list.querySelector(`select[data-prog="${btn.dataset.prog}"]`);
            const project_ids = sel ? Array.from(sel.selectedOptions).map((o) => parseInt(o.value, 10)) : [];
            await pmApiPATCH(`${API}/pm/programs/${btn.dataset.prog}`, { project_ids });
            await refreshList();
          } catch (e) {
            alert(e.message || 'Could not save program.');
          }
        };
      });
    }
    btn.onclick = async () => { backdrop.classList.remove('hidden'); await refreshList(); };
    if (closeBtn) closeBtn.onclick = () => backdrop.classList.add('hidden');
    backdrop.addEventListener('click', (e) => { if (e.target === backdrop) backdrop.classList.add('hidden'); });
    if (createBtn) {
      createBtn.onclick = async () => {
        const nameInput = byId('pmNewProgramName');
        const name = nameInput ? nameInput.value.trim() : '';
        if (!name) {
          alert('Enter a program name.');
          return;
        }
        try {
          await pmApiPOST(`${API}/pm/programs`, { name });
          if (nameInput) nameInput.value = '';
          await refreshList();
        } catch (e) {
          alert(e.message || 'Could not create program.');
        }
      };
    }
  };

  window.pmLoadSubscribeState = async function(projectId) {
    try {
      const r = await pmApiGET(`${API}/projects/${projectId}/subscribe`);
      return !!r.subscribed;
    } catch (e) { return false; }
  };

  window.pmRenderTimeEntries = async function(mount, taskId) {
    if (!mount || !taskId) return;
    mount.innerHTML = '<p class="text-xs text-zinc-500">Loading time log…</p>';
    try {
      const entries = await pmApiGET(`${API}/tasks/${taskId}/time-entries`);
      const total = (entries || []).reduce((s, e) => s + (e.minutes || 0), 0);
      mount.innerHTML = `
        <div class="text-xs text-zinc-600 mb-2">Total: <strong>${total}</strong> min (${(total / 60).toFixed(1)} h)</div>
        <ul class="space-y-1 mb-2 max-h-32 overflow-y-auto text-xs">
          ${(entries || []).map((e) => `<li class="border rounded px-2 py-1 flex flex-wrap items-center gap-2" data-entry-id="${e.id}">
            <span class="flex-1">${e.entry_date ? e.entry_date.slice(0, 10) : ''}: ${e.minutes} min${e.note ? ' — ' + esc(e.note) : ''}</span>
            <button type="button" class="text-indigo-600 pm-time-edit" data-id="${e.id}">Edit</button>
            <button type="button" class="text-red-600 pm-time-del" data-id="${e.id}">Remove</button>
          </li>`).join('') || '<li class="italic text-zinc-500">No entries</li>'}
        </ul>
        <div class="flex flex-wrap gap-2">
          <input type="number" id="pmTimeMinutes" min="1" class="border rounded px-2 py-1 text-sm w-20" placeholder="Min" />
          <input type="date" id="pmTimeDate" class="border rounded px-2 py-1 text-sm" />
          <input type="text" id="pmTimeNote" class="border rounded px-2 py-1 text-sm flex-1 min-w-[8rem]" placeholder="Note" />
          <button type="button" id="pmTimeAddBtn" class="text-xs px-2 py-1 bg-indigo-600 text-white rounded">Log</button>
        </div>`;
      const addBtn = mount.querySelector('#pmTimeAddBtn');
      if (addBtn) {
        addBtn.onclick = async () => {
          const minutes = parseInt((mount.querySelector('#pmTimeMinutes') || {}).value || 0, 10);
          const entry_date = (mount.querySelector('#pmTimeDate') || {}).value || undefined;
          const note = (mount.querySelector('#pmTimeNote') || {}).value || undefined;
          if (!minutes) return;
          await pmApiPOST(`${API}/tasks/${taskId}/time-entries`, { minutes, entry_date, note });
          await pmRenderTimeEntries(mount, taskId);
        };
      }
      mount.querySelectorAll('.pm-time-del').forEach((btn) => {
        btn.onclick = async () => {
          if (!confirm('Remove time entry?')) return;
          await pmApiDELETE(`${API}/tasks/${taskId}/time-entries/${btn.dataset.id}`);
          await pmRenderTimeEntries(mount, taskId);
        };
      });
      mount.querySelectorAll('.pm-time-edit').forEach((btn) => {
        btn.onclick = async () => {
          const row = btn.closest('[data-entry-id]');
          const e = (entries || []).find((x) => String(x.id) === String(btn.dataset.id));
          if (!e) return;
          const minutes = prompt('Minutes:', String(e.minutes));
          if (!minutes) return;
          await pmApiPATCH(`${API}/tasks/${taskId}/time-entries/${btn.dataset.id}`, {
            minutes: parseInt(minutes, 10),
            note: e.note,
            entry_date: e.entry_date ? e.entry_date.slice(0, 10) : undefined,
          });
          await pmRenderTimeEntries(mount, taskId);
        };
      });
    } catch (e) {
      mount.innerHTML = '<p class="text-xs text-red-500">Could not load time entries.</p>';
    }
  };

  function esc(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;');
  }
})();
