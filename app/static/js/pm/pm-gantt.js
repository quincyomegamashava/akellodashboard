/** Gantt schedule render — requires PM globals from template. */

const GANTT_MONTH_COLORS = ['#1e3a5f', '#0d9488'];

function ganttMonthClusters(workDays) {
  const clusters = [];
  let cur = [];
  let curKey = null;
  workDays.forEach((d) => {
    const key = `${d.getFullYear()}-${d.getMonth()}`;
    if (key !== curKey) {
      if (cur.length) clusters.push(cur);
      cur = [];
      curKey = key;
    }
    cur.push(d);
  });
  if (cur.length) clusters.push(cur);
  return clusters;
}

function ganttMonthLabel(d) {
  const name = d.toLocaleString('en-US', { month: 'long' }).toUpperCase();
  return `${name} ${d.getFullYear()}`;
}

const GANTT_DESC_PREVIEW_PLACEHOLDER = 'Hover a description cell in the table to read the full text.';

function resetGanttDescPreview() {
  const body = $('ganttDescPreviewBody');
  if (!body) return;
  body.textContent = GANTT_DESC_PREVIEW_PLACEHOLDER;
  body.classList.add('text-zinc-400');
  body.classList.remove('text-zinc-700');
}

function ganttDescDecodedFromTrigger(trigger) {
  const enc = trigger.getAttribute('data-gantt-desc');
  if (enc == null) return null;
  try {
    const raw = decodeURIComponent(enc);
    return raw.trim() ? raw : null;
  } catch (e) {
    return null;
  }
}

function bindGanttDescPreviewTriggers(container) {
  if (!container) return;
  container.querySelectorAll('[data-gantt-desc-trigger]').forEach((el) => {
    el.addEventListener('mouseenter', () => {
      const raw = ganttDescDecodedFromTrigger(el);
      if (raw == null) return;
      const body = $('ganttDescPreviewBody');
      if (!body) return;
      body.textContent = raw;
      body.classList.remove('text-zinc-400');
      body.classList.add('text-zinc-700');
    });
  });
}

function destroyVisGantt() {
  resetGanttDescPreview();
  const container = $('ganttSheetMount');
  if (container && container._ganttClickHandler) {
    container.removeEventListener('click', container._ganttClickHandler);
    container._ganttClickHandler = null;
  }
  if (container) container.innerHTML = '';
}

