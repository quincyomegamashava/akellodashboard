/** Task dependency / blocked-by helpers. */
(function() {
  const API = window.PM_API_BASE || '/api';
  window.pmProjectDependencies = [];

  window.pmListProjectTasks = function(boardData, excludeTaskId) {
    const rows = [];
    (boardData?.columns || []).forEach((col) => {
      (col.tasks || []).forEach((t) => {
        if (excludeTaskId && String(t.id) === String(excludeTaskId)) return;
        rows.push({ id: t.id, title: t.title, column: col.title, progress: t.progress });
      });
    });
    return rows;
  };

  window.pmLoadProjectDependencies = async function(projectId) {
    if (!projectId) return [];
    try {
      window.pmProjectDependencies = await pmApiGET(`${API}/projects/${projectId}/task-dependencies`);
    } catch (e) {
      window.pmProjectDependencies = [];
    }
    return window.pmProjectDependencies;
  };

  window.pmLoadTaskDependencies = async function(taskId) {
    return pmApiGET(`${API}/tasks/${taskId}/dependencies`);
  };

  window.pmAddTaskDependency = async function(taskId, dependsOnId) {
    return pmApiPOST(`${API}/tasks/${taskId}/dependencies`, { depends_on_task_id: dependsOnId });
  };

  window.pmRemoveTaskDependency = async function(taskId, depId) {
    return pmApiDELETE(`${API}/tasks/${taskId}/dependencies/${depId}`);
  };

  window.pmMountDependenciesEditor = async function(mount, task, boardData) {
    if (!mount || !task) return;
    mount.innerHTML = '<p class="text-xs text-zinc-500">Loading dependencies…</p>';
    const deps = await pmLoadTaskDependencies(task.id);
    const tasks = pmListProjectTasks(boardData, task.id);
    const taskById = (id) => tasks.find((t) => String(t.id) === String(id)) || pmFindTaskById(boardData, id);

    function render() {
      mount.innerHTML = `
        <div class="space-y-2">
          <div class="text-xs text-zinc-500">Primary blocker: ${task.blocked_by_task_id ? esc((taskById(task.blocked_by_task_id) || {}).title || '#' + task.blocked_by_task_id) : '—'}</div>
          <ul class="space-y-1">${(deps || []).map((d) => {
            const bt = taskById(d.depends_on_task_id);
            return `<li class="flex items-center gap-2 text-sm border rounded px-2 py-1">
              <span class="flex-1">${esc(bt ? bt.title : 'Task #' + d.depends_on_task_id)}</span>
              <button type="button" class="text-xs text-red-600 pm-dep-rm" data-dep="${d.id}">Remove</button>
            </li>`;
          }).join('') || '<li class="text-xs text-zinc-500 italic">No dependencies</li>'}</ul>
          <div class="flex gap-2">
            <select id="pm-dep-add-sel" class="flex-1 border rounded px-2 py-1 text-sm">
              <option value="">Add depends on…</option>
              ${tasks.map((t) => `<option value="${t.id}">${esc(t.title)}</option>`).join('')}
            </select>
            <button type="button" id="pm-dep-add-btn" class="text-xs px-2 py-1 bg-indigo-600 text-white rounded">Add</button>
          </div>
        </div>`;
      mount.querySelectorAll('.pm-dep-rm').forEach((btn) => {
        btn.onclick = async () => {
          await pmRemoveTaskDependency(task.id, btn.dataset.dep);
          deps.length = 0;
          (await pmLoadTaskDependencies(task.id)).forEach((d) => deps.push(d));
          render();
        };
      });
      const addBtn = mount.querySelector('#pm-dep-add-btn');
      if (addBtn) {
        addBtn.onclick = async () => {
          const sel = mount.querySelector('#pm-dep-add-sel');
          const v = sel ? sel.value : '';
          if (!v) return;
          try {
            await pmAddTaskDependency(task.id, parseInt(v, 10));
            const fresh = await pmLoadTaskDependencies(task.id);
            deps.length = 0;
            fresh.forEach((d) => deps.push(d));
            render();
          } catch (e) { alert(e.message || e); }
        };
      }
    }
    render();
  };

  window.pmMountBlockedByPicker = function(mount, boardData, task, onChange) {
    const tasks = pmListProjectTasks(boardData, task?.id);
    const sel = document.createElement('select');
    sel.className = 'w-full border border-zinc-200 rounded-lg px-2 py-1.5 text-sm';
    sel.innerHTML = '<option value="">— Not blocked —</option>' +
      tasks.map((t) => {
        const selAttr = String(task?.blocked_by_task_id) === String(t.id) ? ' selected' : '';
        return `<option value="${t.id}"${selAttr}>${t.title} (${t.column})</option>`;
      }).join('');
    sel.onchange = () => {
      const v = sel.value;
      if (typeof onChange === 'function') onChange(v ? parseInt(v, 10) : null);
    };
    mount.innerHTML = '';
    mount.appendChild(sel);
    return sel;
  };

  window.pmIsTaskBlocked = function(task, boardData) {
    if (!task?.blocked_by_task_id) return false;
    const blocker = pmFindTaskById(boardData, task.blocked_by_task_id);
    if (!blocker) return false;
    const prog = blocker.progress;
    if (blocker.subtask_total > 0) {
      return (blocker.subtask_done_count || 0) < blocker.subtask_total;
    }
    return (prog || 0) < 100;
  };

  window.pmFindTaskById = function(boardData, taskId) {
    for (const col of (boardData?.columns || [])) {
      for (const t of (col.tasks || [])) {
        if (String(t.id) === String(taskId)) return t;
      }
    }
    return null;
  };

  window.pmWarnBlockedMove = function(task, destColTitle) {
    if (!pmIsTaskBlocked(task, window.lastBoardData)) return true;
    const t = (destColTitle || '').toLowerCase();
    if (t.includes('done') || t.includes('complete')) {
      return confirm('This task is blocked by an incomplete dependency. Move to Done anyway?');
    }
    return true;
  };

  window.pmDrawGanttDependencyArrows = function(container, barPositions, projectDeps) {
    if (!container || !barPositions || !projectDeps || !projectDeps.length) return;
    container.style.position = 'relative';
    let svg = container.querySelector('#ganttDepSvg');
    if (!svg) {
      svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.id = 'ganttDepSvg';
      svg.setAttribute('class', 'absolute inset-0 pointer-events-none');
      svg.style.width = '100%';
      svg.style.height = '100%';
      container.style.position = 'relative';
      container.appendChild(svg);
    }
    svg.innerHTML = '';
    projectDeps.forEach((d) => {
      const from = barPositions[d.depends_on_task_id];
      const to = barPositions[d.task_id];
      if (!from || !to) return;
      const x1 = from.right;
      const y1 = from.cy;
      const x2 = to.left;
      const y2 = to.cy;
      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      const mid = (x1 + x2) / 2;
      path.setAttribute('d', `M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2},${y2}`);
      path.setAttribute('stroke', '#f59e0b');
      path.setAttribute('stroke-width', '1.5');
      path.setAttribute('fill', 'none');
      path.setAttribute('marker-end', 'url(#arrow)');
      svg.appendChild(path);
    });
    if (!svg.querySelector('#arrow')) {
      const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
      defs.innerHTML = '<marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="#f59e0b"/></marker>';
      svg.appendChild(defs);
    }
  };

  window.pmGanttRedrawDependencyArrows = function(container) {
    if (!container) return;
    const scrollRoot = container.querySelector('#ganttRightScroll') || container;
    const rootRect = scrollRoot.getBoundingClientRect();
    const positions = {};
    container.querySelectorAll('.gantt-bar[data-gantt-task-id]').forEach((bar) => {
      const r = bar.getBoundingClientRect();
      const id = bar.getAttribute('data-gantt-task-id');
      positions[id] = {
        left: r.left - rootRect.left + scrollRoot.scrollLeft,
        right: r.right - rootRect.left + scrollRoot.scrollLeft,
        cy: r.top - rootRect.top + r.height / 2,
      };
    });
    pmDrawGanttDependencyArrows(scrollRoot, positions, window.pmProjectDependencies || []);
  };

  let _ganttScrollRaf = null;
  window.pmWireGanttDependencyScroll = function(container) {
    if (!container) return;
    const scrollRoot = container.querySelector('#ganttRightScroll') || container;
    if (scrollRoot._pmDepScrollWired) return;
    scrollRoot._pmDepScrollWired = true;
    scrollRoot.addEventListener('scroll', () => {
      if (_ganttScrollRaf) cancelAnimationFrame(_ganttScrollRaf);
      _ganttScrollRaf = requestAnimationFrame(() => pmGanttRedrawDependencyArrows(container));
    });
  };

  window.pmComputeCriticalPathTaskIds = function(boardData, projectDeps) {
    const deps = projectDeps || [];
    if (!deps.length || !boardData) return new Set();
    const tasks = {};
    (boardData.columns || []).forEach((col) => {
      (col.tasks || []).forEach((t) => {
        if (t.start_date && t.end_date) tasks[t.id] = t;
      });
    });
    const graph = {};
    const rev = {};
    deps.forEach((d) => {
      if (!tasks[d.task_id] || !tasks[d.depends_on_task_id]) return;
      if (!graph[d.depends_on_task_id]) graph[d.depends_on_task_id] = [];
      graph[d.depends_on_task_id].push(d.task_id);
      if (!rev[d.task_id]) rev[d.task_id] = [];
      rev[d.task_id].push(d.depends_on_task_id);
    });
    const memo = {};
    function chainLen(id) {
      if (memo[id] != null) return memo[id];
      const kids = graph[id] || [];
      if (!kids.length) { memo[id] = 1; return 1; }
      memo[id] = 1 + Math.max(...kids.map(chainLen));
      return memo[id];
    }
    let best = 0;
    let endId = null;
    Object.keys(tasks).forEach((id) => {
      const n = parseInt(id, 10);
      const len = chainLen(n);
      if (len > best) { best = len; endId = n; }
    });
    if (!endId) return new Set();
    const path = new Set();
    let cur = endId;
    path.add(cur);
    while (rev[cur] && rev[cur].length) {
      cur = rev[cur][0];
      path.add(cur);
    }
    return path;
  };

  function esc(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
  }
})();
