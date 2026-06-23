/** MilestoneA CRUD and Gantt markers. */
(function() {
  const API = window.PM_API_BASE || '/api';
  window.pmProjectMilestones = [];

  window.pmLoadMilestones = async function(projectId) {
    if (!projectId) return [];
    window.pmProjectMilestones = await pmApiGET(`${API}/projects/${projectId}/milestones`);
    return window.pmProjectMilestones;
  };

  function taskOptions(boardData) {
    const tasks = [];
    (boardData?.columns || []).forEach((c) => (c.tasks || []).forEach((t) => tasks.push({ id: t.id, title: t.title })));
    return tasks;
  }

  window.pmRenderMilestonesManager = function(mount, projectId, boardData) {
    if (!mount) return;
    const canManage = typeof pmCanManageProject === 'function' ? pmCanManageProject() : true;
    const ms = window.pmProjectMilestones || [];
    const tasks = taskOptions(boardData);
    mount.innerHTML = `
      <div class="space-y-2">
        ${ms.length ? ms.map((m) => `
          <div class="border rounded-lg p-2 text-sm" data-ms-id="${m.id}">
            <div class="flex flex-wrap items-center gap-2 pm-ms-view">
              <span class="w-3 h-3 rounded-full shrink-0" style="background:${m.color || '#8b5cf6'}"></span>
              <span class="font-medium flex-1">${esc(m.title)}</span>
              <span class="text-xs text-zinc-500">${m.due_date ? m.due_date.slice(0, 10) : '—'}</span>
              ${canManage ? `<button type="button" class="text-xs text-indigo-600 pm-ms-edit" data-id="${m.id}">Edit</button>
              <button type="button" class="text-xs text-red-600 pm-ms-del" data-id="${m.id}">Delete</button>` : ''}
            </div>
            <div class="pm-ms-edit-form hidden grid gap-2 mt-2 border-t pt-2">
              <input class="pm-ms-et border rounded px-2 py-1 text-sm" value="${esc(m.title)}" />
              <input class="pm-ms-ed border rounded px-2 py-1 text-sm" type="date" value="${m.due_date ? m.due_date.slice(0, 10) : ''}" />
              <input class="pm-ms-ec border rounded w-10 h-8" type="color" value="${m.color || '#8b5cf6'}" />
              <select class="pm-ms-ets border rounded px-2 py-1 text-sm min-h-[4rem]" multiple>
                ${tasks.map((t) => `<option value="${t.id}" ${(m.task_ids || []).includes(t.id) ? 'selected' : ''}>${esc(t.title)}</option>`).join('')}
              </select>
              <div class="flex gap-2">
                <button type="button" class="text-xs px-2 py-1 bg-indigo-600 text-white rounded pm-ms-save" data-id="${m.id}">Save</button>
                <button type="button" class="text-xs px-2 py-1 border rounded pm-ms-cancel">Cancel</button>
              </div>
            </div>
          </div>`).join('') : '<p class="text-sm text-zinc-500 italic">No milestones yet.</p>'}
        ${canManage ? `<div class="grid gap-2 border-t pt-2 mt-2">
          <input id="pmMsTitle" class="border rounded px-2 py-1 text-sm" placeholder="Milestone title" />
          <input id="pmMsDue" type="date" class="border rounded px-2 py-1 text-sm" />
          <input id="pmMsColor" type="color" value="#8b5cf6" class="w-10 h-8" />
          <select id="pmMsTasks" multiple class="border rounded px-2 py-1 text-sm min-h-[4rem]">
            ${tasks.map((t) => `<option value="${t.id}">${esc(t.title)}</option>`).join('')}
          </select>
          <button type="button" id="pmMsAddBtn" class="text-sm px-3 py-1.5 bg-indigo-600 text-white rounded-lg w-fit">Add milestone</button>
        </div>` : ''}
      </div>`;
    const addBtn = mount.querySelector('#pmMsAddBtn');
    if (addBtn) {
      addBtn.onclick = async () => {
        const title = (mount.querySelector('#pmMsTitle') || {}).value.trim();
        const due = (mount.querySelector('#pmMsDue') || {}).value;
        const color = (mount.querySelector('#pmMsColor') || {}).value;
        const taskSel = mount.querySelector('#pmMsTasks');
        const task_ids = taskSel ? Array.from(taskSel.selectedOptions).map((o) => parseInt(o.value, 10)) : [];
        if (!title) return;
        await pmApiPOST(`${API}/projects/${projectId}/milestones`, {
          title, due_date: due || undefined, color, task_ids,
        });
        await pmLoadMilestones(projectId);
        pmRenderMilestonesManager(mount, projectId, boardData);
        if (typeof renderVisGantt === 'function' && window.lastBoardData) renderVisGantt(window.lastBoardData);
        if (typeof renderCalendar === 'function' && window.lastBoardData) renderCalendar(window.lastBoardData);
      };
    }
    mount.querySelectorAll('.pm-ms-edit').forEach((btn) => {
      btn.onclick = () => {
        const row = btn.closest('[data-ms-id]');
        if (!row) return;
        row.querySelector('.pm-ms-view').classList.add('hidden');
        row.querySelector('.pm-ms-edit-form').classList.remove('hidden');
      };
    });
    mount.querySelectorAll('.pm-ms-cancel').forEach((btn) => {
      btn.onclick = () => {
        const row = btn.closest('[data-ms-id]');
        if (!row) return;
        row.querySelector('.pm-ms-edit-form').classList.add('hidden');
        row.querySelector('.pm-ms-view').classList.remove('hidden');
      };
    });
    mount.querySelectorAll('.pm-ms-save').forEach((btn) => {
      btn.onclick = async () => {
        const row = btn.closest('[data-ms-id]');
        if (!row) return;
        const title = (row.querySelector('.pm-ms-et') || {}).value.trim();
        const due_date = (row.querySelector('.pm-ms-ed') || {}).value || null;
        const color = (row.querySelector('.pm-ms-ec') || {}).value;
        const taskSel = row.querySelector('.pm-ms-ets');
        const task_ids = taskSel ? Array.from(taskSel.selectedOptions).map((o) => parseInt(o.value, 10)) : [];
        if (!title) return;
        await pmApiPATCH(`${API}/projects/${projectId}/milestones/${btn.dataset.id}`, {
          title, due_date, color, task_ids,
        });
        await pmLoadMilestones(projectId);
        pmRenderMilestonesManager(mount, projectId, boardData);
        if (typeof renderVisGantt === 'function' && window.lastBoardData) renderVisGantt(window.lastBoardData);
        if (typeof renderCalendar === 'function' && window.lastBoardData) renderCalendar(window.lastBoardData);
      };
    });
    mount.querySelectorAll('.pm-ms-del').forEach((btn) => {
      btn.onclick = async () => {
        if (!confirm('Delete milestone?')) return;
        await pmApiDELETE(`${API}/projects/${projectId}/milestones/${btn.dataset.id}`);
        await pmLoadMilestones(projectId);
        pmRenderMilestonesManager(mount, projectId, boardData);
      };
    });
  };

  window.pmGanttMilestoneMarkersHtml = function(workDays, dayW) {
    const ms = window.pmProjectMilestones || [];
    if (!ms.length || !workDays || !workDays.length) return '';
    const idxFor = (dateStr) => {
      const t = new Date(dateStr.slice(0, 10)).getTime();
      for (let i = 0; i < workDays.length; i++) {
        if (new Date(workDays[i]).setHours(0,0,0,0) === t) return i;
      }
      return -1;
    };
    let html = '<div class="relative h-6 border-b border-zinc-200 bg-violet-50/50" style="width:' + (workDays.length * dayW) + 'px">';
    ms.forEach((m) => {
      if (!m.due_date) return;
      const idx = idxFor(m.due_date);
      if (idx < 0) return;
      const left = idx * dayW + dayW / 2 - 6;
      html += `<div title="${esc(m.title)}" style="left:${left}px;background:${m.color || '#8b5cf6'}" class="absolute top-0.5 w-3 h-3 rotate-45 border border-white shadow-sm pm-cal-ms-marker" data-ms-title="${esc(m.title)}"></div>`;
    });
    html += '</div>';
    return html;
  };

  window.pmMilestonesOnDay = function(dayKey) {
    return (window.pmProjectMilestones || []).filter((m) => m.due_date && m.due_date.slice(0, 10) === dayKey);
  };

  window.pmCalendarMilestoneHtml = function(dayKey) {
    const ms = pmMilestonesOnDay(dayKey);
    if (!ms.length) return '';
    return ms.map((m) => `<span class="inline-block w-2 h-2 rotate-45 shrink-0 ml-1 pm-cal-ms-marker cursor-pointer" data-ms-title="${esc(m.title)}" style="background:${m.color || '#8b5cf6'}" title="${esc(m.title)}"></span>`).join('');
  };

  function esc(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
  }
})();
