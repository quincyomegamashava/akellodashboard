/** Task details modal — requires PM globals from template. */

async function syncTaskAfterSubtaskChange(taskId) {
  try {
    const full = await apiGET(`${API_BASE}/tasks/${taskId}`);
    for (const col of (lastBoardData?.columns || [])) {
      const idx = (col.tasks || []).findIndex((t) => String(t.id) === String(taskId));
      if (idx >= 0) {
        col.tasks[idx] = full;
        break;
      }
    }
    pmUpdateTaskCardOnBoard(taskId, full);
    await pmRefreshTimelineViews();
    openTaskDetails(full);
  } catch (e) {
    if (currentProjectId) await loadBoard(currentProjectId);
    const updated = findTaskOnBoard(taskId);
    if (updated) openTaskDetails(updated);
  }
}

async function pmLoadTaskCommentsAndActivity(taskId) {
  const commentsEl = document.getElementById('pm-task-comments-list');
  const activityEl = document.getElementById('pm-task-activity-list');
  if (!commentsEl && !activityEl) return;
  try {
    const [comments, activities] = await Promise.all([
      apiGET(`${API_BASE}/tasks/${taskId}/comments`),
      apiGET(`${API_BASE}/tasks/${taskId}/activities`),
    ]);
    if (commentsEl) {
      commentsEl.innerHTML = (comments || []).length
        ? comments.map((c) => `<div class="border border-zinc-100 rounded-lg px-2.5 py-2 bg-white"><div class="text-xs text-zinc-500">${escapeHtml(c.author_name || 'User')} · ${c.created_at ? formatDate(c.created_at) : ''}</div><div class="mt-0.5 text-zinc-800">${typeof pmFormatCommentBody === 'function' ? pmFormatCommentBody(c.body) : escapeHtml(c.body)}</div></div>`).join('')
        : '<p class="text-zinc-500 italic text-xs">No comments yet</p>';
    }
    if (activityEl) {
      activityEl.innerHTML = (activities || []).length
        ? activities.map((a) => `<div><span class="font-medium">${escapeHtml(a.actor_name || 'System')}</span> ${escapeHtml(a.action)}${a.detail ? `: ${escapeHtml(a.detail)}` : ''}</div>`).join('')
        : '<p class="text-zinc-500 italic">No activity recorded</p>';
    }
  } catch (e) {
    if (commentsEl) commentsEl.innerHTML = '<p class="text-red-500 text-xs">Failed to load comments</p>';
  }
}

function pmTaskSection(title, bodyHtml, extraClass = '') {
  return `<section class="pm-task-section ${extraClass}">
    <div class="pm-task-section__head">${escapeHtml(title)}</div>
    <div class="pm-task-section__body">${bodyHtml}</div>
  </section>`;
}

