/** Board load/render — requires PM globals from template. */
/* ---------- Board rendering and column/task creation ---------- */
function pmSyncTaskInBoardData(taskId, patch) {
  if (!lastBoardData) return;
  let task = null;
  let fromCol = null;
  for (const col of (lastBoardData.columns || [])) {
    const idx = (col.tasks || []).findIndex((t) => String(t.id) === String(taskId));
    if (idx >= 0) {
      task = col.tasks[idx];
      fromCol = col;
      if (patch.column_id != null && String(patch.column_id) !== String(col.id)) {
        col.tasks.splice(idx, 1);
      }
      break;
    }
  }
  if (!task) return;
  Object.assign(task, patch);
  if (patch.column_id != null && fromCol && String(patch.column_id) !== String(fromCol.id)) {
    const dest = (lastBoardData.columns || []).find((c) => String(c.id) === String(patch.column_id));
    if (dest) {
      if (!dest.tasks) dest.tasks = [];
      const pos = patch.position != null ? patch.position : dest.tasks.length;
      dest.tasks.splice(pos, 0, task);
    }
  }
  pmUpdateTaskCardOnBoard(taskId, patch);
}

async function loadBoard(projectId) {
  if (!projectId) return;
  try {
    if (typeof pmLoadProjectLabels === 'function') await pmLoadProjectLabels(projectId);
    if (typeof pmLoadProjectDependencies === 'function') await pmLoadProjectDependencies(projectId);
    if (typeof pmLoadMilestones === 'function') await pmLoadMilestones(projectId);
    if (typeof pmLoadBaselines === 'function') await pmLoadBaselines(projectId);
    if (typeof pmPopulateBaselineSelect === 'function') pmPopulateBaselineSelect($('pmBaselineSelect'));
const data = await apiGET(`${API_BASE}/projects/${projectId}/board`);
    lastBoardData = data;
    if (typeof pmApplyProjectCapabilities === 'function') pmApplyProjectCapabilities(data);
    const canEdit = typeof pmCanEditTasks === 'function' ? pmCanEditTasks() : true;
    const canManage = typeof pmCanManageProject === 'function' ? pmCanManageProject() : true;
    const board = $('board');
    board.innerHTML = '';

    // Resolve members and type robustly
    const projectInfo = await resolveProjectInfo(projectId, data);
    const timelineSection = document.getElementById('timelineSection');
    const timelineAxisEl = document.getElementById('timelineAxis');
    const milestoneBodyEl = document.getElementById('milestoneBody');
    const timelineItemsBodyEl = document.getElementById('timelineItemsBody');
    const timelineItemsEmptyEl = document.getElementById('timelineItemsEmpty');
    const ganttBtn = document.getElementById('showGanttBtn');

    // Show members list
    // const membersBox = $('projectMembers'); // This element does not exist
    // if (projectInfo.members && projectInfo.members.length) {
    //   // show up to 8 names then "+ N"
    //   const MAX_SHOW = 8;
    //   const names = projectInfo.members.slice(0, MAX_SHOW).map(n => escapeHtml(n));
    //   const rest = projectInfo.members.length - names.length;
    //   membersBox.innerHTML = `👥 Members: <span class="font-medium">${names.join(', ')}${rest>0? `, +${rest}` : ''}</span>`;
    // } else {
    //   membersBox.innerHTML = "👥 Members: <span class='italic text-gray-500'>No members assigned</span>";
    // }

    if (ganttBtn) { ganttBtn.disabled = false; ganttBtn.title = ''; }

    const subWrap = $('pmSubscribeWrap');
    const subToggle = $('pmSubscribeToggle');
    if (subWrap && subToggle && typeof pmLoadSubscribeState === 'function') {
      subWrap.classList.remove('hidden');
      subToggle.checked = await pmLoadSubscribeState(projectId);
      subToggle.onchange = async () => {
        if (typeof pmSubscribeProject === 'function') {
          await pmSubscribeProject(projectId, subToggle.checked);
        }
      };
    }

    
    // render columns (data.columns expected)
    (data.columns || []).forEach(col => {
const colDiv = el('div', {class:'column flex-none w-[300px] flex flex-col rounded-xl border border-zinc-200 bg-zinc-50/80 p-3 shadow-sm', id:`column-${col.id}`});
      const header = el('div', {class:'column-header'});
      const title = el('h3', {class:'column-header-title', text:col.title});
      const controls = el('div', {class:'column-header-actions'});

      // Quick add input (hidden by default)
      const quickAddWrap = el('div', {class:'mt-2 hidden', id:`qa-${col.id}`});
      quickAddWrap.innerHTML = `<input class="w-full border p-2 rounded text-sm" placeholder="Type task title and hit Enter" />`;
      quickAddWrap.querySelector('input').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          const val = e.target.value.trim();
          if (val) {
            apiPOST(`${API_BASE}/columns/${col.id}/tasks`, {title: val}).then(()=>{
              e.target.value='';
              loadBoard(projectId);
            });
          }
        }
      });

      const addBtn = el('button', {class:'column-btn column-btn--icon', title:'Add task'});
      addBtn.textContent = '+';
      addBtn.onclick = () => {
        const qa = document.getElementById(`qa-${col.id}`);
        qa.classList.toggle('hidden');
        if (!qa.classList.contains('hidden')) qa.querySelector('input').focus();
      };
      if (canEdit) {
        controls.appendChild(addBtn);
      }
      if (canManage && typeof pmOpenColumnWorkflow === 'function') {
        const wfBtn = el('button', {class:'column-btn column-btn--icon', title:'Column rules'});
        wfBtn.textContent = '⚙';
        wfBtn.onclick = () => pmOpenColumnWorkflow(col.id, col.title);
        controls.appendChild(wfBtn);
      }
      if (canManage) {
        const renameBtn = el('button', {class:'column-btn', title:'Rename column', text:'Rename'});
        renameBtn.onclick = () => promptRenameColumn(projectId, col.id, col.title);
        controls.appendChild(renameBtn);
        if ((data.columns || []).length > 1) {
          const delColBtn = el('button', {class:'column-btn column-btn--danger', title:'Delete column', text:'Delete'});
          delColBtn.onclick = () => promptDeleteColumn(projectId, col, data.columns);
          controls.appendChild(delColBtn);
        }
      }
      header.appendChild(title);
      header.appendChild(controls);

      const taskList = el('div', {class:'task-list flex-1 min-h-[48px] space-y-2 mt-2', id:`col-tasks-${col.id}`});
      (col.tasks || []).forEach(task => renderTask(task, taskList));

      colDiv.appendChild(header);
      colDiv.appendChild(quickAddWrap);
      colDiv.appendChild(taskList);
      board.appendChild(colDiv);
    });

    const totalTasks = (data.columns || []).reduce((n, c) => n + (c.tasks || []).length, 0);
    if (!(data.columns || []).length) {
      const empty = el('div', { class: 'flex-1 flex flex-col items-center justify-center text-center p-8 border border-dashed border-zinc-200 rounded-xl bg-zinc-50/50 min-h-[200px]' });
      empty.innerHTML = canManage
        ? '<p class="text-sm text-zinc-600">This project has no columns yet.</p><p class="text-xs text-zinc-500 mt-1">Use <strong>+ Add column</strong> to get started.</p>'
        : '<p class="text-sm text-zinc-600">This project has no board content yet.</p>';
      board.appendChild(empty);
    } else if (!totalTasks) {
      const empty = el('div', { class: 'w-full text-center text-sm text-zinc-500 py-6 italic' });
      empty.textContent = 'No tasks yet — add one from a column header.';
      board.insertBefore(empty, board.firstChild);
    }

    // Add "Add Column" button
    if (canManage) {
      const addColBtn = el('button', {class:'flex-none h-fit self-start px-4 py-2.5 rounded-xl border border-dashed border-zinc-300 bg-white text-sm font-medium text-zinc-600 hover:border-indigo-300 hover:bg-indigo-50/50 transition-colors', text:'+ Add column'});
      addColBtn.onclick = () => promptAddColumn(projectId);
      board.appendChild(addColBtn);
    }

    const msMount = $('pmMilestonesMount');
    if (msMount && typeof pmRenderMilestonesManager === 'function') {
      pmRenderMilestonesManager(msMount, projectId, data);
    }

    // Refresh open-tasks list (timeline UI removed)
    try {
      renderIncompleteTasks(data);
      if (typeof pmWireIncompleteFilters === 'function') pmWireIncompleteFilters();
    } catch(e){ console.warn('Open tasks render failed', e); }

    // initialize Sortable for columns (reorder)
    if (canManage) {
      new Sortable(board, {
        animation: 150,
        ghostClass: 'ghost',
        draggable: '.column',
        onEnd: async (evt) => {
          const colEls = Array.from(board.children).filter(ch => ch.id && ch.id.startsWith('column-'));
          const newOrder = colEls.map(el => parseInt(el.id.replace('column-','')));
          try {
            await apiPOST(`${API_BASE}/projects/${projectId}/columns/reorder`, {order: newOrder});
          } catch (err) {
            console.error('Failed to reorder columns:', err);
            await loadBoard(projectId);
          }
        }
      });
    }

    // initialize Sortable for each task-list
    if (canEdit) {
    const lists = board.querySelectorAll('.task-list');
    lists.forEach(list => {
      new Sortable(list, {
        group: 'tasks',
        animation: 150,
        ghostClass: 'ghost',
        onAdd: async (evt) => {
          const taskId = evt.item.dataset.taskId;
          const newColumnId = parseInt(evt.to.id.replace('col-tasks-',''));
          const newPos = evt.newIndex;
          const task = findTaskOnBoard(taskId);
          const destCol = (data.columns || []).find((c) => String(c.id) === String(newColumnId));
          if (task && destCol && typeof pmWarnBlockedMove === 'function' && !pmWarnBlockedMove(task, destCol.title)) {
            await loadBoard(projectId);
            return;
          }
          try {
            await apiPATCH(`${API_BASE}/tasks/${taskId}`, {column_id: newColumnId, position: newPos});
            pmSyncTaskInBoardData(taskId, { column_id: newColumnId, position: newPos });
            requestAnimationFrame(() => renderIncompleteTasks(lastBoardData));
          } catch (err) {
            console.error('Move task failed', err);
            alert(err.message || err);
            await loadBoard(projectId);
          }
        },
        onUpdate: async (evt) => {
          const taskId = evt.item.dataset.taskId;
          const newPos = evt.newIndex;
          try {
            await apiPATCH(`${API_BASE}/tasks/${taskId}`, {position: newPos});
            pmSyncTaskInBoardData(taskId, { position: newPos });
          } catch (err) {
            console.error('Reorder failed', err);
            await loadBoard(projectId);
          }
        }
      });
    });
    }

    if (activePmTab === 'incomplete') {
      requestAnimationFrame(() => renderIncompleteTasks(data));
    }
    if (activePmTab === 'gantt') {
      requestAnimationFrame(() => renderVisGantt(data));
    }
    if (activePmTab === 'calendar') {
      requestAnimationFrame(() => renderCalendar(data));
    }
    if (activePmTab === 'documents') {
      requestAnimationFrame(() => renderDocumentsPanel(data));
    }
    if (activePmTab === 'activity' && typeof pmRenderActivityPanel === 'function') {
      requestAnimationFrame(() => pmRenderActivityPanel($('pmActivityFeed'), projectId, {}));
    }

    if (typeof pmWireBaselineControls === 'function') {
      const saveBtn = $('pmBaselineSaveBtn');
      if (saveBtn && saveBtn.dataset.wired !== String(projectId)) {
        saveBtn.dataset.wired = String(projectId);
        pmWireBaselineControls(projectId, () => renderVisGantt(lastBoardData));
      }
    }
    if (typeof pmPopulateBulkAssignees === 'function') pmPopulateBulkAssignees();

    updateProjectManageButtons();
    pmPopulateBoardFilterDropdowns(data);
    pmWireBoardFilters();
    pmApplyBoardFilters();
    if (typeof pmRefreshSavedViewsSelect === 'function') pmRefreshSavedViewsSelect();
    if (typeof pmPushRecentProject === 'function') pmPushRecentProject(projectId);
    pmUpdateUrl();

    if (pmPendingDeepLinkTask) {
      const tid = pmPendingDeepLinkTask;
      pmPendingDeepLinkTask = null;
      const t = findTaskOnBoard(tid);
      if (t) {
        requestAnimationFrame(() => openTaskDetails(t));
      } else {
        try {
          const full = await apiGET(`${API_BASE}/tasks/${tid}`);
          openTaskDetails(full);
        } catch (e) { /* task not in board */ }
      }
    }
  } catch (err) {
    console.error('Error loading board', err);
    const msg = err && err.message ? escapeHtml(err.message) : 'Unknown error';
    $('board').innerHTML = `<p class='text-red-500'>Failed to load board.${msg ? ` (${msg})` : ''}</p>`;
    // $('projectMembers').innerHTML = "";
  }
}

