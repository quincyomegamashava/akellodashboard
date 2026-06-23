/** Calendar views — requires PM globals from template. */

/** When a day has multiple tasks, prefer showing the most urgent hue on the year mini-dot. */
function calDayWorstBarColor(items) {
  if (!items || !items.length) return null;
  for (const it of items) {
    if (calIsOverdue(it.task)) return '#ef4444';
  }
  for (const it of items) {
    if (calScheduleBarColor(it.task) === '#f59e0b') return '#f59e0b';
  }
  return calScheduleBarColor(items[0].task);
}

function calTaskChipMarkup(item) {
  const { task, columnTitle } = item;
  const tid = item.parentTaskId || task.id;
  const rawTitle = (task.title || '').slice(0, 80);
  const barColor = calScheduleBarColor(task);
  const done = calIsDone(task);
  const nAsg = Array.isArray(task.assignees) ? task.assignees.length : 0;
  const badge = nAsg ? `<span class="pm-cal-asg">${nAsg > 9 ? '9+' : String(nAsg)}</span>` : '';
  const cls = ['pm-cal-chip'];
  if (done) cls.push('pm-cal-chip--done');
  if (task.item_type === 'subtask') cls.push('pm-cal-chip--subtask');
  const tip = escapeHtml([task.title || '', columnTitle].filter(Boolean).join(' — ').slice(0, 220));
  return `<button type="button" class="${cls.join(' ')}" data-cal-task-id="${tid}" title="${tip}" style="--chip-bar:${barColor}"><span class="pm-cal-chip-dot" aria-hidden="true"></span>${badge}<span class="pm-cal-chip-t">${escapeHtml(rawTitle)}</span></button>`;
}

function calWeekStartSunday(d) {
  const t = ganttStripTime(d);
  const w = t.getDay();
  const s = new Date(t);
  s.setDate(s.getDate() - w);
  return s;
}

function calSameLocalDay(a, b) {
  return calDayKey(a) === calDayKey(b);
}

function syncCalViewToggleButtons() {
  document.querySelectorAll('#panel-calendar .cal-view-btn').forEach((b) => {
    const mode = b.getAttribute('data-cal-mode');
    const on = mode === calendarViewMode;
    b.setAttribute('aria-pressed', on ? 'true' : 'false');
  });
}

function calNavigateToday() {
  calendarCursor = ganttStripTime(new Date());
  renderCalendar(lastBoardData);
}

function calNavigatePrev() {
  const c = calendarCursor;
  if (calendarViewMode === 'month') {
    calendarCursor = new Date(c.getFullYear(), c.getMonth() - 1, 1);
  } else if (calendarViewMode === 'week') {
    const ws = calWeekStartSunday(c);
    ws.setDate(ws.getDate() - 7);
    calendarCursor = ws;
  } else {
    calendarCursor = new Date(c.getFullYear() - 1, 0, 1);
  }
  renderCalendar(lastBoardData);
}

function calNavigateNext() {
  const c = calendarCursor;
  if (calendarViewMode === 'month') {
    calendarCursor = new Date(c.getFullYear(), c.getMonth() + 1, 1);
  } else if (calendarViewMode === 'week') {
    const ws = calWeekStartSunday(c);
    ws.setDate(ws.getDate() + 7);
    calendarCursor = ws;
  } else {
    calendarCursor = new Date(c.getFullYear() + 1, 0, 1);
  }
  renderCalendar(lastBoardData);
}

function calSetViewMode(mode) {
  if (mode !== 'year' && mode !== 'month' && mode !== 'week') return;
  calendarViewMode = mode;
  const c = calendarCursor;
  if (mode === 'month') {
    calendarCursor = new Date(c.getFullYear(), c.getMonth(), 1);
  } else if (mode === 'year') {
    calendarCursor = new Date(c.getFullYear(), 0, 1);
  }
  renderCalendar(lastBoardData);
}

function renderCalendarMonth(mount, boardData, idx) {
  const c = calendarCursor;
  const y = c.getFullYear();
  const m = c.getMonth();
  const first = new Date(y, m, 1);
  const gridStart = new Date(first);
  gridStart.setDate(first.getDate() - first.getDay());
  const today = ganttStripTime(new Date());
  const titleEl = $('calNavTitle');
  if (titleEl) titleEl.textContent = first.toLocaleString(undefined, { month: 'long', year: 'numeric' });

  const dows = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  let h = '<div class="pm-cal-month-grid">';
  dows.forEach((label, i) => {
    const wk = i === 0 || i === 6;
    h += `<div class="pm-cal-dow${wk ? ' pm-cal-dow--weekend' : ''}">${label}</div>`;
  });
  for (let i = 0; i < 42; i++) {
    const cellDate = new Date(gridStart);
    cellDate.setDate(gridStart.getDate() + i);
    const inMonth = cellDate.getMonth() === m;
    const wk = cellDate.getDay();
    const isWeekend = wk === 0 || wk === 6;
    const isToday = calSameLocalDay(cellDate, today);
    const k = calDayKey(cellDate);
    const items = (idx.byDay.get(k) || []).slice();
    items.sort((a, b) => String(a.task.title || '').localeCompare(String(b.task.title || '')));
    const maxShow = 3;
    const shown = items.slice(0, maxShow);
    const more = items.length - shown.length;
    let cls = 'pm-cal-cell';
    if (!inMonth) cls += ' pm-cal-cell--muted';
    if (isWeekend) cls += ' pm-cal-cell--weekend';
    if (isToday) cls += ' pm-cal-cell--today';
    if (items.length) cls += ' pm-cal-cell--has-tasks';
    h += `<div class="${cls}">`;
    const dnCls = ['pm-cal-daynum'];
    if (!inMonth) dnCls.push('pm-cal-daynum--muted');
    if (isToday) dnCls.push('pm-cal-daynum--pill');
    h += `<div class="pm-cal-daynum-row"><span class="${dnCls.join(' ')}">${cellDate.getDate()}</span>${typeof pmCalendarMilestoneHtml === 'function' ? pmCalendarMilestoneHtml(k) : ''}</div>`;
    h += '<div class="pm-cal-chips">';
    h += shown.map((it) => calTaskChipMarkup(it)).join('');
    if (more > 0) h += `<div class="pm-cal-more">+${more} more</div>`;
    h += '</div></div>';
  }
  h += '</div>';
  mount.innerHTML = h;
}