async function openTaskDetails(task) {
  if (!task) return;
  task.attachments = task.attachments || [];
  const users = await loadUsers();
  const userMap = new Map((users || []).map((u) => [String(u.id), u.name]));
  const createdByName = task.created_by != null
    ? (userMap.get(String(task.created_by)) || `User #${task.created_by}`)
    : '';
  const assigneesLabel = (Array.isArray(task.assignees) && task.assignees.length)
    ? task.assignees.map((a) => a.name).join(', ')
    : 'Unassigned';
  const startFmt = task.start_date ? formatDate(task.start_date) : '—';
  const endFmt = task.end_date ? formatDate(task.end_date) : '—';
  const progress = typeof task.progress === 'number' ? Math.max(0, Math.min(100, task.progress)) : 0;
  const subTotal = task.subtask_total || (task.subtasks || []).length;
  const subDone = task.subtask_done_count != null
    ? task.subtask_done_count
    : (task.subtasks || []).filter((s) => s.is_done).length;
  const s = ganttParseLocal(task.start_date);
  const e = ganttParseLocal(task.end_date);
  const duration = (s && e) ? ganttCountBizInclusive(s, e) : null;
  const columnTitle = (() => {
    const src = lastBoardData || boardData;
    for (const col of (src?.columns || [])) {
      if (String(col.id) === String(task.column_id)) return col.title || '';
    }
    return '';
  })();
  const attachmentsHtml = task.attachments.length
    ? `<ul class="divide-y divide-zinc-100 border border-zinc-200/80 rounded-xl bg-white/80 backdrop-blur-sm">
        ${task.attachments.map((a) => `
          <li class="px-3.5 py-2.5 flex flex-wrap items-center gap-2">
            <button type="button" class="text-left text-indigo-700 hover:text-indigo-900 hover:underline text-sm min-w-0 truncate flex-1 transition-colors" data-details-preview-aid="${a.id}">
              ${escapeHtml(a.original_name || 'Attachment')}
            </button>
            <a class="text-xs text-zinc-500 hover:text-zinc-900 underline underline-offset-2" href="${taskAttachmentFileUrl(a.id, 'attachment')}" target="_blank" rel="noopener">Download</a>
            <button type="button" class="text-xs text-red-600 hover:text-red-700 underline underline-offset-2" data-details-remove-aid="${a.id}">Remove</button>
          </li>
        `).join('')}
      </ul>`
    : '<div class="text-sm text-zinc-500 italic border border-dashed border-zinc-300 rounded-xl px-3 py-3 bg-zinc-50/70">No attachments</div>';

  openModal('Task details', (c) => {
    const overviewBody = `
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0">
          <h3 class="text-lg font-semibold tracking-tight text-zinc-900 break-words">${escapeHtml(task.title || 'Untitled task')}</h3>
          ${columnTitle ? `<div class="mt-1.5 inline-flex items-center rounded-full border border-zinc-200 bg-zinc-100/70 px-2.5 py-0.5 text-[11px] font-medium text-zinc-600">Column: <span class="ml-1 text-zinc-800">${escapeHtml(columnTitle)}</span></div>` : ''}
        </div>
        <div class="text-xs font-semibold text-indigo-700 bg-indigo-50 border border-indigo-100 px-2.5 py-1 rounded-full shrink-0">${progress}% complete</div>
      </div>
      <div class="mt-2">
        <div class="h-1.5 bg-zinc-100 rounded-full overflow-hidden">
          <div class="h-full bg-indigo-500 rounded-full transition-all duration-300" style="width:${progress}%"></div>
        </div>
      </div>`;

    const descriptionBody = `
      <div class="text-sm text-zinc-700 whitespace-pre-wrap break-words leading-snug">${escapeHtml(task.description || 'No description')}</div>`;

    const scheduleBody = `
      <div class="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
        <div class="border border-zinc-200 bg-zinc-50/50 rounded-lg p-2"><div class="text-[10px] uppercase tracking-wide text-zinc-500">Start</div><div class="mt-0.5 font-semibold text-zinc-800">${escapeHtml(startFmt)}</div></div>
        <div class="border border-zinc-200 bg-zinc-50/50 rounded-lg p-2"><div class="text-[10px] uppercase tracking-wide text-zinc-500">Due</div><div class="mt-0.5 font-semibold text-zinc-800">${escapeHtml(endFmt)}</div></div>
        <div class="border border-zinc-200 bg-zinc-50/50 rounded-lg p-2"><div class="text-[10px] uppercase tracking-wide text-zinc-500">Duration</div><div class="mt-0.5 font-semibold text-zinc-800">${duration != null ? `${duration} day${duration === 1 ? '' : 's'}` : '—'}</div></div>
        <div class="border border-zinc-200 bg-zinc-50/50 rounded-lg p-2"><div class="text-[10px] uppercase tracking-wide text-zinc-500">Assignees</div><div class="mt-0.5 font-semibold text-zinc-800 break-words">${escapeHtml(assigneesLabel)}</div></div>
      </div>
      ${task.labels && task.labels.length ? `<div class="mt-2 flex flex-wrap gap-1">${task.labels.map((lb) => `<span class="pm-label-chip" style="background:${lb.color || '#6366f1'}">${escapeHtml(lb.name)}</span>`).join('')}</div>` : ''}
      ${task.blocked_by_task_id ? `<div class="mt-2 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1">Blocked by: <button type="button" class="underline font-medium" data-open-blocker="${task.blocked_by_task_id}">${escapeHtml(task.blocked_by_title || ('Task #' + task.blocked_by_task_id))}</button></div>` : ''}
      ${createdByName ? `<div class="mt-2 text-xs text-zinc-500">Created by <span class="font-medium text-zinc-700">${escapeHtml(createdByName)}</span></div>` : ''}`;

    const canEditTask = typeof pmCanEditTasks === 'function' ? pmCanEditTasks() : true;
    const subtasksBody = `
      ${subTotal ? `<div class="flex items-center justify-between gap-2 mb-2"><span class="text-xs text-zinc-500">${subDone}/${subTotal} complete</span></div><div class="h-1.5 bg-zinc-100 rounded-full overflow-hidden mb-2"><div class="h-full bg-emerald-500 rounded-full transition-all duration-300" style="width:${Math.round(100 * subDone / subTotal)}%"></div></div>` : ''}
      <div id="pm-subtask-list" class="space-y-1.5"></div>
      ${canEditTask ? `<div class="grid gap-2 mt-2">
        <div class="flex flex-wrap gap-2">
          <input type="text" id="pm-subtask-input" class="flex-1 min-w-[10rem] border border-zinc-200 rounded-lg px-3 py-1.5 text-sm" placeholder="Add a sub-task…" />
          <input type="date" id="pm-subtask-start" class="border border-zinc-200 rounded-lg px-2 py-1.5 text-sm" title="Start date" />
          <input type="date" id="pm-subtask-end" class="border border-zinc-200 rounded-lg px-2 py-1.5 text-sm" title="Due date" />
          <button type="button" id="pm-subtask-add" class="px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-sm hover:bg-indigo-700">Add</button>
        </div>
        <div class="pm-subtask-assignees-field">
          <label class="text-xs text-zinc-500 block mb-1">Assignees (optional)</label>
          <div id="pm-subtask-assignees-wrap"></div>
        </div>
      </div>` : ''}`;

    const commentsBody = `
      <div id="pm-task-comments-list" class="space-y-2 max-h-40 overflow-y-auto text-sm mb-2"></div>
      <div class="flex gap-2">
        <input type="text" id="pm-task-comment-input" class="flex-1 border border-zinc-200 rounded-lg px-3 py-1.5 text-sm" placeholder="Add a comment…" />
        <button type="button" id="pm-task-comment-add" class="px-3 py-1.5 rounded-lg bg-indigo-600 text-white text-sm hover:bg-indigo-700">Post</button>
      </div>`;

    const timeBody = `<div id="pm-time-entries-mount"></div>`;

    const activityBody = `
      <details class="rounded-lg border border-zinc-200 bg-zinc-50/50">
        <summary class="px-3 py-1.5 text-sm font-medium text-zinc-700 cursor-pointer">Show activity log</summary>
        <div id="pm-task-activity-list" class="px-3 pb-2 text-xs text-zinc-600 space-y-1 max-h-48 overflow-y-auto"></div>
      </details>`;

    const actionsBody = `
      <div class="flex flex-wrap items-center justify-end gap-2">
        <button type="button" class="px-3 py-1.5 rounded-lg border border-zinc-300 bg-white text-zinc-700 hover:bg-zinc-50 transition-colors text-sm" data-details-act="close">Close</button>
        ${canEditTask ? `<button type="button" class="px-3 py-1.5 rounded-lg border border-indigo-200 bg-indigo-600 text-white hover:bg-indigo-700 transition-colors text-sm" data-details-act="edit">Edit</button>
        ${task.can_delete ? '<button type="button" class="px-3 py-1.5 rounded-lg border border-red-200 bg-red-50 text-red-700 hover:bg-red-100 transition-colors text-sm" data-details-act="delete">Delete</button>' : ''}` : ''}
      </div>`;

    c.innerHTML = [
      pmTaskSection('Overview', overviewBody, 'pm-task-section--overview'),
      pmTaskSection('Description', descriptionBody, 'pm-task-section--description'),
      pmTaskSection('Schedule & people', scheduleBody, 'pm-task-section--schedule'),
      pmTaskSection('Sub-tasks', subtasksBody, 'pm-task-section--subtasks'),
      pmTaskSection('Comments', commentsBody, 'pm-task-section--comments'),
      pmTaskSection('Time log', timeBody, 'pm-task-section--time'),
      pmTaskSection('Activity', activityBody, 'pm-task-section--activity'),
      pmTaskSection('Attachments', attachmentsHtml, 'pm-task-section--attachments'),
      pmTaskSection('Actions', actionsBody, 'pm-task-section--actions'),
    ].join('');

    c.querySelectorAll('[data-details-preview-aid]').forEach((btn) => {
      btn.onclick = () => {
        const id = parseInt(btn.getAttribute('data-details-preview-aid'), 10);
        const found = (task.attachments || []).find((x) => x.id === id);
        if (found) openAttachmentPreview(found);
      };
    });
    c.querySelectorAll('[data-details-remove-aid]').forEach((btn) => {
      btn.onclick = async () => {
        const id = parseInt(btn.getAttribute('data-details-remove-aid'), 10);
        if (!id) return;
        if (!confirm('Remove this attachment?')) return;
        try {
          await apiDELETE(`${API_BASE}/task-attachments/${id}`);
          task.attachments = (task.attachments || []).filter((x) => x.id !== id);
          // Re-open to refresh the details attachment list UI.
          openTaskDetails(task);
          if (currentProjectId) await loadBoard(currentProjectId);
        } catch (e) {
          alert(e.message || e);
        }
      };
    });

    const closeBtn = c.querySelector('[data-details-act="close"]');
    if (closeBtn) closeBtn.onclick = closeModal;

    const editBtn = c.querySelector('[data-details-act="edit"]');
    if (editBtn) {
      editBtn.onclick = () => {
        closeModal();
        promptEditTask(task);
      };
    }

    const delBtn = c.querySelector('[data-details-act="delete"]');
    if (delBtn) {
      delBtn.onclick = () => {
        closeModal();
        confirmDeleteTask(task.id);
      };
    }

    c.querySelectorAll('[data-open-blocker]').forEach((btn) => {
      btn.onclick = () => {
        const bid = btn.getAttribute('data-open-blocker');
        const blocker = findTaskOnBoard(bid);
        if (blocker) openTaskDetails(blocker);
      };
    });

    if (typeof pmStartActivityPoll === 'function' && currentProjectId) {
      pmStartActivityPoll(currentProjectId, () => pmLoadTaskCommentsAndActivity(task.id));
    }

    const subtaskList = c.querySelector('#pm-subtask-list');
    const refreshSubtasks = () => syncTaskAfterSubtaskChange(task.id);
    renderPmSubtaskRows(subtaskList, task, users, refreshSubtasks);

    const asgWrap = c.querySelector('#pm-subtask-assignees-wrap');
    if (asgWrap) {
      pmMountAssigneePicker(asgWrap, { selected: [], compact: true });
    }

    const subAddBtn = c.querySelector('#pm-subtask-add');
    const subInput = c.querySelector('#pm-subtask-input');
    const addSubtask = async () => {
      const title = (subInput?.value || '').trim();
      if (!title) return;
      const startVal = ($('pm-subtask-start') || {}).value || null;
      const endVal = ($('pm-subtask-end') || {}).value || null;
      const assignees = pmGetAssigneeIdsFromMount(asgWrap);
      try {
        await apiPOST(`${API_BASE}/tasks/${task.id}/subtasks`, {
          title,
          start_date: startVal || undefined,
          end_date: endVal || undefined,
          assignees,
        });
        if (subInput) subInput.value = '';
        if ($('pm-subtask-start')) $('pm-subtask-start').value = '';
        if ($('pm-subtask-end')) $('pm-subtask-end').value = '';
        if (asgWrap) pmMountAssigneePicker(asgWrap, { selected: [], compact: true });
        await refreshSubtasks();
      } catch (e) {
        alert(e.message || e);
      }
    };
    if (subAddBtn) subAddBtn.onclick = addSubtask;
    if (subInput) {
      subInput.onkeydown = (e) => {
        if (e.key === 'Enter') {
          e.preventDefault();
          addSubtask();
        }
      };
    }

    pmLoadTaskCommentsAndActivity(task.id);
    if (typeof pmRenderTimeEntries === 'function') {
      pmRenderTimeEntries(c.querySelector('#pm-time-entries-mount'), task.id);
    }
    const commentAdd = c.querySelector('#pm-task-comment-add');
    const commentInput = c.querySelector('#pm-task-comment-input');
    if (commentAdd && commentInput) {
      const postComment = async () => {
        const body = (commentInput.value || '').trim();
        if (!body) return;
        try {
          await apiPOST(`${API_BASE}/tasks/${task.id}/comments`, { body });
          commentInput.value = '';
          await pmLoadTaskCommentsAndActivity(task.id);
        } catch (e) {
          alert(e.message || e);
        }
      };
      commentAdd.onclick = postComment;
      commentInput.onkeydown = (e) => {
        if (e.key === 'Enter') { e.preventDefault(); postComment(); }
      };
      if (typeof pmWireCommentMentions === 'function') {
        pmWireCommentMentions(commentInput, () => currentProjectId);
      }
    }
  }, null, false);
  modalBackdrop.classList.add('task-details-modal');
  modalBackdrop.addEventListener('click', function pmModalClosePoll() {
    if (typeof pmStopActivityPoll === 'function') pmStopActivityPoll();
  }, { once: true });
}

