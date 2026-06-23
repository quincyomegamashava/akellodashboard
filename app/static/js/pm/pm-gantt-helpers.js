/** Gantt helpers — requires PM globals from template. */

function renderCalendar(boardData) {
  const mount = $('calendarMount');
  if (!mount) return;
  if (!(calendarCursor instanceof Date) || isNaN(calendarCursor.getTime())) {
    calendarCursor = ganttStripTime(new Date());
  }
  const note = $('calNoteUndated');
  if (!currentProjectId || !boardData || !boardData.columns) {
    mount.innerHTML = '<p class="pm-cal-empty">Select a project to view the calendar.</p>';
    const titleEl = $('calNavTitle');
    if (titleEl) titleEl.textContent = '—';
    if (note) note.classList.add('hidden');
    syncCalViewToggleButtons();
    return;
  }
  const idx = buildCalendarTaskIndex(boardData);
  if (note) {
    if (idx.undated > 0) {
      note.classList.remove('hidden');
      note.textContent = `${idx.undated} task${idx.undated === 1 ? '' : 's'} have no start/end date and are not shown on the calendar. Open the Board tab to add dates.`;
    } else {
      note.classList.add('hidden');
    }
  }
  if (calendarViewMode === 'month') {
    renderCalendarMonth(mount, boardData, idx);
  } else if (calendarViewMode === 'week') {
    renderCalendarWeek(mount, boardData, idx);
  } else {
    renderCalendarYear(mount, boardData, idx);
  }
  syncCalViewToggleButtons();
}

const GANTT_DAY_W = 20;
const GANTT_LEFT_COLS = 'minmax(0, 1.1fr) minmax(0, 0.88fr) 0.58fr 0.62fr 0.62fr 0.34fr 0.48fr';

function ganttStripTime(d) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

function ganttParseLocal(iso) {
  if (!iso) return null;
  const s = String(iso).slice(0, 10);
  const p = s.split('-').map(Number);
  if (p.length < 3 || !p[0]) return null;
  return new Date(p[0], p[1] - 1, p[2]);
}

function ganttEnumerateWorkdays(minD, maxD) {
  const out = [];
  let cur = ganttStripTime(minD);
  const end = ganttStripTime(maxD);
  while (cur <= end) {
    const wd = cur.getDay();
    if (wd !== 0 && wd !== 6) out.push(new Date(cur));
    cur = new Date(cur.getFullYear(), cur.getMonth(), cur.getDate() + 1);
  }
  return out;
}

function ganttCountBizInclusive(s, e) {
  let n = 0;
  let c = ganttStripTime(s);
  const end = ganttStripTime(e);
  if (c > end) return 0;
  while (c <= end) {
    const wd = c.getDay();
    if (wd !== 0 && wd !== 6) n++;
    c = new Date(c.getFullYear(), c.getMonth(), c.getDate() + 1);
  }
  return Math.max(n, 0);
}

function ganttFormatMMDDYY(d) {
  if (!d || isNaN(d.getTime())) return '—';
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  const y = String(d.getFullYear()).slice(-2);
  return `${m}/${day}/${y}`;
}

function ganttProgressColor(pct) {
  const n = typeof pct === 'number' ? pct : 0;
  if (n >= 100) return '#16a34a'; // green
  if (n > 0) return '#f59e0b'; // amber
  return '#9ca3af'; // grey
}

function ganttDayLetter(d) {
  return ['S', 'M', 'T', 'W', 'T', 'F', 'S'][d.getDay()];
}

function ganttOwnerShort(name) {
  if (!name || name === 'Unassigned') return '—';
  const parts = String(name).trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 12);
  return `${parts[0].slice(0, 8)} ${parts[parts.length - 1].charAt(0)}`.trim();
}

function ganttAssigneeLabel(task) {
  if (Array.isArray(task.assignees) && task.assignees.length) {
    return (task.assignees[0].name || String(task.assignees[0]));
  }
  return 'Unassigned';
}

function ganttLocalDayStart(d) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

function ganttDueInThisWeek(d) {
  const today = ganttLocalDayStart(new Date());
  const dow = today.getDay();
  const monOffset = dow === 0 ? -6 : 1 - dow;
  const weekStart = new Date(today);
  weekStart.setDate(weekStart.getDate() + monOffset);
  const weekEnd = new Date(weekStart);
  weekEnd.setDate(weekEnd.getDate() + 6);
  const dd = ganttLocalDayStart(d);
  return dd >= weekStart && dd <= weekEnd;
}

function ganttDueInThisMonth(d) {
  const now = new Date();
  return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth();
}

function ganttCollectDatedTasks(boardData) {
  const out = [];
  pmFlattenBoardScheduleEntries(boardData).forEach((entry) => {
    const task = pmScheduleTaskLike(entry);
    if (!task.start_date || !task.end_date) return;
    const a = ganttParseLocal(task.start_date);
    const b = ganttParseLocal(task.end_date);
    if (!a || !b || isNaN(a.getTime()) || isNaN(b.getTime())) return;
    if (b < a) return;
    out.push({ task, col: entry.col });
  });
  return out;
}

function ganttMatchesFilters(task, dueEnd) {
  if (ganttFilterOwner && ganttAssigneeLabel(task) !== ganttFilterOwner) return false;
  if (ganttDueFilter === 'week' && !ganttDueInThisWeek(dueEnd)) return false;
  if (ganttDueFilter === 'month' && !ganttDueInThisMonth(dueEnd)) return false;
  return true;
}

function populateGanttOwnerOptions(boardData) {
  const sel = $('ganttFilterOwner');
  if (!sel || !boardData) return;
  const allDated = ganttCollectDatedTasks(boardData);
  const owners = [...new Set(allDated.map(({ task }) => ganttAssigneeLabel(task)))].sort((a, b) => a.localeCompare(b));
  const prev = ganttFilterOwner;
  sel.innerHTML = '<option value="">All</option>'
    + owners.map((o) => `<option value="${escapeHtml(o)}">${escapeHtml(o)}</option>`).join('');
  if (prev && owners.includes(prev)) {
    sel.value = prev;
    ganttFilterOwner = prev;
  } else {
    sel.value = '';
    ganttFilterOwner = '';
  }
}

function ganttWeekClusters(workDays) {
  const clusters = [];
  let cur = [];
  let curKey = null;
  workDays.forEach((d, i) => {
    const mon = new Date(d);
    const day = mon.getDay();
    const diff = day === 0 ? -6 : 1 - day;
    mon.setDate(mon.getDate() + diff);
    const key = mon.getTime();
    if (curKey === null) {
      curKey = key;
      cur = [{ d, i }];
    } else if (key === curKey) {
      cur.push({ d, i });
    } else {
      clusters.push(cur);
      cur = [{ d, i }];
      curKey = key;
    }
  });
  if (cur.length) clusters.push(cur);
  return clusters;
}