function renderCalendarWeek(mount, boardData, idx) {
  const ws = calWeekStartSunday(calendarCursor);
  const titleEl = $('calNavTitle');
  const we = new Date(ws);
  we.setDate(we.getDate() + 6);
  if (titleEl) {
    titleEl.textContent = ws.getFullYear() === we.getFullYear()
      ? `${ws.toLocaleString(undefined, { month: 'short', day: 'numeric' })} – ${we.toLocaleString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}`
      : `${ws.toLocaleDateString()} – ${we.toLocaleDateString()}`;
  }
  const today = ganttStripTime(new Date());
  const dows = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  let h = '<div class="pm-cal-month-grid">';
  dows.forEach((label, i) => {
    const wk = i === 0 || i === 6;
    h += `<div class="pm-cal-dow${wk ? ' pm-cal-dow--weekend' : ''}">${label}</div>`;
  });
  for (let i = 0; i < 7; i++) {
    const cellDate = new Date(ws);
    cellDate.setDate(ws.getDate() + i);
    const wk = cellDate.getDay();
    const isWeekend = wk === 0 || wk === 6;
    const isToday = calSameLocalDay(cellDate, today);
    const k = calDayKey(cellDate);
    const items = (idx.byDay.get(k) || []).slice();
    items.sort((a, b) => String(a.task.title || '').localeCompare(String(b.task.title || '')));
    let cls = 'pm-cal-cell pm-cal-week-cell';
    if (isWeekend) cls += ' pm-cal-cell--weekend';
    if (isToday) cls += ' pm-cal-cell--today';
    if (items.length) cls += ' pm-cal-cell--has-tasks';
    h += `<div class="${cls}">`;
    const label = cellDate.toLocaleString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
    const dnCls = ['pm-cal-daynum'];
    if (isToday) dnCls.push('pm-cal-daynum--pill');
    h += `<div class="pm-cal-daynum-row"><span class="${dnCls.join(' ')}">${escapeHtml(label)}</span></div>`;
    h += '<div class="pm-cal-chips">';
    items.forEach((it) => { h += calTaskChipMarkup(it); });
    if (!items.length) h += '<span class="pm-cal-week-empty">No dated tasks</span>';
    h += '</div></div>';
  }
  h += '</div>';
  mount.innerHTML = h;
}

function renderCalendarYear(mount, boardData, idx) {
  const y = calendarCursor.getFullYear();
  const titleEl = $('calNavTitle');
  if (titleEl) titleEl.textContent = String(y);
  const today = ganttStripTime(new Date());
  let html = '<div class="pm-cal-year-grid">';
  for (let m = 0; m < 12; m++) {
    const first = new Date(y, m, 1);
    const gridStart = new Date(first);
    gridStart.setDate(first.getDate() - first.getDay());
    html += '<div class="pm-cal-mini-wrap">';
    html += `<div class="pm-cal-mini-title">${first.toLocaleString(undefined, { month: 'long' })}</div>`;
    html += '<div class="pm-cal-mini-grid">';
    ['S', 'M', 'T', 'W', 'T', 'F', 'S'].forEach((d) => {
      html += `<div class="pm-cal-mini-dh">${d}</div>`;
    });
    for (let i = 0; i < 42; i++) {
      const cellDate = new Date(gridStart);
      cellDate.setDate(gridStart.getDate() + i);
      const inMonth = cellDate.getMonth() === m;
      const k = calDayKey(cellDate);
      const list = idx.byDay.get(k) || [];
      const firstTask = list[0];
      let dot = '';
      if (list.length && firstTask) {
        const bar = calDayWorstBarColor(list);
        dot = `<span class="pm-cal-mini-dot" style="--chip-bar:${bar}"></span>`;
      }
      let dcls = 'pm-cal-mini-day';
      if (inMonth) dcls += ' pm-cal-mini-day--in';
      if (calSameLocalDay(cellDate, today)) dcls += ' pm-cal-mini-day--today';
      const label = inMonth ? String(cellDate.getDate()) : '';
      const tip = list.map((x) => x.task.title).join(', ');
      const openFirst = list.length ? ` data-cal-task-id="${list[0].parentTaskId || list[0].task.id}" style="cursor:pointer"` : '';
      html += `<div class="${dcls}" title="${escapeHtml(tip.slice(0, 200))}"${openFirst}>${label}${dot}</div>`;
    }
    html += '</div></div>';
  }
  html += '</div>';
  mount.innerHTML = html;
}