/* ---------- Column helpers ---------- */
async function promptAddColumn(projectId) {
  openModal('Create Column', (c) => {
    c.innerHTML = `<input id="col_title" class="w-full border p-2 rounded" placeholder="Column title" />`;
  }, async () => {
    const title = $('col_title').value.trim() || 'New Column';
    await apiPOST(`${API_BASE}/projects/${projectId}/columns`, {title});
    await loadBoard(projectId);
  });
}

async function promptDeleteColumn(projectId, column, allColumns) {
  const others = (allColumns || []).filter((c) => String(c.id) !== String(column.id));
  if (!others.length) {
    alert('Cannot delete the only column.');
    return;
  }
  const opts = others.map((c) => `<option value="${c.id}">${escapeHtml(c.title)}</option>`).join('');
  openModal('Delete Column', (c) => {
    c.innerHTML = `
      <p class="text-sm text-zinc-700 mb-3">Move all tasks from <strong>${escapeHtml(column.title)}</strong> to:</p>
      <select id="col_move_to" class="w-full border p-2 rounded">${opts}</select>
    `;
  }, async () => {
    const moveTo = parseInt($('col_move_to').value, 10);
    await apiDELETE(`${API_BASE}/columns/${column.id}`, { move_to_column_id: moveTo });
    await loadBoard(projectId);
  });
}