function renderVisGantt(boardData) {
  destroyVisGantt();
  const container = $('ganttSheetMount');
  const emptyEl = $('ganttEmptyState');
  if (!container) return;

  if (!boardData || !boardData.columns) {
    if (emptyEl) {
      emptyEl.classList.remove('hidden');
      emptyEl.textContent = 'Select a project to view the schedule.';
    }
    return;
  }

  const ganttDueEl = $('ganttFilterDue');
  if (ganttDueEl) ganttDueFilter = ganttDueEl.value || 'all';
  const ganttOwnerEl = $('ganttFilterOwner');
  if (ganttOwnerEl) ganttFilterOwner = ganttOwnerEl.value || '';
  populateGanttOwnerOptions(boardData);

  const allDated = ganttCollectDatedTasks(boardData);
  if (!allDated.length) {
    if (emptyEl) {
      emptyEl.classList.remove('hidden');
      emptyEl.textContent = 'Add tasks with both start and end dates to see them on the schedule.';
    }
    return;
  }

  const filteredDated = allDated.filter(({ task }) => {
    const e = ganttParseLocal(task.end_date);
    return e && ganttMatchesFilters(task, e);
  });
  if (!filteredDated.length) {
    if (emptyEl) {
      emptyEl.classList.remove('hidden');
      emptyEl.textContent = 'No tasks match the filters. Try All owners or a different due range.';
    }
    return;
  }

  ensureColorMaps(boardData);
  const criticalIds = (typeof pmComputeCriticalPathTaskIds === 'function')
    ? pmComputeCriticalPathTaskIds(boardData, window.pmProjectDependencies || [])
    : new Set();
  const rows = [];
  let gMin = null;
  let gMax = null;

  (boardData.columns || []).forEach((col) => {
    const inCol = filteredDated.filter((x) => x.col.id === col.id);
    if (!inCol.length) return;
    rows.push({ type: 'group', title: col.title || `Column ${col.id}`, col });
    inCol.forEach(({ task }) => {
      const s = ganttParseLocal(task.start_date);
      const e = ganttParseLocal(task.end_date);
      if (!s || !e) return;
      rows.push({ type: 'task', task, col });
      const t0 = ganttStripTime(s).getTime();
      const t1 = ganttStripTime(e).getTime();
      if (gMin === null || t0 < gMin) gMin = t0;
      if (gMax === null || t1 > gMax) gMax = t1;
    });
  });

  if (!rows.length || gMin === null) {
    if (emptyEl) {
      emptyEl.classList.remove('hidden');
      emptyEl.textContent = 'No tasks match the filters. Try All owners or a different due range.';
    }
    return;
  }
  if (emptyEl) emptyEl.classList.add('hidden');

  const minD = new Date(gMin);
  const maxD = new Date(gMax);
  const workDays = ganttEnumerateWorkdays(minD, maxD);
  if (!workDays.length) {
    if (emptyEl) {
      emptyEl.classList.remove('hidden');
      emptyEl.textContent = 'No working days in range.';
    }
    return;
  }

  const totalW = workDays.length * GANTT_DAY_W;
  const idxFor = (date) => {
    const t = ganttStripTime(date).getTime();
    for (let i = 0; i < workDays.length; i++) {
      if (ganttStripTime(workDays[i]).getTime() === t) return i;
    }
    for (let i = 0; i < workDays.length; i++) {
      if (ganttStripTime(workDays[i]).getTime() >= t) return i;
    }
    return workDays.length - 1;
  };
  const lastIdxOnOrBefore = (date) => {
    const t = ganttStripTime(date).getTime();
    let last = -1;
    for (let i = 0; i < workDays.length; i++) {
      if (ganttStripTime(workDays[i]).getTime() <= t) last = i;
      else break;
    }
    return Math.max(0, last);
  };

  const weekClusters = ganttWeekClusters(workDays);
  const monthClusters = ganttMonthClusters(workDays);
  let phaseHtml = '';
  monthClusters.forEach((cl, mi) => {
    const wPx = cl.length * GANTT_DAY_W;
    const color = GANTT_MONTH_COLORS[mi % GANTT_MONTH_COLORS.length];
    const label = ganttMonthLabel(cl[0]);
    phaseHtml += `<div class="flex items-center justify-center text-[10px] font-bold text-white shrink-0 border-r border-white/20" style="width:${wPx}px;background:${color}">${label}</div>`;
  });

  let weekHtml = '';
  weekClusters.forEach((cl, wi) => {
    const wPx = cl.length * GANTT_DAY_W;
    const label = `WEEK ${wi + 1}`;
    weekHtml += `<div class="flex items-center justify-center text-[10px] font-semibold text-zinc-600 bg-zinc-100 border-r border-zinc-200 shrink-0" style="width:${wPx}px">${label}</div>`;
  });

  let dayHtml = '';
  workDays.forEach((d) => {
    dayHtml += `<div class="gantt-grid-line flex items-center justify-center text-[10px] text-zinc-500 shrink-0 border-r border-zinc-200/90" style="width:${GANTT_DAY_W}px">${ganttDayLetter(d)}</div>`;
  });

  const leftW = 520;
  let bodyHtml = '';
  rows.forEach((row) => {
    if (row.type === 'group') {
      bodyHtml += `<div class="flex items-center min-h-[30px] bg-zinc-300 border-b border-r border-zinc-300 font-semibold text-zinc-900 px-2 text-[11px]">${escapeHtml(row.title)}</div>`;
      bodyHtml += `<div class="min-h-[30px] bg-zinc-200/70 border-b border-zinc-200" style="width:${totalW}px"></div>`;
      return;
    }
    const task = row.task;
    const col = row.col;
    const s = ganttParseLocal(task.start_date);
    const e = ganttParseLocal(task.end_date);
    const assName = ganttAssigneeLabel(task);
    const dur = ganttCountBizInclusive(s, e);
    const pct = typeof task.progress === 'number' ? Math.max(0, Math.min(100, task.progress)) : 0;
    const today0 = ganttLocalDayStart(new Date());
    const end0 = e ? ganttStripTime(e) : null;
    const isOverdue = !!(end0 && end0 < today0);
    const barColor = (isOverdue && pct < 100) ? '#ef4444' : ganttProgressColor(pct);
    const isSubtask = task.item_type === 'subtask';
    const barOpacity = isSubtask ? '0.72' : '1';
    const si = idxFor(s);
    const ei = lastIdxOnOrBefore(e);
    const barLeft = si * GANTT_DAY_W;
    const barW = Math.max(GANTT_DAY_W, (ei - si + 1) * GANTT_DAY_W);

    const gridLines = workDays.map(() => `<div class="gantt-grid-line shrink-0" style="width:${GANTT_DAY_W}px"></div>`).join('');

    const rawDesc = task.description != null ? String(task.description) : '';
    const descOneLine = rawDesc.replace(/\s+/g, ' ').trim();
    const descCell = descOneLine
      ? `<div class="gantt-desc-trigger px-1 py-1.5 border-r border-zinc-100 truncate text-zinc-600 min-w-0 cursor-default" data-gantt-desc-trigger="1" data-gantt-desc="${encodeURIComponent(rawDesc)}">${escapeHtml(descOneLine)}</div>`
      : `<div class="px-1 py-1.5 border-r border-zinc-100 text-zinc-400 min-w-0">—</div>`;

    const openId = task.id;
    bodyHtml += `<div class="grid gap-0 border-b border-r border-zinc-200 bg-white hover:bg-zinc-50/90 cursor-pointer text-[11px] leading-tight${isSubtask ? ' bg-zinc-50/40' : ''}" style="grid-template-columns:${GANTT_LEFT_COLS}" data-gantt-task-id="${openId}">`;
    bodyHtml += `<div class="px-1.5 py-1.5 border-r border-zinc-100 truncate min-w-0${isSubtask ? ' pl-4 text-zinc-700' : ''}" title="${escapeHtml(task.title || '')}">${escapeHtml(task.title || '')}</div>`;
    bodyHtml += descCell;
    bodyHtml += `<div class="px-1 py-1.5 border-r border-zinc-100 truncate text-zinc-700 min-w-0">${escapeHtml(ganttOwnerShort(assName))}</div>`;
    bodyHtml += `<div class="px-1 py-1.5 border-r border-zinc-100 text-center text-zinc-600">${ganttFormatMMDDYY(s)}</div>`;
    bodyHtml += `<div class="px-1 py-1.5 border-r border-zinc-100 text-center text-zinc-600">${ganttFormatMMDDYY(e)}</div>`;
    bodyHtml += `<div class="px-1 py-1.5 border-r border-zinc-100 text-center text-zinc-600">${dur}</div>`;
    bodyHtml += `<div class="px-1 py-1 flex items-center"><div class="gantt-pct-cell w-full"><div class="gantt-pct-fill" style="width:${pct}%"></div><span class="relative z-[1] flex w-full justify-center text-[10px] font-medium text-zinc-800">${pct}%</span></div></div>`;
    bodyHtml += `</div>`;

    bodyHtml += `<div class="relative border-b border-zinc-200 bg-white min-h-[34px]" style="width:${totalW}px">`;
    bodyHtml += `<div class="absolute inset-0 flex pointer-events-none opacity-60">${gridLines}</div>`;
    const blockedCls = (typeof pmIsTaskBlocked === 'function' && pmIsTaskBlocked(task, boardData)) ? ' is-blocked' : '';
    const varCls = (typeof pmBaselineVarianceClass === 'function') ? pmBaselineVarianceClass(task.id, task.end_date) : '';
    const critCls = criticalIds.has(task.id) ? ' gantt-critical' : '';
    bodyHtml += `<div class="gantt-bar absolute bg-blue-600 pointer-events-auto${blockedCls}${varCls ? ' ' + varCls : ''}${critCls}" data-gantt-task-id="${openId}" style="left:${barLeft}px;width:${barW}px;background:${barColor};opacity:${barOpacity};border:1px solid rgba(0,0,0,0.12)"></div>`;
    bodyHtml += `</div>`;
  });

  const gridStyle = `display:grid;grid-template-columns:${leftW}px ${totalW}px;`;
  const msMarkers = (typeof pmGanttMilestoneMarkersHtml === 'function')
    ? pmGanttMilestoneMarkersHtml(workDays, GANTT_DAY_W)
    : `<div class="min-h-[24px] border-b border-zinc-200" style="width:${totalW}px"></div>`;
  container.innerHTML = `
    <div class="gantt-scroll-x rounded-lg border border-zinc-200 bg-white" id="ganttRightScroll">
      <div class="min-w-max" style="${gridStyle}">
        <div class="bg-zinc-100 border-b border-r border-zinc-200 px-2 py-1.5 text-[11px] font-semibold text-zinc-800">Task details</div>
        <div class="flex border-b border-zinc-200 min-h-[28px] overflow-hidden">${phaseHtml}</div>
        <div class="grid gap-0 border-b border-r border-zinc-200 bg-zinc-50 text-[10px] font-semibold text-zinc-700" style="grid-template-columns:${GANTT_LEFT_COLS}">
          <div class="px-1.5 py-1 border-r border-zinc-200">TASK TITLE</div>
          <div class="px-1 py-1 border-r border-zinc-200">DESCRIPTION</div>
          <div class="px-1 py-1 border-r border-zinc-200">TASK OWNER</div>
          <div class="px-1 py-1 border-r border-zinc-200 text-center">START</div>
          <div class="px-1 py-1 border-r border-zinc-200 text-center">DUE</div>
          <div class="px-1 py-1 border-r border-zinc-200 text-center">DAYS</div>
          <div class="px-1 py-1 text-center">% DONE</div>
        </div>
        <div class="flex border-b border-zinc-200 bg-zinc-50/80 min-h-[26px]">${weekHtml}</div>
        <div class="bg-violet-50/40 border-b border-r border-zinc-200 px-2 py-0.5 text-[10px] font-semibold text-violet-800 min-h-[22px] flex items-center">Milestones</div>
        ${msMarkers}
        <div class="flex border-b border-zinc-200 bg-white min-h-[22px]">${dayHtml}</div>
        ${bodyHtml}
      </div>
    </div>`;

  const ganttClickHandler = (ev) => {
    const el = ev.target.closest('[data-gantt-task-id]');
    if (el) {
      const id = el.getAttribute('data-gantt-task-id');
      if (id) openTaskFromTimeline(id);
    }
  };
  container._ganttClickHandler = ganttClickHandler;
  container.addEventListener('click', ganttClickHandler);
  bindGanttDescPreviewTriggers(container);
  if (typeof pmWireGanttDependencyScroll === 'function') pmWireGanttDependencyScroll(container);
  requestAnimationFrame(() => {
    if (typeof pmGanttRedrawDependencyArrows === 'function') pmGanttRedrawDependencyArrows(container);
  });
}
