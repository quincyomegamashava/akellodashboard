/** Portfolio dashboard helpers. */
(function() {
  const API = window.PM_API_BASE || '/api';
  let _lastStats = [];

  function esc(s) {
    if (!s) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function fmtDate(iso) {
    if (!iso) return '—';
    try { return new Date(iso).toLocaleDateString(); } catch (e) { return iso; }
  }

  window.pmLoadPortfolio = async function(programId, health) {
    const params = new URLSearchParams();
    if (programId) params.set('program_id', programId);
    if (health) params.set('health', health);
    const q = params.toString();
    _lastStats = await pmApiGET(`${API}/pm/portfolio${q ? '?' + q : ''}`);
    return _lastStats;
  };

  window.pmFilterPortfolioStats = function(stats, opts) {
    let rows = (stats || []).slice();
    const o = opts || {};
    if (o.ownerId) rows = rows.filter((s) => String(s.owner_id) === String(o.ownerId));
    if (o.myProjects && o.userId) rows = rows.filter((s) => String(s.owner_id) === String(o.userId));
    return rows;
  };

  window.pmGetLastPortfolioStats = function() { return _lastStats; };

  window.pmPortfolioSummary = function(stats) {
    const s = stats || [];
    return {
      total: s.length,
      red: s.filter((x) => x.health === 'red').length,
      yellow: s.filter((x) => x.health === 'yellow').length,
      green: s.filter((x) => x.health === 'green').length,
      overdue: s.reduce((n, x) => n + (x.overdue_count || 0), 0),
      blocked: s.reduce((n, x) => n + (x.blocked_count || 0), 0),
    };
  };

  function sortStats(stats, sortBy) {
    const copy = (stats || []).slice();
    const key = sortBy || 'health';
    const healthOrder = { red: 0, yellow: 1, green: 2 };
    copy.sort((a, b) => {
      if (key === 'name') return (a.project_name || '').localeCompare(b.project_name || '');
      if (key === 'pct') return (b.pct_complete || 0) - (a.pct_complete || 0);
      if (key === 'overdue') return (b.overdue_count || 0) - (a.overdue_count || 0);
      return (healthOrder[a.health] ?? 9) - (healthOrder[b.health] ?? 9);
    });
    return copy;
  }

  function sparklineSvg(projectId) {
    return `<svg class="pm-sparkline" data-spark-project="${projectId}" width="80" height="24" viewBox="0 0 80 24"></svg>`;
  }

  async function loadSparkline(svg) {
    const pid = svg.getAttribute('data-spark-project');
    if (!pid) return;
    try {
      const snaps = await pmApiGET(`${API}/projects/${pid}/stats/snapshots`);
      if (!snaps || !snaps.length) return;
      const pts = snaps.slice(-8);
      const maxT = Math.max(...pts.map((p) => p.total || 1), 1);
      const coords = pts.map((p, i) => {
        const x = (i / Math.max(pts.length - 1, 1)) * 76 + 2;
        const y = 22 - ((p.completed || 0) / maxT) * 18;
        return `${x},${y}`;
      }).join(' ');
      svg.innerHTML = `<polyline fill="none" stroke="#6366f1" stroke-width="1.5" points="${coords}"/>`;
    } catch (e) { /* ignore */ }
  }

  window.pmRenderPortfolioSummary = function(mount, stats) {
    if (!mount) return;
    const sum = pmPortfolioSummary(stats);
    mount.innerHTML = `
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div class="rounded-lg border border-zinc-200 bg-white p-3"><div class="text-xs text-zinc-500">Projects</div><div class="text-xl font-bold text-zinc-900">${sum.total}</div></div>
        <div class="rounded-lg border border-red-200 bg-red-50 p-3"><div class="text-xs text-red-700">At risk</div><div class="text-xl font-bold text-red-800">${sum.red}</div></div>
        <div class="rounded-lg border border-amber-200 bg-amber-50 p-3"><div class="text-xs text-amber-700">Watch</div><div class="text-xl font-bold text-amber-800">${sum.yellow}</div></div>
        <div class="rounded-lg border border-emerald-200 bg-emerald-50 p-3"><div class="text-xs text-emerald-700">On track</div><div class="text-xl font-bold text-emerald-800">${sum.green}</div></div>
        <div class="rounded-lg border border-zinc-200 bg-white p-3"><div class="text-xs text-zinc-500">Overdue tasks</div><div class="text-xl font-bold text-red-700">${sum.overdue}</div></div>
        <div class="rounded-lg border border-zinc-200 bg-white p-3"><div class="text-xs text-zinc-500">Blocked</div><div class="text-xl font-bold text-amber-700">${sum.blocked}</div></div>
      </div>`;
  };

  window.pmRenderPortfolioGrid = function(mount, stats, sortBy) {
    if (!mount) return;
    const rows = sortStats(stats, sortBy);
    if (!rows.length) {
      mount.innerHTML = '<p class="text-zinc-500 col-span-full">No projects to show.</p>';
      return;
    }
    const healthColor = { green: 'border-emerald-300 bg-emerald-50', yellow: 'border-amber-300 bg-amber-50', red: 'border-red-300 bg-red-50' };
    mount.innerHTML = rows.map((s) => `
      <a href="/projectmanagement?project=${s.project_id}" class="block rounded-xl border p-4 shadow-sm hover:shadow-md transition ${healthColor[s.health] || 'border-zinc-200 bg-white'}">
        <div class="flex justify-between gap-2">
          <div class="font-semibold text-zinc-900 min-w-0 truncate">${esc(s.project_name)}</div>
          <span class="text-[10px] uppercase font-semibold shrink-0 px-1.5 py-0.5 rounded ${s.health === 'red' ? 'bg-red-200 text-red-900' : s.health === 'yellow' ? 'bg-amber-200 text-amber-900' : 'bg-emerald-200 text-emerald-900'}">${esc(s.health)}</span>
        </div>
        <div class="mt-1 text-xs text-zinc-500">${esc(s.project_type || '')} · ${esc(s.owner_name || 'No owner')}</div>
        ${(s.program_names || []).length ? `<div class="text-[10px] text-indigo-600 mt-0.5">${esc(s.program_names.join(', '))}</div>` : ''}
        <div class="mt-2 flex items-end justify-between gap-2">
          <div>
            <div class="text-2xl font-bold text-indigo-700">${s.pct_complete}%</div>
            <div class="text-xs text-zinc-600">${s.completed_tasks}/${s.total_tasks} done · ${s.open_task_count || 0} open</div>
          </div>
          ${sparklineSvg(s.project_id)}
        </div>
        <div class="mt-2 flex gap-3 text-xs">
          <span class="text-red-700">${s.overdue_count} overdue</span>
          <span class="text-amber-700">${s.blocked_count} blocked</span>
        </div>
        ${(s.top_overdue_tasks || []).length ? `<div class="mt-2 text-xs space-y-0.5">${s.top_overdue_tasks.map((t) =>
          `<a class="text-red-700 hover:underline block truncate" href="/projectmanagement?project=${s.project_id}&task=${t.task_id}">${esc(t.title)}</a>`
        ).join('')}</div>` : ''}
        ${s.next_milestone ? `<div class="mt-2 text-xs text-zinc-600">Next milestone: <span class="font-medium">${esc(s.next_milestone)}</span>${s.next_milestone_date ? ` · ${fmtDate(s.next_milestone_date)}` : ''}</div>` : ''}
      </a>`).join('');
    mount.querySelectorAll('.pm-sparkline').forEach((svg) => loadSparkline(svg));
  };

  window.pmRenderPortfolioTable = function(mount, stats, sortBy) {
    if (!mount) return;
    const rows = sortStats(stats, sortBy);
    if (!rows.length) {
      mount.innerHTML = '<p class="text-zinc-500">No projects to show.</p>';
      return;
    }
    mount.innerHTML = `
      <div class="overflow-x-auto rounded-xl border border-zinc-200 bg-white">
        <table class="min-w-full text-sm">
          <thead class="bg-zinc-50 text-left text-zinc-600">
            <tr>
              <th class="px-3 py-2">Project</th><th class="px-3 py-2">Health</th><th class="px-3 py-2">Owner</th><th class="px-3 py-2">Type</th>
              <th class="px-3 py-2">%</th><th class="px-3 py-2">Tasks</th><th class="px-3 py-2">Open</th><th class="px-3 py-2">Overdue</th><th class="px-3 py-2">Blocked</th><th class="px-3 py-2">Next milestone</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map((s) => `
              <tr class="border-t border-zinc-100 hover:bg-zinc-50 cursor-pointer" onclick="location.href='/projectmanagement?project=${s.project_id}'">
                <td class="px-3 py-2 font-medium">${esc(s.project_name)}</td>
                <td class="px-3 py-2 capitalize">${esc(s.health)}</td>
                <td class="px-3 py-2">${esc(s.owner_name || '—')}</td>
                <td class="px-3 py-2">${esc(s.project_type)}</td>
                <td class="px-3 py-2">${s.pct_complete}%</td>
                <td class="px-3 py-2">${s.completed_tasks}/${s.total_tasks}</td>
                <td class="px-3 py-2">${s.open_task_count || 0}</td>
                <td class="px-3 py-2 text-red-700">
                  ${s.overdue_count}
                  ${(s.top_overdue_tasks || []).length ? `<div class="text-[10px] mt-0.5">${s.top_overdue_tasks.slice(0, 3).map((t) =>
                    `<a class="block text-red-600 hover:underline" href="/projectmanagement?project=${s.project_id}&task=${t.task_id}" onclick="event.stopPropagation()">${esc(t.title)}</a>`
                  ).join('')}</div>` : ''}
                </td>
                <td class="px-3 py-2 text-amber-700">${s.blocked_count}</td>
                <td class="px-3 py-2">${s.next_milestone ? esc(s.next_milestone) + (s.next_milestone_date ? ' (' + fmtDate(s.next_milestone_date) + ')' : '') : '—'}</td>
              </tr>`).join('')}
          </tbody>
        </table>
      </div>`;
  };

  window.pmLoadPrograms = async function() {
    return pmApiGET(`${API}/pm/programs`);
  };
})();
